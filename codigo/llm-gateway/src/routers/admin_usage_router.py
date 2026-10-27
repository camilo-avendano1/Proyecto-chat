"""
Router for Usage Monitoring and Token Observability (LLM Gateway).
Endpoints:
- GET /api/v1/usage
- GET /api/v1/usage/by-user
- GET /api/v1/usage/by-tenant
- GET /api/v1/usage/by-role
- GET /api/v1/usage/by-model
- GET /api/v1/usage/records
Accessible by Administrators (SUPERADMIN, CLIENT_ADMIN) and Internal Services.
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from src.db.ledger_repo import LedgerRepository
from src.dependencies import get_db, require_admin_or_internal
from src.schemas import (
    ModelUsageResponse,
    RoleUsageResponse,
    TenantUsageResponse,
    UsageRecordItemResponse,
    UsageSummaryResponse,
    UserUsageResponse,
)

router = APIRouter(prefix="/api/v1/usage", tags=["Usage Observability & Tokens"])


def _resolve_effective_client(auth_ctx: Dict[str, Any], requested_client_id: Optional[str]) -> Optional[str]:
    # CLIENT_ADMIN is strictly locked to its own client_id
    if auth_ctx.get("role") == "CLIENT_ADMIN":
        return auth_ctx.get("client_id")
    return requested_client_id


@router.get(
    "",
    response_model=UsageSummaryResponse,
    status_code=status.HTTP_200_OK,
    summary="Resumen Global de Consumo de Tokens",
    description="Calcula el consolidado de tokens, costos y ahorro por fast-path."
)
async def get_usage_summary(
    tenant_id: Optional[str] = Query(None, description="Filtrar por Tenant"),
    usuario: Optional[str] = Query(None, description="Filtrar por Usuario"),
    client_id: Optional[str] = Query(None, description="Filtrar por Cliente"),
    auth_ctx: Dict[str, Any] = Depends(require_admin_or_internal),
    db: Session = Depends(get_db),
):
    effective_client = _resolve_effective_client(auth_ctx, client_id)
    repo = LedgerRepository(db)
    summary = repo.get_summary(client_id=effective_client, tenant_id=tenant_id, usuario=usuario)
    return UsageSummaryResponse(**summary)


@router.get(
    "/by-user",
    response_model=List[UserUsageResponse],
    status_code=status.HTTP_200_OK,
    summary="Consumo Agrupado por Usuario",
    description="Desglosa el consumo, llamadas LLM, fast-path y costos agrupados por usuario y rol."
)
async def get_usage_by_user(
    tenant_id: Optional[str] = Query(None, description="Filtrar por Tenant"),
    client_id: Optional[str] = Query(None, description="Filtrar por Cliente"),
    auth_ctx: Dict[str, Any] = Depends(require_admin_or_internal),
    db: Session = Depends(get_db),
):
    effective_client = _resolve_effective_client(auth_ctx, client_id)
    repo = LedgerRepository(db)
    rows = repo.get_by_user(client_id=effective_client, tenant_id=tenant_id)
    return [UserUsageResponse(**r) for r in rows]


@router.get(
    "/by-tenant",
    response_model=List[TenantUsageResponse],
    status_code=status.HTTP_200_OK,
    summary="Consumo Agrupado por Tenant",
    description="Permite auditar el gasto de tokens agrupado por entidad/filial."
)
async def get_usage_by_tenant(
    client_id: Optional[str] = Query(None, description="Filtrar por Cliente"),
    auth_ctx: Dict[str, Any] = Depends(require_admin_or_internal),
    db: Session = Depends(get_db),
):
    effective_client = _resolve_effective_client(auth_ctx, client_id)
    repo = LedgerRepository(db)
    rows = repo.get_by_tenant(client_id=effective_client)
    return [TenantUsageResponse(**r) for r in rows]


@router.get(
    "/by-role",
    response_model=List[RoleUsageResponse],
    status_code=status.HTTP_200_OK,
    summary="Consumo Agrupado por Rol Asistencial/Técnico",
    description="Segmenta el consumo por perfil: PERFIL_IPS_MEDICO, PERFIL_IPS_RADICADOR, etc."
)
async def get_usage_by_role(
    client_id: Optional[str] = Query(None, description="Filtrar por Cliente"),
    auth_ctx: Dict[str, Any] = Depends(require_admin_or_internal),
    db: Session = Depends(get_db),
):
    effective_client = _resolve_effective_client(auth_ctx, client_id)
    repo = LedgerRepository(db)
    rows = repo.get_by_role(client_id=effective_client)
    return [RoleUsageResponse(**r) for r in rows]


@router.get(
    "/by-model",
    response_model=List[ModelUsageResponse],
    status_code=status.HTTP_200_OK,
    summary="Consumo Agrupado por Modelo de IA",
    description="Muestra qué modelos fueron consultados y los costos asociados por cada motor de inferencia."
)
async def get_usage_by_model(
    client_id: Optional[str] = Query(None, description="Filtrar por Cliente"),
    auth_ctx: Dict[str, Any] = Depends(require_admin_or_internal),
    db: Session = Depends(get_db),
):
    effective_client = _resolve_effective_client(auth_ctx, client_id)
    repo = LedgerRepository(db)
    rows = repo.get_by_model(client_id=effective_client)
    return [ModelUsageResponse(**r) for r in rows]


@router.get(
    "/records",
    response_model=List[UsageRecordItemResponse],
    status_code=status.HTTP_200_OK,
    summary="Registros Detallados del Ledger",
    description="Listado paginado de llamadas al ledger de consumo."
)
async def get_usage_records(
    tenant_id: Optional[str] = Query(None, description="Filtrar por Tenant"),
    usuario: Optional[str] = Query(None, description="Filtrar por Usuario"),
    client_id: Optional[str] = Query(None, description="Filtrar por Cliente"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    auth_ctx: Dict[str, Any] = Depends(require_admin_or_internal),
    db: Session = Depends(get_db),
):
    effective_client = _resolve_effective_client(auth_ctx, client_id)
    repo = LedgerRepository(db)
    rows = repo.get_recent_records(
        client_id=effective_client,
        tenant_id=tenant_id,
        usuario=usuario,
        limit=limit,
        offset=offset,
    )
    return [UsageRecordItemResponse(**r) for r in rows]
