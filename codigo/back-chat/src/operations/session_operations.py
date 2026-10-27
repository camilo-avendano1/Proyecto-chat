"""
Session operations for widget initialization.
Validates public API keys, checks domain whitelists, resolves client routing, and issues signed session JWTs.
"""

from typing import Any, Optional
from src.domain.entities import WidgetSession
from src.domain.exceptions import (
    InvalidApiKeyException,
    TenantNotFoundException,
    UnauthorizedOriginException,
)
from src.infrastructure.security.audit_logger import audit_logger
from src.operations.interfaces import SessionRepositoryProtocol


class SessionOperations:
    """Manages secure session creation for embeddable chat widgets across clients."""

    def __init__(self, session_repo: SessionRepositoryProtocol, jwt_handler: Any = None):
        self.session_repo = session_repo
        self.jwt_handler = jwt_handler

    def create_session(
        self,
        api_key: str,
        origin: str,
        eps_id: str,
        ips_code: str,
        client_id: Optional[str] = "sigires",
        expires_in_seconds: int = 1800,
    ) -> WidgetSession:
        if not api_key:
            audit_logger.log_auth_failure(
                reason="MISSING_X_WIDGET_KEY",
                origin=origin,
                client_id=client_id or "unknown",
            )
            raise InvalidApiKeyException("Falta la cabecera obligatoria X-Widget-Key.")

        tenant = self.session_repo.get_tenant_by_key(api_key)
        if not tenant:
            audit_logger.log_auth_failure(
                reason="INVALID_OR_REVOKED_API_KEY",
                origin=origin,
                api_key_preview=api_key[:6] + "..." if len(api_key) > 6 else api_key,
                client_id=client_id or "unknown",
            )
            raise InvalidApiKeyException("La API Key suministrada no es válida o fue revocada.")

        # Determine effective client_id
        effective_client_id = tenant.client_id or client_id or "sigires"
        client = self.session_repo.get_client_by_id(effective_client_id)
        client_name = client.nombre if client else effective_client_id.upper()
        busqueda_api_url = client.busqueda_api_url if client else "http://localhost:8001"

        # Check domain whitelist
        if not tenant.is_origin_allowed(origin):
            audit_logger.log_security_event(
                event_type="UNAUTHORIZED_ORIGIN",
                severity="HIGH",
                client_id=effective_client_id,
                tenant_id=tenant.tenant_id,
                usuario="anonymous",
                details={
                    "origin": origin,
                    "tenant_name": tenant.nombre,
                    "allowed": tenant.dominios_permitidos,
                },
                ips_code=ips_code,
            )
            raise UnauthorizedOriginException(
                f"El dominio de origen '{origin}' no está autorizado en la lista blanca de '{tenant.nombre}'."
            )

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
            "origin": origin,
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
            expires_in_seconds=expires_in_seconds,
        )
