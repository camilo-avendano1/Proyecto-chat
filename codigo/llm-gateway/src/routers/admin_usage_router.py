"""
Router for Usage Monitoring and Token Observability (LLM Gateway).
Endpoints:
- GET /api/v1/usage
- GET /api/v1/usage/summary
- GET /api/v1/usage/by-user
- GET /api/v1/usage/by-site
- GET /api/v1/usage/by-role
- GET /api/v1/usage/by-model
- GET /api/v1/usage/timeseries
- GET /api/v1/usage/records
Accessible by Administrators (GLOBAL_ADMIN, ORG_ADMIN) and Internal Services.
"""

from typing import Any, Callable, Dict, List, Optional, TypeVar
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from src.db.ledger_repo import LedgerRepository
from src.dependencies import get_db, require_admin_or_internal
from src.schemas import (
    ModelUsageResponse,
    RoleUsageResponse,
    SiteUsageResponse,
    TimeseriesPointResponse,
    UsageRecordItemResponse,
    UsageSummaryResponse,
    UserUsageResponse,
)

router = APIRouter(prefix="/api/v1/usage", tags=["Usage Observability & Tokens"])

_T = TypeVar("_T")


def _resolve_effective_org(auth_ctx: Dict[str, Any], requested_org_id: Optional[str]) -> Optional[str]:
    # ORG_ADMIN is strictly locked to its own org_id
    if auth_ctx.get("role") == "ORG_ADMIN":
        return auth_ctx.get("org_id")
    return requested_org_id


def _execute_usage_query(query_fn: Callable[..., _T], **kwargs: Any) -> _T:
    try:
        return query_fn(**kwargs)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Parámetro de fecha inválido: {exc}",
        ) from exc


@router.get(
    "",
    response_model=UsageSummaryResponse,
    status_code=status.HTTP_200_OK,
    summary="Resumen Global de Consumo de Tokens",
    description="Calcula el consolidado de tokens, costos y ahorro por fast-path."
)
async def get_usage_summary(
    site_id: Optional[str] = Query(None, description="Filtrar por Sede"),
    usuario: Optional[str] = Query(None, description="Filtrar por Usuario"),
    org_id: Optional[str] = Query(None, description="Filtrar por Organización"),
    days: Optional[int] = Query(None, ge=1, le=365, description="Últimos N días"),
    date_from: Optional[str] = Query(None, description="Fecha inicio (YYYY-MM-DD o ISO-8601)"),
    date_to: Optional[str] = Query(None, description="Fecha fin (YYYY-MM-DD o ISO-8601)"),
    auth_ctx: Dict[str, Any] = Depends(require_admin_or_internal),
    db: Session = Depends(get_db),
):
    effective_org = _resolve_effective_org(auth_ctx, org_id)
    repo = LedgerRepository(db)
    summary = _execute_usage_query(
        repo.get_summary,
        org_id=effective_org,
        site_id=site_id,
        usuario=usuario,
        days=days,
        date_from=date_from,
        date_to=date_to,
    )
    return UsageSummaryResponse(**summary)


@router.get(
    "/summary",
    response_model=UsageSummaryResponse,
    status_code=status.HTTP_200_OK,
    summary="Resumen Global de Consumo de Tokens (Alias)",
    description="Alias de GET /api/v1/usage. Calcula el consolidado de tokens, costos y ahorro por fast-path."
)
async def get_usage_summary_alias(
    site_id: Optional[str] = Query(None, description="Filtrar por Sede"),
    usuario: Optional[str] = Query(None, description="Filtrar por Usuario"),
    org_id: Optional[str] = Query(None, description="Filtrar por Organización"),
    days: Optional[int] = Query(None, ge=1, le=365, description="Últimos N días"),
    date_from: Optional[str] = Query(None, description="Fecha inicio (YYYY-MM-DD o ISO-8601)"),
    date_to: Optional[str] = Query(None, description="Fecha fin (YYYY-MM-DD o ISO-8601)"),
    auth_ctx: Dict[str, Any] = Depends(require_admin_or_internal),
    db: Session = Depends(get_db),
):
    return await get_usage_summary(
        site_id=site_id,
        usuario=usuario,
        org_id=org_id,
        days=days,
        date_from=date_from,
        date_to=date_to,
        auth_ctx=auth_ctx,
        db=db,
    )


