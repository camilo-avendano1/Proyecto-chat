"""
Session operations for widget initialization.
Validates public API keys, checks domain whitelists, resolves client routing, and issues signed session JWTs.
"""

import re
from typing import Any, Dict, Optional
from src.domain.entities import WidgetSession
from src.domain.exceptions import (
    InvalidApiKeyException,
    TenantNotFoundException,
    UnauthorizedOriginException,
)
from src.infrastructure.security.audit_logger import audit_logger
from src.operations.interfaces import SessionRepositoryProtocol

_METADATA_MAX_KEYS = 20
_METADATA_MAX_STR_LEN = 200
_METADATA_KEY_REGEX = re.compile(r"^[a-zA-Z0-9_.-]{1,64}$")


def _sanitize_metadata(
    metadata: Optional[Dict[str, Any]],
    eps_id: Optional[str] = None,
    ips_code: Optional[str] = None,
) -> Dict[str, Any]:
    """Sanitizes optional session metadata (max 20 safe keys, scalar values, strings <= 200 chars)."""
    raw: Dict[str, Any] = dict(metadata or {})
    if eps_id:
        raw.setdefault("eps_id", eps_id)
    if ips_code:
        raw.setdefault("ips_code", ips_code)

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
    """Manages secure session creation for embeddable chat widgets across clients."""

    def __init__(self, session_repo: SessionRepositoryProtocol, jwt_handler: Any = None):
        self.session_repo = session_repo
        self.jwt_handler = jwt_handler

    def create_session(
        self,
        api_key: str,
        origin: Optional[str] = None,
        client_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        eps_id: Optional[str] = None,
        ips_code: Optional[str] = None,
        expires_in_seconds: int = 1800,
    ) -> WidgetSession:
        effective_origin = origin or ""
        if not api_key:
            audit_logger.log_auth_failure(
                reason="MISSING_X_WIDGET_KEY",
                origin=effective_origin,
                client_id=client_id or "unknown",
            )
            raise InvalidApiKeyException("Falta la cabecera obligatoria X-Widget-Key.")

        tenant = self.session_repo.get_tenant_by_key(api_key)
        if not tenant:
            audit_logger.log_auth_failure(
                reason="INVALID_OR_REVOKED_API_KEY",
                origin=effective_origin,
                api_key_preview=api_key[:6] + "..." if len(api_key) > 6 else api_key,
                client_id=client_id or "unknown",
            )
            raise InvalidApiKeyException("La API Key suministrada no es válida o fue revocada.")

        # Determine effective client_id
        effective_client_id = tenant.client_id or client_id or "default"
        client = self.session_repo.get_client_by_id(effective_client_id)
        client_name = client.nombre if client else effective_client_id.upper()
        busqueda_api_url = client.busqueda_api_url if client else "http://localhost:8001"

        # Check domain whitelist
        if not tenant.is_origin_allowed(effective_origin):
            audit_logger.log_security_event(
                event_type="UNAUTHORIZED_ORIGIN",
                severity="HIGH",
                client_id=effective_client_id,
                tenant_id=tenant.tenant_id,
                usuario="anonymous",
                details={
                    "origin": effective_origin,
                    "tenant_name": tenant.nombre,
                    "allowed": tenant.dominios_permitidos,
                },
                ips_code=ips_code,
            )
            raise UnauthorizedOriginException(
                f"El dominio de origen '{effective_origin}' no está autorizado en la lista blanca de '{tenant.nombre}'."
            )

        merged_metadata = _sanitize_metadata(metadata, eps_id=eps_id, ips_code=ips_code)

        # Generate JWT session token containing client and search API routing
        payload = {
            "sub": tenant.tenant_id,
            "client_id": effective_client_id,
            "client_name": client_name,
            "busqueda_api_url": busqueda_api_url,
            "tenant_id": tenant.tenant_id,
            "tenant_name": tenant.nombre,
            "eps_id": eps_id,
            "ips_code": ips_code,
            "metadata": merged_metadata,
            "origin": effective_origin,
        }

        session_token = self.jwt_handler.create_session_token(
            data=payload,
            expires_delta_seconds=expires_in_seconds
        )

        return WidgetSession(
            session_token=session_token,
            client_id=effective_client_id,
            client_name=client_name,
            busqueda_api_url=busqueda_api_url,
            tenant_id=tenant.tenant_id,
            tenant_name=tenant.nombre,
            eps_id=eps_id,
            ips_code=ips_code,
            metadata=merged_metadata,
            expires_in_seconds=expires_in_seconds,
        )
