"""
Router for Chat and Diagnostic endpoints.
Endpoints:
- POST /api/v1/chat/stream       (Server-Sent Events streaming - primary generic endpoint)
- POST /api/v1/chat/query        (Synchronous JSON response - primary generic endpoint)
- POST /api/v1/diagnostic/stream (Legacy compatible SSE alias)
- POST /api/v1/diagnostic/query  (Legacy compatible JSON alias)
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
    ChatQueryResponse,
    ChatRequest,
)
from src.operations.diagnostic_operations import DiagnosticOperations

router = APIRouter(prefix="/api/v1/diagnostic", tags=["Diagnóstico y Chat RAG"])
chat_router = APIRouter(prefix="/api/v1/chat", tags=["Chat RAG Multi-Cliente"])

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


def _extract_session_context(session: Dict[str, Any]) -> Dict[str, Any]:
    raw_metadata = session.get("metadata")
    return {
        "tenant_id": session.get("tenant_id") or "tenant_default",
        "client_id": session.get("client_id") or "default",
        "client_name": session.get("client_name") or "la Plataforma",
        "busqueda_api_url": session.get("busqueda_api_url"),
        "session_metadata": raw_metadata if isinstance(raw_metadata, dict) else None,
        "session_org_code": session.get("ips_code"),
    }


async def _handle_stream(body: ChatRequest, session: Dict[str, Any]) -> StreamingResponse:
    ctx = _extract_session_context(session)
    event_generator = _diagnostic_ops.execute_stream(
        request=body,
        tenant_id=ctx["tenant_id"],
        client_id=ctx["client_id"],
        busqueda_api_url=ctx["busqueda_api_url"],
        client_name=ctx["client_name"],
        session_metadata=ctx["session_metadata"],
        session_org_code=ctx["session_org_code"],
    )
    return StreamingResponse(
        event_generator,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


async def _handle_query(body: ChatRequest, session: Dict[str, Any]) -> ChatQueryResponse:
    ctx = _extract_session_context(session)
    try:
        return await _diagnostic_ops.execute_query(
            request=body,
            tenant_id=ctx["tenant_id"],
            client_id=ctx["client_id"],
            busqueda_api_url=ctx["busqueda_api_url"],
            client_name=ctx["client_name"],
            session_metadata=ctx["session_metadata"],
            session_org_code=ctx["session_org_code"],
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al procesar la consulta: {str(exc)}",
        )


@chat_router.post(
    "/stream",
    summary="Chat RAG en Streaming (SSE)",
    description=(
        "Endpoint principal multi-cliente para chat en tiempo real mediante Server-Sent Events "
        "(chunk, error_diagnostic, sources, done)."
    ),
    response_class=StreamingResponse,
)
async def stream_chat(
    body: ChatRequest,
    session: Dict[str, Any] = Depends(get_current_session),
):
    return await _handle_stream(body, session)


@chat_router.post(
    "/query",
    response_model=ChatQueryResponse,
    status_code=status.HTTP_200_OK,
    summary="Chat RAG Síncrono (JSON)",
    description="Endpoint síncrono multi-cliente que retorna la respuesta, diagnóstico opcional y fuentes consultadas.",
)
async def query_chat(
    body: ChatRequest,
    session: Dict[str, Any] = Depends(get_current_session),
):
    return await _handle_query(body, session)


@router.post(
    "/stream",
    summary="Consulta y Diagnóstico en Streaming (SSE)",
    description=(
        "Endpoint compatible para el widget de chat embebido. "
        "Emite eventos Server-Sent Events (chunk, error_diagnostic, sources, done) "
        "con efecto de escritura en tiempo real."
    ),
    response_class=StreamingResponse,
)
async def stream_diagnostic(
    body: ChatRequest,
    session: Dict[str, Any] = Depends(get_current_session),
):
    return await _handle_stream(body, session)


@router.post(
    "/query",
    response_model=ChatQueryResponse,
    status_code=status.HTTP_200_OK,
    summary="Consulta y Diagnóstico Síncrono (JSON)",
    description="Alternativa síncrona que retorna la respuesta consolidada, detalles opcionales de error y fuentes documentales.",
)
async def query_diagnostic(
    body: ChatRequest,
    session: Dict[str, Any] = Depends(get_current_session),
):
    return await _handle_query(body, session)
