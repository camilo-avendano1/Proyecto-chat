"""
Primitivas de seguridad del Auth Service:
- Hash SHA-256 de API Keys públicas del widget (nunca se guardan en claro).
- Hash bcrypt de contraseñas de administradores.
- Emisión y verificación de JWT (audiencias separadas: widget vs admin).
"""

from datetime import datetime, timedelta, timezone
import hashlib
import hmac
from typing import Any, Dict
import uuid

import bcrypt
import jwt

from src.config import settings

BCRYPT_MAX_BYTES = 72
ROLE_SUPERADMIN = "SUPERADMIN"
ROLE_CLIENT_ADMIN = "CLIENT_ADMIN"
VALID_ROLES = (ROLE_SUPERADMIN, ROLE_CLIENT_ADMIN)


def hash_api_key(api_key: str) -> str:
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()


def api_key_preview(api_key: str) -> str:
    return api_key[:8] + "..." if len(api_key) > 8 else "***"


def constant_time_equals(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


# Hash ficticio para igualar el tiempo de respuesta cuando el usuario no existe
DUMMY_PASSWORD_HASH = hash_password("dummy-password-for-timing-safety")


def validate_password_strength(password: str) -> None:
    """Política mínima: 10+ caracteres, letras y números, máximo 72 bytes (límite bcrypt)."""
    if len(password) < 10:
        raise ValueError("La contraseña debe tener al menos 10 caracteres.")
    if len(password.encode("utf-8")) > BCRYPT_MAX_BYTES:
        raise ValueError("La contraseña no puede superar 72 bytes.")
    if not any(c.isalpha() for c in password) or not any(c.isdigit() for c in password):
        raise ValueError("La contraseña debe combinar letras y números.")


def _encode(claims: Dict[str, Any], secret: str, audience: str, expires_seconds: int, token_type: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        **claims,
        "iss": settings.JWT_ISSUER,
        "aud": audience,
        "typ": token_type,
        "iat": now,
        "nbf": now,
        "exp": now + timedelta(seconds=expires_seconds),
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, secret, algorithm=settings.JWT_ALGORITHM)


def issue_widget_token(claims: Dict[str, Any], expires_seconds: int) -> str:
    return _encode(claims, settings.WIDGET_JWT_SECRET, settings.WIDGET_TOKEN_AUDIENCE, expires_seconds, "widget")


def issue_admin_token(claims: Dict[str, Any], expires_seconds: int) -> str:
    return _encode(claims, settings.ADMIN_JWT_SECRET, settings.ADMIN_TOKEN_AUDIENCE, expires_seconds, "admin")


def decode_admin_token(token: str) -> Dict[str, Any]:
    """Lanza jwt.PyJWTError si el token es inválido, expiró o no es de tipo admin."""
    payload = jwt.decode(
        token,
        settings.ADMIN_JWT_SECRET,
        algorithms=[settings.JWT_ALGORITHM],
        audience=settings.ADMIN_TOKEN_AUDIENCE,
        issuer=settings.JWT_ISSUER,
        options={"require": ["exp", "iat", "sub", "aud", "iss"]},
    )
    if payload.get("typ") != "admin":
        raise jwt.InvalidTokenError("Tipo de token incorrecto")
    return payload
