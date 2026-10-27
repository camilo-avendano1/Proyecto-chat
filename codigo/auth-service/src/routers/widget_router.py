"""
Router for Widget Session Handshake (auth-service).
Endpoint: POST /api/v1/widget/session
Preserves 100% compatibility with existing widget integration contracts.
"""

from typing import Optional
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from src.core.exceptions import AuthenticationError, ForbiddenError, ServiceError
from src.dependencies import get_client_ip, get_db
from src.schemas import SessionCreateRequest, SessionResponse
from src.services.widget_session_service import WidgetSessionService

router = APIRouter(prefix="/api/v1/widget", tags=["Widget Authentication"])


@router.post(
    "/session",
    response_model=SessionResponse,
    status_code=status.HTTP_200_OK,
    summary="Inicializar Sesión Segura del Widget",
    description="Valida la API Key pública del Tenant/Empresa, verifica la lista blanca de dominios y emite el JWT de sesión."
)
async def create_widget_session(
    body: SessionCreateRequest,
    request: Request,
    x_widget_key: str = Header(..., alias="X-Widget-Key", description="API Key pública del Tenant o Empresa"),
    db: Session = Depends(get_db),
):
    ip = get_client_ip(
        x_forwarded_for=request.headers.get("x-forwarded-for"),
        x_real_ip=request.headers.get("x-real-ip"),
    )
    service = WidgetSessionService(db)
    try:
        session = service.create_session(
            api_key=x_widget_key,
            origin=body.origin,
            eps_id=body.eps_id,
            ips_code=body.ips_code,
            client_id=body.client_id,
            ip_address=ip,
        )
        return SessionResponse(
            session_token=session.session_token,
            client_id=session.client_id,
            client_name=session.client_name,
            tenant_id=session.tenant_id,
            tenant_name=session.tenant_name,
            expires_in_seconds=session.expires_in_seconds,
        )
    except AuthenticationError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=exc.detail)
    except ForbiddenError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=exc.detail)
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)
