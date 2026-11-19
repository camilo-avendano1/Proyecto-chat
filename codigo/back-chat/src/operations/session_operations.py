"""
Session operations for widget initialization.
Validates public API keys, checks domain whitelists, resolves organization routing, and issues signed session JWTs.
"""

import re
from typing import Any, Dict, Optional
from src.domain.entities import WidgetSession
from src.domain.exceptions import (
    InvalidApiKeyException,
    SiteNotFoundException,
    UnauthorizedOriginException,
)
from src.infrastructure.security.audit_logger import audit_logger
from src.operations.interfaces import SessionRepositoryProtocol

_METADATA_MAX_KEYS = 20
_METADATA_MAX_STR_LEN = 200
_METADATA_KEY_REGEX = re.compile(r"^[a-zA-Z0-9_.-]{1,64}$")


def _sanitize_metadata(
    metadata: Optional[Dict[str, Any]],
    site_code: Optional[str] = None,
) -> Dict[str, Any]:
    """Sanitizes optional session metadata (max 20 safe keys, scalar values, strings <= 200 chars)."""
    raw: Dict[str, Any] = dict(metadata or {})
    if site_code:
        raw.setdefault("site_code", site_code)

    clean: Dict[str, Any] = {}
    for key, value in raw.items():
        if len(clean) >= _METADATA_MAX_KEYS:
            break
        if not isinstance(key, str) or not _METADATA_KEY_REGEX.match(key):
            continue
        if value is None or not isinstance(value, (str, int, float, bool)):
            continue
        clean[key] = value[:_METADATA_MAX_STR_LEN] if isinstance(value, str) else value
    return clean


class SessionOperations:
    """Manages secure session creation for embeddable chat widgets across organizations."""

    def __init__(self, session_repo: SessionRepositoryProtocol, jwt_handler: Any = None):
        self.session_repo = session_repo
        self.jwt_handler = jwt_handler

    def create_session(
        self,
        api_key: str,
        origin: Optional[str] = None,
        org_id: Optional[str] = None,
        site_code: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        expires_in_seconds: int = 1800,
    ) -> WidgetSession:
        effective_origin = origin or ""
        if not api_key:
            audit_logger.log_auth_failure(
                reason="MISSING_X_WIDGET_KEY",
                origin=effective_origin,
                org_id=org_id or "unknown",
            )
            raise InvalidApiKeyException("Falta la cabecera obligatoria X-Widget-Key.")

        site = self.session_repo.get_site_by_key(api_key)
        if not site:
            audit_logger.log_auth_failure(
                reason="INVALID_OR_REVOKED_API_KEY",
                origin=effective_origin,
                api_key_preview=api_key[:6] + "..." if len(api_key) > 6 else api_key,
                org_id=org_id or "unknown",
            )
            raise InvalidApiKeyException("La API Key suministrada no es válida o fue revocada.")

        # Determine effective organization
        effective_org_id = site.org_id or org_id or "default"
        org = self.session_repo.get_organization_by_id(effective_org_id)
        if org is None and org_id and not site.org_id:
            raise SiteNotFoundException(f"Organización '{org_id}' no encontrada.")

        org_name = org.nombre if org else effective_org_id.upper()
        busqueda_api_url = org.busqueda_api_url if org else "http://localhost:8001"
        site_label = org.site_label if org else "Sede"
        effective_site_code = site_code or site.site_code

        # Check domain whitelist
        if not site.is_origin_allowed(effective_origin):
            audit_logger.log_security_event(
                event_type="UNAUTHORIZED_ORIGIN",
                severity="HIGH",
                org_id=effective_org_id,
                site_id=site.site_id,
                usuario="anonymous",
                details={
                    "origin": effective_origin,
                    "site_name": site.nombre,
                    "allowed": site.dominios_permitidos,
                },
                site_code=effective_site_code,
            )
            raise UnauthorizedOriginException(
                f"El dominio de origen '{effective_origin}' no está autorizado en la lista blanca de '{site.nombre}'."
            )

        merged_metadata = _sanitize_metadata(metadata, site_code=site_code)

        # Generate JWT session token containing organization, site and search API routing
        payload = {
            "sub": site.site_id,
            "org_id": effective_org_id,
            "org_name": org_name,
            "busqueda_api_url": busqueda_api_url,
            "site_id": site.site_id,
            "site_name": site.nombre,
            "site_code": effective_site_code,
            "site_label": site_label,
            "metadata": merged_metadata,
            "origin": effective_origin,
        }

        session_token = self.jwt_handler.create_session_token(
            data=payload,
            expires_delta_seconds=expires_in_seconds,
        )

        return WidgetSession(
            session_token=session_token,
            org_id=effective_org_id,
            org_name=org_name,
            busqueda_api_url=busqueda_api_url,
            site_id=site.site_id,
            site_name=site.nombre,
            site_code=effective_site_code,
            site_label=site_label,
            metadata=merged_metadata,
            expires_in_seconds=expires_in_seconds,
        )
