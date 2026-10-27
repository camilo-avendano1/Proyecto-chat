"""
JWT Token management and FastAPI security dependency.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import jwt

from src.config import settings

security_bearer = HTTPBearer(auto_error=False)


class JWTHandler:
    def __init__(
        self,
        secret_key: str = settings.WIDGET_JWT_SECRET or settings.JWT_SECRET_KEY,
        algorithm: str = settings.JWT_ALGORITHM,
        admin_secret: str = settings.ADMIN_JWT_SECRET,
    ):
        self.secret_key = secret_key
        self.algorithm = algorithm
        self.admin_secret = admin_secret

    def create_session_token(
        self,
        data: Dict[str, Any],
        expires_delta_seconds: int = settings.SESSION_EXPIRES_SECONDS,
    ) -> str:
        to_encode = data.copy()
        now = datetime.now(timezone.utc)
        expire = now + timedelta(seconds=expires_delta_seconds)
        to_encode.update({
            "exp": expire,
            "iat": now,
            "aud": settings.WIDGET_TOKEN_AUDIENCE,
            "typ": "widget",
        })
        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        return encoded_jwt

    def decode_token(self, token: str) -> Dict[str, Any]:
        from src.infrastructure.security.audit_logger import audit_logger
        # Try primary widget secret, then fallback secret
        secrets_to_try = [self.secret_key]
        if settings.JWT_SECRET_KEY and settings.JWT_SECRET_KEY not in secrets_to_try:
            secrets_to_try.append(settings.JWT_SECRET_KEY)

        last_error = None
        for secret in secrets_to_try:
            try:
                payload = jwt.decode(
                    token,
                    secret,
                    algorithms=[self.algorithm],
                    options={"verify_aud": False},
                )
                return payload
            except jwt.ExpiredSignatureError as e:
                last_error = e
                break
            except jwt.PyJWTError as e:
                last_error = e
                continue

        if isinstance(last_error, jwt.ExpiredSignatureError):
            audit_logger.log_security_event(
                event_type="JWT_TOKEN_EXPIRED",
                severity="MEDIUM",
                client_id="unknown",
                tenant_id="unknown",
                usuario="unknown",
                details={"reason": "Signature has expired"},
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="El token de sesión ha expirado. Por favor renueve la sesión en /api/v1/widget/session.",
            )
        else:
            audit_logger.log_security_event(
                event_type="JWT_TOKEN_INVALID_OR_TAMPERED",
                severity="HIGH",
                client_id="unknown",
                tenant_id="unknown",
                usuario="unknown",
                details={"reason": str(last_error)},
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token de sesión inválido o adulterado.",
            )

    def decode_admin_token(self, token: str) -> Dict[str, Any]:
        from src.infrastructure.security.audit_logger import audit_logger
        try:
            payload = jwt.decode(
                token,
                self.admin_secret,
                algorithms=[self.algorithm],
                audience=settings.ADMIN_TOKEN_AUDIENCE,
            )
            if payload.get("typ") != "admin":
                raise jwt.InvalidTokenError("Token no es de tipo admin")
            return payload
        except jwt.ExpiredSignatureError:
            audit_logger.log_security_event(
                event_type="ADMIN_TOKEN_EXPIRED",
                severity="MEDIUM",
                client_id="unknown",
                tenant_id="unknown",
                usuario="admin",
                details={"reason": "Signature has expired"},
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="El token de administrador ha expirado.",
            )
        except jwt.PyJWTError as e:
            audit_logger.log_security_event(
                event_type="ADMIN_TOKEN_INVALID",
                severity="HIGH",
                client_id="unknown",
                tenant_id="unknown",
                usuario="admin",
                details={"reason": str(e)},
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token de administrador inválido.",
            )


default_jwt_handler = JWTHandler()


async def get_current_session(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security_bearer),
) -> Dict[str, Any]:
    """
    FastAPI security dependency for protected diagnostic endpoints.
    Requires Bearer <session_token> in the Authorization header.
    """
    if not credentials or not credentials.credentials:
        from src.infrastructure.security.audit_logger import audit_logger
        audit_logger.log_security_event(
            event_type="MISSING_BEARER_AUTHORIZATION",
            severity="MEDIUM",
            client_id="unknown",
            tenant_id="unknown",
            usuario="unknown",
            details={"endpoint": "protected_diagnostic"},
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Falta el encabezado Authorization: Bearer <session_token>.",
        )
    return default_jwt_handler.decode_token(credentials.credentials)


async def get_current_admin(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security_bearer),
) -> Dict[str, Any]:
    """
    FastAPI security dependency for admin observability and management endpoints.
    Requires Bearer <admin_token> in the Authorization header.
    """
    if not credentials or not credentials.credentials:
        from src.infrastructure.security.audit_logger import audit_logger
        audit_logger.log_security_event(
            event_type="MISSING_ADMIN_AUTHORIZATION",
            severity="HIGH",
            client_id="unknown",
            tenant_id="unknown",
            usuario="unauthenticated_admin",
            details={"endpoint": "admin_panel"},
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Se requiere token de administrador (Authorization: Bearer <token>).",
        )
    return default_jwt_handler.decode_admin_token(credentials.credentials)
