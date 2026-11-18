"""
Autenticación de usuarios finales del widget (handshake).
Valida la API Key pública del tenant, la lista blanca de dominios y emite el JWT de sesión.
"""

from dataclasses import dataclass
import re
from typing import Any, Dict, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.config import settings
from src.core.audit import audit_logger
from src.core.exceptions import AuthenticationError, ForbiddenError
from src.core.security import api_key_preview, hash_api_key, issue_widget_token
from src.db.database import ClientORM, TenantORM

_METADATA_KEY_RE = re.compile(r"^[a-zA-Z0-9_.-]{1,64}\Z")
_MAX_METADATA_KEYS = 20
_MAX_METADATA_STR_LEN = 200


def _sanitize_metadata(metadata: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Valida y normaliza metadatos de sesión (máx. 20 claves válidas y valores escalares)."""
    if not metadata or not isinstance(metadata, dict):
        return {}
    sanitized: Dict[str, Any] = {}
    for key, value in metadata.items():
        if len(sanitized) >= _MAX_METADATA_KEYS:
            break
        if not isinstance(key, str) or not _METADATA_KEY_RE.match(key):
            continue
        if value is None or not isinstance(value, (str, int, float, bool)):
            continue
        sanitized[key] = value[:_MAX_METADATA_STR_LEN] if isinstance(value, str) else value
    return sanitized


@dataclass
class WidgetSession:
    session_token: str
    client_id: str
    client_name: str
    tenant_id: str
    tenant_name: str
    expires_in_seconds: int


class WidgetSessionService:
    def __init__(self, db: Session):
        self.db = db

    def create_session(
        self,
        api_key: str,
        origin: Optional[str] = None,
        client_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        eps_id: Optional[str] = None,
        ips_code: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> WidgetSession:
        effective_origin = origin or ""

        if not api_key:
            audit_logger.log_auth_failure(
                reason="MISSING_X_WIDGET_KEY",
                origin=effective_origin,
                ip_address=ip_address,
                client_id=client_id or "unknown",
            )
            raise AuthenticationError("Falta la cabecera obligatoria X-Widget-Key.")

        tenant = self.db.scalar(select(TenantORM).where(TenantORM.api_key_hash == hash_api_key(api_key)))
        if not tenant or tenant.status != "ACTIVE":
            audit_logger.log_auth_failure(
                reason="INVALID_OR_REVOKED_API_KEY",
                origin=effective_origin,
                api_key_preview=api_key_preview(api_key),
                ip_address=ip_address,
                client_id=client_id or "unknown",
            )
            raise AuthenticationError("La API Key suministrada no es válida o fue revocada.")

        client = self.db.get(ClientORM, tenant.client_id)
        if not client or client.status != "ACTIVE":
            audit_logger.log_auth_failure(
                reason="CLIENT_INACTIVE",
                origin=effective_origin,
                ip_address=ip_address,
                client_id=tenant.client_id,
                tenant_id=tenant.tenant_id,
            )
            raise AuthenticationError("La empresa cliente asociada no está activa.")

        if not tenant.is_origin_allowed(effective_origin):
            audit_logger.log_security_event(
                event_type="UNAUTHORIZED_ORIGIN",
                severity="HIGH",
                client_id=client.client_id,
                tenant_id=tenant.tenant_id,
                usuario="anonymous",
                details={"origin": effective_origin, "tenant_name": tenant.nombre, "allowed": tenant.dominios_permitidos},
                ips_code=ips_code,
                ip_address=ip_address,
            )
            raise ForbiddenError(
                f"El dominio de origen '{effective_origin}' no está autorizado en la lista blanca de '{tenant.nombre}'."
            )

        merged_metadata = _sanitize_metadata(metadata)
        if eps_id and "eps_id" not in merged_metadata:
            merged_metadata["eps_id"] = str(eps_id)[:_MAX_METADATA_STR_LEN]
        if ips_code and "ips_code" not in merged_metadata:
            merged_metadata["ips_code"] = str(ips_code)[:_MAX_METADATA_STR_LEN]

        expires = settings.SESSION_EXPIRES_SECONDS
        token = issue_widget_token(
            {
                "sub": tenant.tenant_id,
                "client_id": client.client_id,
                "client_name": client.nombre,
                "busqueda_api_url": client.busqueda_api_url,
                "tenant_id": tenant.tenant_id,
                "tenant_name": tenant.nombre,
                "metadata": merged_metadata,
                "eps_id": eps_id,
                "ips_code": ips_code,
                "origin": effective_origin,
            },
            expires_seconds=expires,
        )

        audit_logger.log_security_event(
            event_type="WIDGET_SESSION_CREATED",
            severity="LOW",
            client_id=client.client_id,
            tenant_id=tenant.tenant_id,
            usuario="widget",
            details={"origin": effective_origin, "eps_id": eps_id, "has_metadata": bool(merged_metadata)},
            ips_code=ips_code,
            ip_address=ip_address,
        )

        return WidgetSession(
            session_token=token,
            client_id=client.client_id,
            client_name=client.nombre,
            tenant_id=tenant.tenant_id,
            tenant_name=tenant.nombre,
            expires_in_seconds=expires,
        )
