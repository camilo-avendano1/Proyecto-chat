"""
Router for Widget Session Management.
Endpoint: POST /api/v1/widget/session
Supports multi-client identification and division/tenant mapping.
"""

from fastapi import APIRouter, Header, HTTPException, status

import httpx
from src.config import settings
from src.domain.exceptions import (
    InvalidApiKeyException,
    TenantNotFoundException,
    UnauthorizedOriginException,
)
from src.infrastructure.repositories.in_memory_session_repo import InMemorySessionRepository
from src.infrastructure.security.jwt_handler import default_jwt_handler
from src.models.session import SessionCreateRequest, SessionResponse
from src.operations.session_operations import SessionOperations

router = APIRouter(prefix="/api/v1/widget", tags=["Widget Session"])

# Composition root dependencies (Fallback local)
_session_repo = InMemorySessionRepository()
_session_ops = SessionOperations(session_repo=_session_repo, jwt_handler=default_jwt_handler)


def get_session_operations() -> SessionOperations:
    return _session_ops


@router.post(
    "/session",
    response_model=SessionResponse,
    status_code=status.HTTP_200_OK,
    summary="Inicializar Sesión Segura del Widget",
    description="Valida la API Key pública delegando en auth-service (puerto 8002) con respaldo local."
)
async def create_widget_session(
    body: SessionCreateRequest,
    x_widget_key: str = Header(..., alias="X-Widget-Key", description="API Key pública del Tenant o Empresa"),
):
    # 1. Intentar delegar a auth-service si está configurado y no estamos en entorno de testing
    if settings.AUTH_SERVICE_URL and settings.ENVIRONMENT != "testing":
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.post(
                    f"{settings.AUTH_SERVICE_URL.rstrip('/')}/api/v1/widget/session",
                    headers={"X-Widget-Key": x_widget_key, "Content-Type": "application/json"},
                    json=body.model_dump(exclude_unset=True),
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return SessionResponse(**data)
                elif resp.status_code in (400, 401, 403, 404, 422):
                    detail = resp.json().get("detail", "Error en autenticación")
                    raise HTTPException(status_code=resp.status_code, detail=detail)
        except HTTPException:
            raise
        except (httpx.ConnectError, httpx.TimeoutException):
            pass  # Fallback a motor local

    # 2. Respaldo local si auth-service no está corriendo
    try:
        session = _session_ops.create_session(
            api_key=x_widget_key,
            origin=body.origin,
            eps_id=body.eps_id,
            ips_code=body.ips_code,
            client_id=body.client_id,
        )
        return SessionResponse(
            session_token=session.session_token,
            client_id=session.client_id,
            client_name=session.client_name,
            tenant_id=session.tenant_id,
            tenant_name=session.tenant_name,
            expires_in_seconds=session.expires_in_seconds,
        )
    except InvalidApiKeyException as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )
    except UnauthorizedOriginException as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )
    except TenantNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
