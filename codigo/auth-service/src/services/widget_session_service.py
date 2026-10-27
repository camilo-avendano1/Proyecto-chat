"""
Autenticación de usuarios finales del widget (handshake).
Valida la API Key pública del tenant, la lista blanca de dominios y emite el JWT de sesión.
"""

from dataclasses import dataclass
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.config import settings
from src.core.audit import audit_logger
from src.core.exceptions import AuthenticationError, ForbiddenError
from src.core.security import api_key_preview, hash_api_key, issue_widget_token
from src.db.database import ClientORM, TenantORM


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
        origin: str,
        eps_id: str,
        ips_code: str,
        client_id: Optional[str] = "sigires",
        ip_address: Optional[str] = None,
    ) -> WidgetSession:
        if not api_key:
            audit_logger.log_auth_failure(
                reason="MISSING_X_WIDGET_KEY", origin=origin, ip_address=ip_address, client_id=client_id or "unknown"
            )
            raise AuthenticationError("Falta la cabecera obligatoria X-Widget-Key.")

        tenant = self.db.scalar(select(TenantORM).where(TenantORM.api_key_hash == hash_api_key(api_key)))
        if not tenant or tenant.status != "ACTIVE":
            audit_logger.log_auth_failure(
                reason="INVALID_OR_REVOKED_API_KEY",
                origin=origin,
                api_key_preview=api_key_preview(api_key),
                ip_address=ip_address,
                client_id=client_id or "unknown",
            )
            raise AuthenticationError("La API Key suministrada no es válida o fue revocada.")

        client = self.db.get(ClientORM, tenant.client_id)
        if not client or client.status != "ACTIVE":
            audit_logger.log_auth_failure(
                reason="CLIENT_INACTIVE",
                origin=origin,
                ip_address=ip_address,
                client_id=tenant.client_id,
                tenant_id=tenant.tenant_id,
            )
            raise AuthenticationError("La empresa cliente asociada no está activa.")

        if not tenant.is_origin_allowed(origin):
            audit_logger.log_security_event(
                event_type="UNAUTHORIZED_ORIGIN",
                severity="HIGH",
                client_id=client.client_id,
                tenant_id=tenant.tenant_id,
                usuario="anonymous",
                details={"origin": origin, "tenant_name": tenant.nombre, "allowed": tenant.dominios_permitidos},
                ips_code=ips_code,
                ip_address=ip_address,
            )
            raise ForbiddenError(
                f"El dominio de origen '{origin}' no está autorizado en la lista blanca de '{tenant.nombre}'."
            )

        expires = settings.SESSION_EXPIRES_SECONDS
        token = issue_widget_token(
            {
                "sub": tenant.tenant_id,
                "client_id": client.client_id,
                "client_name": client.nombre,
                "busqueda_api_url": client.busqueda_api_url,
                "tenant_id": tenant.tenant_id,
                "tenant_name": tenant.nombre,
                "eps_id": eps_id,
                "ips_code": ips_code,
                "origin": origin,
            },
            expires_seconds=expires,
        )

        audit_logger.log_security_event(
            event_type="WIDGET_SESSION_CREATED",
            severity="LOW",
            client_id=client.client_id,
            tenant_id=tenant.tenant_id,
            usuario="widget",
            details={"origin": origin, "eps_id": eps_id},
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
