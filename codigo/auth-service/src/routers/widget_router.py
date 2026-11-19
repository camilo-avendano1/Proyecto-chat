"""
Router for Widget Session Handshake (auth-service).
Endpoint: POST /api/v1/widget/session
"""

from typing import Optional
from fastapi import APIRouter, Body, Depends, Header, HTTPException, Request, status
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
    description="Valida la API Key pública de la Sede/Organización, verifica la lista blanca de dominios y emite el JWT de sesión."
)
async def create_widget_session(
    request: Request,
    body: Optional[SessionCreateRequest] = Body(default=None),
    x_widget_key: str = Header(..., alias="X-Widget-Key", description="API Key pública de la Sede"),
    db: Session = Depends(get_db),
):
    ip = get_client_ip(
        x_forwarded_for=request.headers.get("x-forwarded-for"),
        x_real_ip=request.headers.get("x-real-ip"),
    )
    effective_origin = (body.origin if body and body.origin else None) or request.headers.get("origin") or ""
    service = WidgetSessionService(db)
    try:
        session = service.create_session(
            api_key=x_widget_key,
            origin=effective_origin,
            org_id=body.org_id if body else None,
            metadata=body.metadata if body else None,
            site_code=body.site_code if body else None,
            ip_address=ip,
        )
        return SessionResponse(
            session_token=session.session_token,
            org_id=session.org_id,
            org_name=session.org_name,
            site_id=session.site_id,
            site_name=session.site_name,
            site_code=session.site_code,
            site_label=session.site_label,
            expires_in_seconds=session.expires_in_seconds,
        )
    except AuthenticationError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=exc.detail)
    except ForbiddenError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=exc.detail)
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)
