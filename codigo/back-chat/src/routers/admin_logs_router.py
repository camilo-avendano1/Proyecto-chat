"""
Router for Administrator Observability: Security Audit Logs, Message Traces, and AI Usage.
Protected by get_current_admin with strict role isolation (SUPERADMIN vs CLIENT_ADMIN).
Developed by: Juan Camilo Avendaño, Fran Sneider Quincha, Adriana Moreno.
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
import httpx

from src.config import settings
from src.core.audit import audit_logger
from src.infrastructure.security.jwt_handler import get_current_admin

router = APIRouter(prefix="/api/v1/admin", tags=["Admin Observability & Logs"])


def _apply_role_scope(admin: Dict[str, Any], client_id: Optional[str]) -> Optional[str]:
    """
    Enforces tenant/client isolation:
    - SUPERADMIN can view any client_id or all.
    - CLIENT_ADMIN is strictly locked to its own client_id.
    """
    role = admin.get("role", "CLIENT_ADMIN")
    admin_client = admin.get("client_id")
    if role == "SUPERADMIN":
        return client_id
    if admin_client:
        return admin_client
    return client_id


@router.get(
    "/logs/security",
    summary="Auditoría Central de Seguridad (SQLite/PostgreSQL)",
    description="Consulta eventos de seguridad (bloqueos, fallos de auth, inyecciones) desde la base central de logs.",
)
async def get_security_logs(
    client_id: Optional[str] = Query(None, description="Filtrar por Empresa/Cliente"),
    tenant_id: Optional[str] = Query(None, description="Filtrar por División/Tenant"),
    usuario: Optional[str] = Query(None, description="Filtrar por Usuario"),
    event_type: Optional[str] = Query(None, description="Tipo de evento"),
    severity: Optional[str] = Query(None, description="Severidad: LOW, MEDIUM, HIGH, CRITICAL"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    admin: Dict[str, Any] = Depends(get_current_admin),
) -> Dict[str, Any]:
    scoped_client = _apply_role_scope(admin, client_id)

    filters: Dict[str, Any] = {}
    if scoped_client:
        filters["client_id"] = scoped_client
    if tenant_id:
        filters["tenant_id"] = tenant_id
    if usuario:
        filters["usuario"] = usuario
    if event_type:
        filters["event_type"] = event_type
    if severity:
        filters["severity"] = severity.upper()

    records = audit_logger.query("security_events", filters=filters, limit=limit, offset=offset)
    total = audit_logger.store.count("security_events", filters=filters) if audit_logger.store else len(records)

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "client_id_scoped": scoped_client,
        "records": records,
    }


@router.get(
    "/logs/messages",
    summary="Auditoría Central de Mensajes y Consultas",
    description="Consulta trazas de mensajes entrantes/salientes sanitizados desde la base central de logs.",
)
async def get_message_logs(
    client_id: Optional[str] = Query(None, description="Filtrar por Empresa/Cliente"),
    tenant_id: Optional[str] = Query(None, description="Filtrar por División/Tenant"),
    usuario: Optional[str] = Query(None, description="Filtrar por Usuario"),
    direction: Optional[str] = Query(None, description="INCOMING o OUTGOING"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    admin: Dict[str, Any] = Depends(get_current_admin),
) -> Dict[str, Any]:
    scoped_client = _apply_role_scope(admin, client_id)

    filters: Dict[str, Any] = {}
    if scoped_client:
        filters["client_id"] = scoped_client
    if tenant_id:
        filters["tenant_id"] = tenant_id
    if usuario:
        filters["usuario"] = usuario
    if direction:
        filters["direction"] = direction.upper()

    records = audit_logger.query("message_logs", filters=filters, limit=limit, offset=offset)
    total = audit_logger.store.count("message_logs", filters=filters) if audit_logger.store else len(records)

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "client_id_scoped": scoped_client,
        "records": records,
    }


@router.get(
    "/logs/system-errors",
    summary="Auditoría Central de Errores del Sistema",
    description="Consulta errores y excepciones operativas registradas en la base central de logs.",
)
async def get_system_error_logs(
    client_id: Optional[str] = Query(None),
    tenant_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    admin: Dict[str, Any] = Depends(get_current_admin),
) -> Dict[str, Any]:
    scoped_client = _apply_role_scope(admin, client_id)

    filters: Dict[str, Any] = {}
    if scoped_client:
        filters["client_id"] = scoped_client
    if tenant_id:
        filters["tenant_id"] = tenant_id

    records = audit_logger.query("system_errors", filters=filters, limit=limit, offset=offset)
    total = audit_logger.store.count("system_errors", filters=filters) if audit_logger.store else len(records)

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "records": records,
    }


# ---------------------------------------------------------------------------
# Proxy hacia el microservicio LLM Gateway (Puerto 8003) para Métricas de Uso
# ---------------------------------------------------------------------------

@router.get(
    "/usage/{subpath:path}",
    summary="Proxy de Métricas de Uso hacia LLM Gateway",
    description="Consulta métricas de consumo de modelos en el LLM Gateway con aislamiento multi-tenant.",
)
async def proxy_usage_to_gateway(
    subpath: str,
    client_id: Optional[str] = Query(None),
    tenant_id: Optional[str] = Query(None),
    usuario: Optional[str] = Query(None),
    rol: Optional[str] = Query(None),
    model: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    admin: Dict[str, Any] = Depends(get_current_admin),
) -> Any:
    scoped_client = _apply_role_scope(admin, client_id)

    params: Dict[str, Any] = {
        "limit": limit,
        "offset": offset,
    }
    if scoped_client:
        params["client_id"] = scoped_client
    if tenant_id:
        params["tenant_id"] = tenant_id
    if usuario:
        params["usuario"] = usuario
    if rol:
        params["rol"] = rol
    if model:
        params["model"] = model

    target_url = f"{settings.LLM_GATEWAY_URL.rstrip('/')}/api/v1/usage/{subpath}".rstrip("/")
    if not subpath:
        target_url = f"{settings.LLM_GATEWAY_URL.rstrip('/')}/api/v1/usage"

    # Forward user authorization to LLM Gateway
    headers = {
        "X-Internal-Key": settings.INTERNAL_SERVICE_KEY,
        "X-Admin-Role": admin.get("role", "CLIENT_ADMIN"),
        "X-Admin-Client-Id": admin.get("client_id", "") or "",
        "X-Admin-Username": admin.get("username", ""),
    }

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(target_url, params=params, headers=headers)
            if resp.status_code == 200:
                return resp.json()
            raise HTTPException(status_code=resp.status_code, detail=resp.text)
    except httpx.ConnectError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="El servicio LLM Gateway (puerto 8003) no se encuentra disponible.",
        )
