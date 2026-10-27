"""
FastAPI dependencies for auth-service:
- Database session injection
- Admin JWT extraction and role validation
"""

from typing import Annotated, Generator, Optional
from fastapi import Depends, Header, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import jwt
from sqlalchemy.orm import Session

from src.config import settings
from src.core.audit import audit_logger
from src.core.security import ROLE_SUPERADMIN, decode_admin_token
from src.db.database import AdminUserORM, Database

# Engine / Database singleton for auth-service
_db_instance = Database(settings.DATABASE_URL)


def get_db_instance() -> Database:
    return _db_instance


def get_db() -> Generator[Session, None, None]:
    """Dependency yielding a scoped database session."""
    yield from _db_instance.session()


security_bearer = HTTPBearer(auto_error=False)


def get_client_ip(
    x_forwarded_for: Annotated[Optional[str], Header()] = None,
    x_real_ip: Annotated[Optional[str], Header()] = None,
) -> str:
    """Extract client IP handling reverse proxy headers."""
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    if x_real_ip:
        return x_real_ip.strip()
    return "127.0.0.1"


async def get_current_admin(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security_bearer),
    db: Session = Depends(get_db),
) -> AdminUserORM:
    """
    Validates Bearer token as an admin JWT.
    Retrieves and returns the corresponding active AdminUserORM entity.
    """
    if not credentials or not credentials.credentials:
        audit_logger.log_auth_failure(
            reason="MISSING_ADMIN_BEARER_TOKEN",
            usuario="unauthenticated",
            event_type="ADMIN_AUTH_FAILED",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Falta el encabezado Authorization: Bearer <admin_token>.",
        )

    token = credentials.credentials
    try:
        payload = decode_admin_token(token)
    except jwt.ExpiredSignatureError:
        audit_logger.log_auth_failure(
            reason="EXPIRED_ADMIN_TOKEN",
            usuario="unknown",
            event_type="ADMIN_TOKEN_EXPIRED",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="El token de administrador ha expirado.",
        )
    except jwt.PyJWTError as exc:
        audit_logger.log_auth_failure(
            reason=f"INVALID_ADMIN_TOKEN: {str(exc)}",
            usuario="unknown",
            event_type="ADMIN_TOKEN_INVALID",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de administrador inválido.",
        )

    admin_id = payload.get("sub")
    admin = db.get(AdminUserORM, admin_id)
    if not admin or not admin.is_active:
        audit_logger.log_auth_failure(
            reason="ADMIN_USER_NOT_FOUND_OR_INACTIVE",
            usuario=payload.get("username", "unknown"),
            event_type="ADMIN_USER_INACTIVE",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="El usuario administrador no existe o se encuentra inactivo.",
        )

    return admin


def require_superadmin(
    admin: AdminUserORM = Depends(get_current_admin),
) -> AdminUserORM:
    """Ensures the authenticated administrator holds the SUPERADMIN role."""
    if admin.role != ROLE_SUPERADMIN:
        audit_logger.log_security_event(
            event_type="SUPERADMIN_PRIVILEGE_DENIED",
            severity="HIGH",
            client_id=admin.client_id or "platform",
            usuario=admin.username,
            details={"attempted_role": admin.role, "required": ROLE_SUPERADMIN},
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso restringido: requiere permisos de SUPERADMIN.",
        )
    return admin
