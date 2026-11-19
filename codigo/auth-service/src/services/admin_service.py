"""
Autenticación y gestión de administradores.

Roles:
- GLOBAL_ADMIN: acceso total, gestiona organizaciones, sedes y administradores.
- ORG_ADMIN: acceso restringido a los datos de su `org_id`.

Incluye bloqueo temporal tras intentos fallidos consecutivos.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.config import settings
from src.core.audit import audit_logger
from src.core.exceptions import (
    AccountLockedError,
    AuthenticationError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ValidationFailedError,
)
from src.core.security import (
    DUMMY_PASSWORD_HASH,
    ROLE_GLOBAL_ADMIN,
    ROLE_ORG_ADMIN,
    VALID_ROLES,
    hash_password,
    issue_admin_token,
    validate_password_strength,
    verify_password,
)
from src.db.database import AdminUserORM, OrganizationORM, as_utc

DEFAULT_SITE_LABEL = "Sede"
DEFAULT_SITE_LABEL_PLURAL = "Sedes"


@dataclass
class AdminToken:
    access_token: str
    expires_in_seconds: int
    admin: AdminUserORM
    org_name: Optional[str]
    site_label: str
    site_label_plural: str


def resolve_org_display_context(
    db: Session, org_id: Optional[str]
) -> Tuple[Optional[str], str, str]:
    """Obtiene nombre y etiquetas de sede de la organización, o valores por defecto."""
    if org_id:
        org = db.get(OrganizationORM, org_id)
        if org is not None:
            return org.nombre, org.site_label, org.site_label_plural
    return None, DEFAULT_SITE_LABEL, DEFAULT_SITE_LABEL_PLURAL


def serialize_admin_profile(
    admin: AdminUserORM, org: Optional[OrganizationORM] = None
) -> Dict[str, Any]:
    if org is not None:
        org_name: Optional[str] = org.nombre
        site_label = org.site_label
        site_label_plural = org.site_label_plural
    else:
        org_name = None
        site_label = DEFAULT_SITE_LABEL
        site_label_plural = DEFAULT_SITE_LABEL_PLURAL
    return {
        "admin_id": admin.id,
        "username": admin.username,
        "full_name": admin.full_name,
        "role": admin.role,
        "org_id": admin.org_id,
        "org_name": org_name,
        "site_label": site_label,
        "site_label_plural": site_label_plural,
        "is_active": admin.is_active,
        "last_login_at": as_utc(admin.last_login_at),
        "created_at": as_utc(admin.created_at),
    }


class AdminAuthService:
    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------ login
    def login(self, username: str, password: str, ip_address: Optional[str] = None) -> AdminToken:
        username = username.strip().lower()
        admin = self.db.scalar(select(AdminUserORM).where(AdminUserORM.username == username))
        now = datetime.now(timezone.utc)

        if admin is None:
            verify_password(password, DUMMY_PASSWORD_HASH)  # igualar tiempos de respuesta
            self._audit_failure(username, "UNKNOWN_USER", ip_address)
            raise AuthenticationError("Usuario o contraseña incorrectos.")

        locked_until = as_utc(admin.locked_until)
        if locked_until and locked_until > now:
            self._audit_failure(username, "ACCOUNT_LOCKED", ip_address, org_id=admin.org_id)
            raise AccountLockedError("Cuenta bloqueada temporalmente por intentos fallidos. Intente más tarde.")

        if not verify_password(password, admin.password_hash):
            admin.failed_attempts = (admin.failed_attempts or 0) + 1
            if admin.failed_attempts >= settings.ADMIN_MAX_FAILED_ATTEMPTS:
                admin.locked_until = now + timedelta(minutes=settings.ADMIN_LOCKOUT_MINUTES)
                admin.failed_attempts = 0
                audit_logger.log_security_event(
                    event_type="ADMIN_ACCOUNT_LOCKED",
                    severity="CRITICAL",
                    org_id=admin.org_id or "platform",
                    usuario=username,
                    details={"lockout_minutes": settings.ADMIN_LOCKOUT_MINUTES},
                    ip_address=ip_address,
                )
            self.db.commit()
            self._audit_failure(username, "INVALID_PASSWORD", ip_address, org_id=admin.org_id)
            raise AuthenticationError("Usuario o contraseña incorrectos.")

        if not admin.is_active:
            self._audit_failure(username, "ACCOUNT_DISABLED", ip_address, org_id=admin.org_id)
            raise AuthenticationError("Usuario o contraseña incorrectos.")

        admin.failed_attempts = 0
        admin.locked_until = None
        admin.last_login_at = now
        self.db.commit()

        expires = settings.ADMIN_TOKEN_EXPIRES_SECONDS
        token = issue_admin_token(
            {"sub": admin.id, "username": admin.username, "role": admin.role, "org_id": admin.org_id},
            expires_seconds=expires,
        )
        org_name, site_label, site_label_plural = resolve_org_display_context(self.db, admin.org_id)
        audit_logger.log_security_event(
            event_type="ADMIN_LOGIN_SUCCESS",
            severity="LOW",
            org_id=admin.org_id or "platform",
            usuario=admin.username,
            details={"role": admin.role},
            ip_address=ip_address,
        )
        return AdminToken(
            access_token=token,
            expires_in_seconds=expires,
            admin=admin,
            org_name=org_name,
            site_label=site_label,
            site_label_plural=site_label_plural,
        )

    def _audit_failure(
        self, username: str, reason: str, ip_address: Optional[str], org_id: Optional[str] = None
    ) -> None:
        audit_logger.log_auth_failure(
            reason=reason,
            ip_address=ip_address,
            org_id=org_id or "platform",
            usuario=username,
            event_type="ADMIN_LOGIN_FAILED",
        )

    def change_password(self, admin: AdminUserORM, current_password: str, new_password: str) -> None:
        if not verify_password(current_password, admin.password_hash):
            audit_logger.log_auth_failure(
                reason="INVALID_CURRENT_PASSWORD",
                org_id=admin.org_id or "platform",
                usuario=admin.username,
                event_type="ADMIN_PASSWORD_CHANGE_FAILED",
                severity="MEDIUM",
            )
            raise AuthenticationError("La contraseña actual no es correcta.")
        _validate_password(new_password)
        admin.password_hash = hash_password(new_password)
        self.db.commit()
        audit_logger.log_security_event(
            event_type="ADMIN_PASSWORD_CHANGED",
            severity="LOW",
            org_id=admin.org_id or "platform",
            usuario=admin.username,
            details={},
        )


def _validate_password(password: str) -> None:
    try:
        validate_password_strength(password)
    except ValueError as exc:
        raise ValidationFailedError(str(exc)) from exc


class AdminUserService:
    """Gestión de administradores (solo GLOBAL_ADMIN)."""

    def __init__(self, db: Session):
        self.db = db

    def list_admins(self) -> List[AdminUserORM]:
        return list(self.db.scalars(select(AdminUserORM).order_by(AdminUserORM.created_at)))

    def build_profile(self, admin: AdminUserORM) -> Dict[str, Any]:
        org = self.db.get(OrganizationORM, admin.org_id) if admin.org_id else None
        return serialize_admin_profile(admin, org)

    def build_profiles(self, admins: List[AdminUserORM]) -> List[Dict[str, Any]]:
        org_ids = {a.org_id for a in admins if a.org_id}
        orgs_map: Dict[str, OrganizationORM] = {}
        if org_ids:
            orgs = self.db.scalars(
                select(OrganizationORM).where(OrganizationORM.org_id.in_(org_ids))
            )
            orgs_map = {o.org_id: o for o in orgs}
        return [
            serialize_admin_profile(a, orgs_map.get(a.org_id) if a.org_id else None)
            for a in admins
        ]

    def _validate_role_and_org(self, role: str, org_id: Optional[str]) -> Optional[str]:
        if role not in VALID_ROLES:
            raise ValidationFailedError(f"Rol inválido. Valores permitidos: {', '.join(VALID_ROLES)}.")
        if role == ROLE_ORG_ADMIN:
            if not org_id:
                raise ValidationFailedError("org_id es obligatorio para el rol ORG_ADMIN.")
            if not self.db.get(OrganizationORM, org_id):
                raise NotFoundError(f"La organización '{org_id}' no existe.")
            return org_id
        return None  # GLOBAL_ADMIN no está atado a una organización

    def create_admin(
        self,
        actor: AdminUserORM,
        username: str,
        password: str,
        role: str,
        org_id: Optional[str],
        full_name: Optional[str],
    ) -> AdminUserORM:
        username = username.strip().lower()
        effective_org = self._validate_role_and_org(role, org_id)
        _validate_password(password)
        if self.db.scalar(select(AdminUserORM).where(AdminUserORM.username == username)):
            raise ConflictError(f"El usuario '{username}' ya existe.")

        admin = AdminUserORM(
            username=username,
            full_name=full_name,
            password_hash=hash_password(password),
            role=role,
            org_id=effective_org,
        )
        self.db.add(admin)
        self.db.commit()
        audit_logger.log_security_event(
            event_type="ADMIN_USER_CREATED",
            severity="MEDIUM",
            org_id=effective_org or "platform",
            usuario=actor.username,
            details={"new_admin": username, "role": role},
        )
        return admin

    def update_admin(self, actor: AdminUserORM, admin_id: str, changes: dict) -> AdminUserORM:
        admin = self.db.get(AdminUserORM, admin_id)
        if not admin:
            raise NotFoundError("Administrador no encontrado.")

        if admin.id == actor.id and (changes.get("is_active") is False or changes.get("role") not in (None, actor.role)):
            raise ForbiddenError("No puede desactivarse ni cambiar su propio rol.")

        role = changes.get("role") or admin.role
        org_id = changes["org_id"] if "org_id" in changes else admin.org_id
        if "role" in changes or "org_id" in changes:
            admin.org_id = self._validate_role_and_org(role, org_id)
            admin.role = role

        if changes.get("password"):
            _validate_password(changes["password"])
            admin.password_hash = hash_password(changes["password"])
            admin.failed_attempts = 0
            admin.locked_until = None
        if "full_name" in changes:
            admin.full_name = changes["full_name"]
        if changes.get("is_active") is not None:
            admin.is_active = bool(changes["is_active"])

        self.db.commit()
        audit_logger.log_security_event(
            event_type="ADMIN_USER_UPDATED",
            severity="MEDIUM",
            org_id=admin.org_id or "platform",
            usuario=actor.username,
            details={
                "target_admin": admin.username,
                "fields": sorted(k for k in changes if k != "password")
                + (["password"] if changes.get("password") else []),
            },
        )
        return admin


def ensure_global_admin(admin: AdminUserORM) -> None:
    if admin.role != ROLE_GLOBAL_ADMIN:
        raise ForbiddenError("Esta operación requiere rol GLOBAL_ADMIN.")
