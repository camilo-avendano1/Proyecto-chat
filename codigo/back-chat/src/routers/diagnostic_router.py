"""
Router for Diagnostic and Chat endpoints.
Endpoints:
- POST /api/v1/diagnostic/stream (Server-Sent Events streaming)
- POST /api/v1/diagnostic/query  (Synchronous JSON response)
Supports multi-client dynamic routing to the corresponding search backend.
"""

from typing import Any, Dict
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from src.infrastructure.external.busqueda_client import BusquedaHttpClient
from src.infrastructure.external.llm_gateway_client import LLMGatewayClient
from src.infrastructure.repositories.in_memory_ledger_repo import InMemoryLedgerRepository
from src.infrastructure.security.jwt_handler import get_current_session
from src.models.diagnostic import (
    DiagnosticQueryResponse,
    DiagnosticStreamRequest,
)
from src.operations.diagnostic_operations import DiagnosticOperations

router = APIRouter(prefix="/api/v1/diagnostic", tags=["Diagnóstico y Chat RAG"])

# Composition root dependencies
_search_client = BusquedaHttpClient()
_llm_client = LLMGatewayClient()
_ledger_repo = InMemoryLedgerRepository()
_diagnostic_ops = DiagnosticOperations(
    search_service=_search_client,
    llm_service=_llm_client,
    ledger_repo=_ledger_repo,
)


def get_diagnostic_operations() -> DiagnosticOperations:
    return _diagnostic_ops


def get_ledger_repository() -> InMemoryLedgerRepository:
    return _ledger_repo


@router.post(
    "/stream",
    summary="Consulta y Diagnóstico en Streaming (SSE)",
    description=(
        "Endpoint prioritario para el widget de chat embebido. "
        "Emite eventos Server-Sent Events (chunk, error_diagnostic, sources, done) "
        "con efecto de escritura en tiempo real."
    ),
    response_class=StreamingResponse,
)
async def stream_diagnostic(
    body: DiagnosticStreamRequest,
    session: Dict[str, Any] = Depends(get_current_session),
):
    tenant_id = session.get("tenant_id") or "tenant_default"
    client_id = session.get("client_id") or "sigires"
    client_name = session.get("client_name") or "SIGIRES"
    busqueda_api_url = session.get("busqueda_api_url")

    event_generator = _diagnostic_ops.execute_stream(
        request=body,
        tenant_id=tenant_id,
        client_id=client_id,
        busqueda_api_url=busqueda_api_url,
        client_name=client_name,
    )

    return StreamingResponse(
        event_generator,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@router.post(
    "/query",
    response_model=DiagnosticQueryResponse,
    status_code=status.HTTP_200_OK,
    summary="Consulta y Diagnóstico Síncrono (JSON)",
    description="Alternativa síncrona que retorna el diagnóstico consolidado, detalles del error y fuentes normativas.",
)
async def query_diagnostic(
    body: DiagnosticStreamRequest,
    session: Dict[str, Any] = Depends(get_current_session),
):
    tenant_id = session.get("tenant_id") or "tenant_default"
    client_id = session.get("client_id") or "sigires"
    client_name = session.get("client_name") or "SIGIRES"
    busqueda_api_url = session.get("busqueda_api_url")

    try:
        response = await _diagnostic_ops.execute_query(
            request=body,
            tenant_id=tenant_id,
            client_id=client_id,
            busqueda_api_url=busqueda_api_url,
            client_name=client_name,
        )
        return response
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al procesar el diagnóstico: {str(exc)}",
        )
