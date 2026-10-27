"""
Dependencies for LLM Gateway:
- Internal Service Key verification for /internal/v1/*
- Admin JWT or Internal Key verification for /api/v1/usage/*
"""

from typing import Any, Dict, Generator, Optional
from fastapi import Depends, Header, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import jwt
from sqlalchemy.orm import Session

from src.config import settings
from src.core.audit import audit_logger
from src.db.models import Database

_db_instance = Database(settings.DATABASE_URL)


def get_db_instance() -> Database:
    return _db_instance


def get_db() -> Generator[Session, None, None]:
    yield from _db_instance.session()


security_bearer = HTTPBearer(auto_error=False)


def require_internal_key(
    x_internal_key: Optional[str] = Header(None, alias="X-Internal-Key"),
) -> None:
    """Verifies that the caller possesses the shared INTERNAL_SERVICE_KEY."""
    if not x_internal_key or x_internal_key != settings.INTERNAL_SERVICE_KEY:
        audit_logger.log_auth_failure(
            reason="INVALID_OR_MISSING_INTERNAL_KEY",
            usuario="internal-service",
            event_type="INTERNAL_AUTH_FAILED",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Falta o es inválida la cabecera X-Internal-Key de comunicación interna.",
        )


def require_admin_or_internal(
    x_internal_key: Optional[str] = Header(None, alias="X-Internal-Key"),
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security_bearer),
) -> Dict[str, Any]:
    """
    Allows access either if the caller presents valid X-Internal-Key
    OR a valid Administrator JWT token.
    Returns token payload or internal service context.
    """
    if x_internal_key and x_internal_key == settings.INTERNAL_SERVICE_KEY:
        return {"sub": "internal", "role": "INTERNAL_SERVICE", "client_id": None}

    if credentials and credentials.credentials:
        token = credentials.credentials
        try:
            payload = jwt.decode(
                token,
                settings.ADMIN_JWT_SECRET,
                algorithms=[settings.JWT_ALGORITHM],
                audience=settings.ADMIN_TOKEN_AUDIENCE,
                issuer=settings.JWT_ISSUER,
            )
            return payload
        except jwt.PyJWTError as exc:
            audit_logger.log_auth_failure(
                reason=f"INVALID_ADMIN_TOKEN: {str(exc)}",
                usuario="unknown",
                event_type="ADMIN_TOKEN_INVALID",
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token de administrador inválido o expirado.",
            )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Se requiere token de Administrador (Bearer) o clave interna (X-Internal-Key).",
    )