@router.get(
    "/by-user",
    response_model=List[UserUsageResponse],
    status_code=status.HTTP_200_OK,
    summary="Consumo Agrupado por Usuario",
    description="Desglosa el consumo, llamadas LLM, fast-path y costos agrupados por usuario y rol."
)
async def get_usage_by_user(
    site_id: Optional[str] = Query(None, description="Filtrar por Sede"),
    org_id: Optional[str] = Query(None, description="Filtrar por Organización"),
    days: Optional[int] = Query(None, ge=1, le=365, description="Últimos N días"),
    date_from: Optional[str] = Query(None, description="Fecha inicio (YYYY-MM-DD o ISO-8601)"),
    date_to: Optional[str] = Query(None, description="Fecha fin (YYYY-MM-DD o ISO-8601)"),
    auth_ctx: Dict[str, Any] = Depends(require_admin_or_internal),
    db: Session = Depends(get_db),
):
    effective_org = _resolve_effective_org(auth_ctx, org_id)
    repo = LedgerRepository(db)
    rows = _execute_usage_query(
        repo.get_by_user,
        org_id=effective_org,
        site_id=site_id,
        days=days,
        date_from=date_from,
        date_to=date_to,
    )
    return [UserUsageResponse(**r) for r in rows]


@router.get(
    "/by-site",
    response_model=List[SiteUsageResponse],
    status_code=status.HTTP_200_OK,
    summary="Consumo Agrupado por Sede",
    description="Permite auditar el gasto de tokens agrupado por sede o sitio."
)
async def get_usage_by_site(
    site_id: Optional[str] = Query(None, description="Filtrar por Sede"),
    org_id: Optional[str] = Query(None, description="Filtrar por Organización"),
    days: Optional[int] = Query(None, ge=1, le=365, description="Últimos N días"),
    date_from: Optional[str] = Query(None, description="Fecha inicio (YYYY-MM-DD o ISO-8601)"),
    date_to: Optional[str] = Query(None, description="Fecha fin (YYYY-MM-DD o ISO-8601)"),
    auth_ctx: Dict[str, Any] = Depends(require_admin_or_internal),
    db: Session = Depends(get_db),
):
    effective_org = _resolve_effective_org(auth_ctx, org_id)
    repo = LedgerRepository(db)
    rows = _execute_usage_query(
        repo.get_by_site,
        org_id=effective_org,
        site_id=site_id,
        days=days,
        date_from=date_from,
        date_to=date_to,
    )
    return [SiteUsageResponse(**r) for r in rows]


@router.get(
    "/by-role",
    response_model=List[RoleUsageResponse],
    status_code=status.HTTP_200_OK,
    summary="Consumo Agrupado por Rol",
    description="Segmenta el consumo de tokens y costos por rol o perfil de usuario de la organización."
)
async def get_usage_by_role(
    site_id: Optional[str] = Query(None, description="Filtrar por Sede"),
    org_id: Optional[str] = Query(None, description="Filtrar por Organización"),
    days: Optional[int] = Query(None, ge=1, le=365, description="Últimos N días"),
    date_from: Optional[str] = Query(None, description="Fecha inicio (YYYY-MM-DD o ISO-8601)"),
    date_to: Optional[str] = Query(None, description="Fecha fin (YYYY-MM-DD o ISO-8601)"),
    auth_ctx: Dict[str, Any] = Depends(require_admin_or_internal),
    db: Session = Depends(get_db),
):
    effective_org = _resolve_effective_org(auth_ctx, org_id)
    repo = LedgerRepository(db)
    rows = _execute_usage_query(
        repo.get_by_role,
        org_id=effective_org,
        site_id=site_id,
        days=days,
        date_from=date_from,
        date_to=date_to,
    )
    return [RoleUsageResponse(**r) for r in rows]


