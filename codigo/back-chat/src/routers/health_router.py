"""
Router for Healthchecks, System Status, Usage Observability, and Security Logs.
Developed by: Juan Camilo Avendaño, Fran Sneider Quincha, Adriana Moreno.
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Query, status
import httpx

from src.config import settings
from src.infrastructure.security.audit_logger import audit_logger
from src.models.diagnostic import (
    MessageLogItemResponse,
    SecurityEventItemResponse,
    StatusResponse,
    TenantUsageResponse,
    UsageSummaryResponse,
    UserUsageResponse,
)
from src.routers.diagnostic_router import get_ledger_repository

router = APIRouter(tags=["Health, Observability & Security"])


@router.get(
    "/health",
    status_code=status.HTTP_200_OK,
    summary="Liveness Health Check",
    description="Endpoint rápido para balanceadores de carga y Google Cloud Run.",
)
async def health_check() -> Dict[str, str]:
    return {"status": "ok"}


@router.get(
    "/api/v1/status",
    response_model=StatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Estado de Componentes y Conectividad",
    description="Verifica el estado del Back Central, conectividad con Back - Busqueda y modo LLM.",
)
async def system_status() -> StatusResponse:
    # Check default Back - Busqueda connectivity
    default_busqueda_url = settings.CLIENT_BUSQUEDA_URLS.get("sigires", "http://localhost:8001")
    busqueda_status = "unreachable (using local fallback)"
    try:
        async with httpx.AsyncClient(timeout=1.5) as client:
            resp = await client.get(f"{default_busqueda_url}/health")
            if resp.status_code == 200:
                busqueda_status = "connected"
    except Exception:
        pass

    auth_service_status = "offline"
    if settings.AUTH_SERVICE_URL:
        try:
            async with httpx.AsyncClient(timeout=1.5) as client:
                resp = await client.get(f"{settings.AUTH_SERVICE_URL.rstrip('/')}/health")
                if resp.status_code == 200:
                    auth_service_status = "connected"
        except Exception:
            pass

    llm_gateway_status = "offline (using local fallback simulation)"
    if settings.LLM_GATEWAY_URL:
        try:
            async with httpx.AsyncClient(timeout=1.5) as client:
                resp = await client.get(f"{settings.LLM_GATEWAY_URL.rstrip('/')}/health")
                if resp.status_code == 200:
                    llm_gateway_status = "connected"
        except Exception:
            pass

    llm_status = f"active ({settings.LLM_PROVIDER})"
    if settings.LLM_PROVIDER == "lmstudio":
        llm_status = "active (LM Studio Local Server)"
    elif settings.LLM_PROVIDER == "ollama":
        llm_status = "active (Ollama Local Server)"

    return StatusResponse(
        status="healthy",
        app_name=settings.APP_NAME,
        version=settings.APP_VERSION,
        environment=settings.ENVIRONMENT,
        authors=settings.AUTHORS,
        llm_provider=settings.LLM_PROVIDER,
        llm_model=settings.LLM_MODEL,
        llm_base_url=settings.LLM_BASE_URL,
        back_busqueda_status=busqueda_status,
        llm_service_status=llm_status,
        auth_service_status=auth_service_status,
        llm_gateway_status=llm_gateway_status,
    )


@router.get(
    "/api/v1/usage",
    response_model=UsageSummaryResponse,
    status_code=status.HTTP_200_OK,
    summary="Resumen de Consumo de Tokens (Ledger)",
    description="Muestra el total de tokens procesados y costos acumulados, filtrable por tenant, usuario y cliente.",
)
async def get_usage_metrics(
    tenant_id: Optional[str] = Query(None, description="Filtrar métricas por ID del Tenant"),
    usuario: Optional[str] = Query(None, description="Filtrar métricas por nombre de usuario"),
    client_id: Optional[str] = Query(None, description="Filtrar métricas por cliente"),
) -> UsageSummaryResponse:
    ledger_repo = get_ledger_repository()
    summary = await ledger_repo.get_usage_summary(
        tenant_id=tenant_id,
        client_id=client_id,
        usuario=usuario,
    )
    return UsageSummaryResponse(
        total_records=summary.get("total_records", 0),
        total_tokens_input=summary.get("total_tokens_input", 0),
        total_tokens_output=summary.get("total_tokens_output", 0),
        total_tokens=summary.get("total_tokens", 0),
        total_cost_usd=summary.get("total_cost_usd", 0.0),
        saved_fast_path_calls=summary.get("saved_fast_path_calls", 0),
    )


@router.get(
    "/api/v1/usage/by-user",
    response_model=List[UserUsageResponse],
    status_code=status.HTTP_200_OK,
    summary="Desglose de Consumo de Tokens por Usuario",
    description="Permite auditar el gasto de tokens, llamadas al LLM y ahorro por fast-path agrupado por usuario.",
)
async def get_usage_by_user(
    tenant_id: Optional[str] = Query(None, description="Filtrar por Tenant específico"),
    client_id: Optional[str] = Query(None, description="Filtrar por Cliente específico"),
) -> List[UserUsageResponse]:
    ledger_repo = get_ledger_repository()
    users_data = await ledger_repo.get_usage_by_user(tenant_id=tenant_id, client_id=client_id)
    return [UserUsageResponse(**u) for u in users_data]


@router.get(
    "/api/v1/usage/by-tenant",
    response_model=List[TenantUsageResponse],
    status_code=status.HTTP_200_OK,
    summary="Desglose de Consumo de Tokens por Tenant",
    description="Permite auditar el gasto de tokens y facturación multi-tenant para cobro o cuotas.",
)
async def get_usage_by_tenant(
    client_id: Optional[str] = Query(None, description="Filtrar por Cliente específico"),
) -> List[TenantUsageResponse]:
    ledger_repo = get_ledger_repository()
    tenants_data = await ledger_repo.get_usage_by_tenant(client_id=client_id)
    return [TenantUsageResponse(**t) for t in tenants_data]


@router.get(
    "/api/v1/usage/security-logs",
    response_model=List[SecurityEventItemResponse],
    status_code=status.HTTP_200_OK,
    summary="Auditoría de Logs de Seguridad",
    description="Consulta eventos de seguridad registrados: intentos de inyección, orígenes no autorizados y fallos de autenticación.",
)
async def get_security_audit_logs(
    tenant_id: Optional[str] = Query(None, description="Filtrar por Tenant"),
    usuario: Optional[str] = Query(None, description="Filtrar por Usuario"),
    event_type: Optional[str] = Query(None, description="Tipo de evento de seguridad"),
    limit: int = Query(50, ge=1, le=500, description="Límite de registros a retornar"),
) -> List[SecurityEventItemResponse]:
    events = audit_logger.get_recent_security_events(
        limit=limit,
        tenant_id=tenant_id,
        usuario=usuario,
        event_type=event_type,
    )
    return [SecurityEventItemResponse(**e) for e in events]


@router.get(
    "/api/v1/usage/message-logs",
    response_model=List[MessageLogItemResponse],
    status_code=status.HTTP_200_OK,
    summary="Auditoría de Entrada y Salida de Mensajes",
    description="Historial detallado de mensajes entrantes y salientes sanitizados con métricas de tokens y latencia.",
)
async def get_message_audit_logs(
    tenant_id: Optional[str] = Query(None, description="Filtrar por Tenant"),
    usuario: Optional[str] = Query(None, description="Filtrar por Usuario"),
    direction: Optional[str] = Query(None, description="Dirección: INCOMING o OUTGOING"),
    limit: int = Query(50, ge=1, le=500, description="Límite de registros a retornar"),
) -> List[MessageLogItemResponse]:
    logs = audit_logger.get_recent_message_logs(
        limit=limit,
        tenant_id=tenant_id,
        usuario=usuario,
        direction=direction,
    )
    return [MessageLogItemResponse(**m) for m in logs]
