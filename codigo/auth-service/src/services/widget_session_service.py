"""
Autenticación de usuarios finales del widget (handshake).
Valida la API Key pública de la sede, la lista blanca de dominios y emite el JWT de sesión.
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
from src.db.database import OrganizationORM, SiteORM

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
    org_id: str
    org_name: str
    site_id: str
    site_name: str
    site_code: str
    site_label: str
    expires_in_seconds: int


class WidgetSessionService:
    def __init__(self, db: Session):
        self.db = db

    def create_session(
        self,
        api_key: str,
        origin: Optional[str] = None,
        org_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        site_code: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> WidgetSession:
        effective_origin = origin or ""

        if not api_key:
            audit_logger.log_auth_failure(
                reason="MISSING_X_WIDGET_KEY",
                origin=effective_origin,
                ip_address=ip_address,
                org_id=org_id or "unknown",
            )
            raise AuthenticationError("Falta la cabecera obligatoria X-Widget-Key.")

        site = self.db.scalar(select(SiteORM).where(SiteORM.api_key_hash == hash_api_key(api_key)))
        if not site or site.status != "ACTIVE":
            audit_logger.log_auth_failure(
                reason="INVALID_OR_REVOKED_API_KEY",
                origin=effective_origin,
                api_key_preview=api_key_preview(api_key),
                ip_address=ip_address,
                org_id=org_id or "unknown",
            )
            raise AuthenticationError("La API Key suministrada no es válida o fue revocada.")

        org = self.db.get(OrganizationORM, site.org_id)
        if not org or org.status != "ACTIVE":
            audit_logger.log_auth_failure(
                reason="ORGANIZATION_INACTIVE",
                origin=effective_origin,
                ip_address=ip_address,
                org_id=site.org_id,
                site_id=site.site_id,
            )
            raise AuthenticationError("La organización asociada no está activa.")

        effective_site_code = (
            site_code.strip() if isinstance(site_code, str) and site_code.strip() else None
        )

        if not site.is_origin_allowed(effective_origin):
            audit_logger.log_security_event(
                event_type="UNAUTHORIZED_ORIGIN",
                severity="HIGH",
                org_id=org.org_id,
                site_id=site.site_id,
                usuario="anonymous",
                details={"origin": effective_origin, "site_name": site.nombre, "allowed": site.dominios_permitidos},
                site_code=effective_site_code or site.site_code,
                ip_address=ip_address,
            )
            raise ForbiddenError(
                f"El dominio de origen '{effective_origin}' no está autorizado en la lista blanca de '{site.nombre}'."
            )

        merged_metadata = _sanitize_metadata(metadata)
        if effective_site_code and "site_code" not in merged_metadata:
            merged_metadata["site_code"] = effective_site_code[:_MAX_METADATA_STR_LEN]

        expires = settings.SESSION_EXPIRES_SECONDS
        token = issue_widget_token(
            {
                "sub": site.site_id,
                "org_id": org.org_id,
                "org_name": org.nombre,
                "busqueda_api_url": org.busqueda_api_url,
                "site_id": site.site_id,
                "site_name": site.nombre,
                "site_code": site.site_code,
                "site_label": org.site_label,
                "metadata": merged_metadata,
                "origin": effective_origin,
            },
            expires_seconds=expires,
        )

        audit_logger.log_security_event(
            event_type="WIDGET_SESSION_CREATED",
            severity="LOW",
            org_id=org.org_id,
            site_id=site.site_id,
            usuario="widget",
            details={
                "origin": effective_origin,
                "site_code": site.site_code,
                "request_site_code": effective_site_code,
                "has_metadata": bool(merged_metadata),
            },
            site_code=site.site_code,
            ip_address=ip_address,
        )

        return WidgetSession(
            session_token=token,
            org_id=org.org_id,
            org_name=org.nombre,
            site_id=site.site_id,
            site_name=site.nombre,
            site_code=site.site_code,
            site_label=org.site_label,
            expires_in_seconds=expires,
        )