@router.get(
    "/by-model",
    response_model=List[ModelUsageResponse],
    status_code=status.HTTP_200_OK,
    summary="Consumo Agrupado por Modelo de IA",
    description="Muestra qué modelos fueron consultados y los costos asociados por cada motor de inferencia."
)
async def get_usage_by_model(
    site_id: Optional[str] = Query(None, description="Filtrar por Sede"),
    org_id: Optional[str] = Query(None, description="Filtrar por Organización"),
    days: Optional[int] = Query(None, ge=1, le=365, description="Últimos N días"),
    date_from: Optional[str] = Query(None, description="Fecha inicio (YYYY-MM-DD o ISO-8601)"),
    date_to: Optional[str] = Query(None, description="Fecha fin (YYYY-MM-DD o ISO-8601)"),
    auth_ctx: Dict[str, Any] = Depends(require_admin_or_internal),
    db: Session = Depends(get_db),
):
    effective_org = _resolve_effective_org(auth_ctx, org_id)
    repo = LedgerRepository(db)
    rows = _execute_usage_query(
        repo.get_by_model,
        org_id=effective_org,
        site_id=site_id,
        days=days,
        date_from=date_from,
        date_to=date_to,
    )
    return [ModelUsageResponse(**r) for r in rows]


@router.get(
    "/timeseries",
    response_model=List[TimeseriesPointResponse],
    status_code=status.HTTP_200_OK,
    summary="Serie Temporal Diaria de Consumo",
    description="Agrupa peticiones, tokens y costos por día en orden cronológico ascendente."
)
async def get_usage_timeseries(
    site_id: Optional[str] = Query(None, description="Filtrar por Sede"),
    org_id: Optional[str] = Query(None, description="Filtrar por Organización"),
    days: Optional[int] = Query(30, ge=1, le=365, description="Últimos N días"),
    date_from: Optional[str] = Query(None, description="Fecha inicio (YYYY-MM-DD o ISO-8601)"),
    date_to: Optional[str] = Query(None, description="Fecha fin (YYYY-MM-DD o ISO-8601)"),
    auth_ctx: Dict[str, Any] = Depends(require_admin_or_internal),
    db: Session = Depends(get_db),
):
    effective_org = _resolve_effective_org(auth_ctx, org_id)
    repo = LedgerRepository(db)
    rows = _execute_usage_query(
        repo.get_timeseries,
        org_id=effective_org,
        site_id=site_id,
        days=days,
        date_from=date_from,
        date_to=date_to,
    )
    return [TimeseriesPointResponse(**r) for r in rows]


@router.get(
    "/records",
    response_model=List[UsageRecordItemResponse],
    status_code=status.HTTP_200_OK,
    summary="Registros Detallados del Ledger",
    description="Listado paginado de llamadas al ledger de consumo."
)
async def get_usage_records(
    site_id: Optional[str] = Query(None, description="Filtrar por Sede"),
    usuario: Optional[str] = Query(None, description="Filtrar por Usuario"),
    org_id: Optional[str] = Query(None, description="Filtrar por Organización"),
    days: Optional[int] = Query(None, ge=1, le=365, description="Últimos N días"),
    date_from: Optional[str] = Query(None, description="Fecha inicio (YYYY-MM-DD o ISO-8601)"),
    date_to: Optional[str] = Query(None, description="Fecha fin (YYYY-MM-DD o ISO-8601)"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    auth_ctx: Dict[str, Any] = Depends(require_admin_or_internal),
    db: Session = Depends(get_db),
):
    effective_org = _resolve_effective_org(auth_ctx, org_id)
    repo = LedgerRepository(db)
    rows = _execute_usage_query(
        repo.get_recent_records,
        org_id=effective_org,
        site_id=site_id,
        usuario=usuario,
        limit=limit,
        offset=offset,
        days=days,
        date_from=date_from,
        date_to=date_to,
    )
    return [UsageRecordItemResponse(**r) for r in rows]
