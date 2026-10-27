"""
Autenticación y gestión de administradores.

Roles:
- SUPERADMIN: acceso total, gestiona administradores.
- CLIENT_ADMIN: acceso restringido a los datos de su `client_id`.

Incluye bloqueo temporal tras intentos fallidos consecutivos.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import List, Optional

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
    ROLE_CLIENT_ADMIN,
    ROLE_SUPERADMIN,
    VALID_ROLES,
    hash_password,
    issue_admin_token,
    validate_password_strength,
    verify_password,
)
from src.db.database import AdminUserORM, ClientORM, as_utc


@dataclass
class AdminToken:
    access_token: str
    expires_in_seconds: int
    admin: AdminUserORM


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
            self._audit_failure(username, "ACCOUNT_LOCKED", ip_address, client_id=admin.client_id)
            raise AccountLockedError("Cuenta bloqueada temporalmente por intentos fallidos. Intente más tarde.")

        if not verify_password(password, admin.password_hash):
            admin.failed_attempts = (admin.failed_attempts or 0) + 1
            if admin.failed_attempts >= settings.ADMIN_MAX_FAILED_ATTEMPTS:
                admin.locked_until = now + timedelta(minutes=settings.ADMIN_LOCKOUT_MINUTES)
                admin.failed_attempts = 0
                audit_logger.log_security_event(
                    event_type="ADMIN_ACCOUNT_LOCKED",
                    severity="CRITICAL",
                    client_id=admin.client_id or "platform",
                    usuario=username,
                    details={"lockout_minutes": settings.ADMIN_LOCKOUT_MINUTES},
                    ip_address=ip_address,
                )
            self.db.commit()
            self._audit_failure(username, "INVALID_PASSWORD", ip_address, client_id=admin.client_id)
            raise AuthenticationError("Usuario o contraseña incorrectos.")

        if not admin.is_active:
            self._audit_failure(username, "ACCOUNT_DISABLED", ip_address, client_id=admin.client_id)
            raise AuthenticationError("Usuario o contraseña incorrectos.")

        admin.failed_attempts = 0
        admin.locked_until = None
        admin.last_login_at = now
        self.db.commit()

        expires = settings.ADMIN_TOKEN_EXPIRES_SECONDS
        token = issue_admin_token(
            {"sub": admin.id, "username": admin.username, "role": admin.role, "client_id": admin.client_id},
            expires_seconds=expires,
        )
        audit_logger.log_security_event(
            event_type="ADMIN_LOGIN_SUCCESS",
            severity="LOW",
            client_id=admin.client_id or "platform",
            usuario=admin.username,
            details={"role": admin.role},
            ip_address=ip_address,
        )
        return AdminToken(access_token=token, expires_in_seconds=expires, admin=admin)

    def _audit_failure(self, username: str, reason: str, ip_address: Optional[str], client_id: Optional[str] = None) -> None:
        audit_logger.log_auth_failure(
            reason=reason,
            ip_address=ip_address,
            client_id=client_id or "platform",
            usuario=username,
            event_type="ADMIN_LOGIN_FAILED",
        )

    def change_password(self, admin: AdminUserORM, current_password: str, new_password: str) -> None:
        if not verify_password(current_password, admin.password_hash):
            audit_logger.log_auth_failure(
                reason="INVALID_CURRENT_PASSWORD", client_id=admin.client_id or "platform",
                usuario=admin.username, event_type="ADMIN_PASSWORD_CHANGE_FAILED", severity="MEDIUM",
            )
            raise AuthenticationError("La contraseña actual no es correcta.")
        _validate_password(new_password)
        admin.password_hash = hash_password(new_password)
        self.db.commit()
        audit_logger.log_security_event(
            event_type="ADMIN_PASSWORD_CHANGED", severity="LOW",
            client_id=admin.client_id or "platform", usuario=admin.username, details={},
        )


def _validate_password(password: str) -> None:
    try:
        validate_password_strength(password)
    except ValueError as exc:
        raise ValidationFailedError(str(exc)) from exc


class AdminUserService:
    """Gestión de administradores (solo SUPERADMIN)."""

    def __init__(self, db: Session):
        self.db = db

    def list_admins(self) -> List[AdminUserORM]:
        return list(self.db.scalars(select(AdminUserORM).order_by(AdminUserORM.created_at)))

    def _validate_role_and_client(self, role: str, client_id: Optional[str]) -> Optional[str]:
        if role not in VALID_ROLES:
            raise ValidationFailedError(f"Rol inválido. Valores permitidos: {', '.join(VALID_ROLES)}.")
        if role == ROLE_CLIENT_ADMIN:
            if not client_id:
                raise ValidationFailedError("client_id es obligatorio para el rol CLIENT_ADMIN.")
            if not self.db.get(ClientORM, client_id):
                raise NotFoundError(f"El cliente '{client_id}' no existe.")
            return client_id
        return None  # SUPERADMIN no está atado a un cliente

    def create_admin(
        self,
        actor: AdminUserORM,
        username: str,
        password: str,
        role: str,
        client_id: Optional[str],
        full_name: Optional[str],
    ) -> AdminUserORM:
        username = username.strip().lower()
        effective_client = self._validate_role_and_client(role, client_id)
        _validate_password(password)
        if self.db.scalar(select(AdminUserORM).where(AdminUserORM.username == username)):
            raise ConflictError(f"El usuario '{username}' ya existe.")

        admin = AdminUserORM(
            username=username,
            full_name=full_name,
            password_hash=hash_password(password),
            role=role,
            client_id=effective_client,
        )
        self.db.add(admin)
        self.db.commit()
        audit_logger.log_security_event(
            event_type="ADMIN_USER_CREATED", severity="MEDIUM",
            client_id=effective_client or "platform", usuario=actor.username,
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
        client_id = changes["client_id"] if "client_id" in changes else admin.client_id
        if "role" in changes or "client_id" in changes:
            admin.client_id = self._validate_role_and_client(role, client_id)
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
            event_type="ADMIN_USER_UPDATED", severity="MEDIUM",
            client_id=admin.client_id or "platform", usuario=actor.username,
            details={"target_admin": admin.username, "fields": sorted(k for k in changes if k != "password")
                     + (["password"] if changes.get("password") else [])},
        )
        return admin


def ensure_superadmin(admin: AdminUserORM) -> None:
    if admin.role != ROLE_SUPERADMIN:
        raise ForbiddenError("Esta operación requiere rol SUPERADMIN.")
