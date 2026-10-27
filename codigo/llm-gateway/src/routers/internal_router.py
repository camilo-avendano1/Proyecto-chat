"""
Internal API for communicating with LLM Gateway from backend orchestrators (back-chat).
Protected by X-Internal-Key header.
Endpoints:
- POST /internal/v1/chat (Sync or Streaming SSE)
- POST /internal/v1/usage/events (Direct record of fast-path and security interceptions)
"""

import asyncio
import json
import time
from typing import AsyncGenerator
from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.orm import Session

from src.core.audit import audit_logger
from src.db.ledger_repo import LedgerRepository
from src.dependencies import get_db, require_internal_key
from src.schemas import ChatRequest, ChatResponse, UsageEventRecordRequest
from src.services.engine_client import EngineClient

router = APIRouter(
    prefix="/internal/v1",
    tags=["Internal LLM Operations"],
    dependencies=[Depends(require_internal_key)],
)

_engine_client = EngineClient()


def get_engine_client() -> EngineClient:
    return _engine_client


@router.post(
    "/chat",
    summary="Inferencia de Modelos LLM",
    description="Ejecuta inferencia síncrona o streaming (SSE) registrando atribución completa en el Usage Ledger."
)
async def chat_inference(
    request: ChatRequest,
    db: Session = Depends(get_db),
):
    caller = request.caller
    ledger_repo = LedgerRepository(db)

    # 1. Caso Síncrono
    if not request.stream:
        result = await _engine_client.generate_response(
            system_prompt=request.system_prompt,
            user_prompt=request.user_prompt,
            history=request.history,
            model_override=caller.model_requested,
        )

        # Registrar en Ledger
        record = ledger_repo.record_usage(
            request_id=caller.request_id,
            client_id=caller.client_id,
            tenant_id=caller.tenant_id,
            usuario=caller.usuario,
            rol=caller.rol,
            ips_code=caller.ips_code,
            operacion=caller.operacion,
            tokens_input=result.tokens_input,
            tokens_output=result.tokens_output,
            tokens_total=result.tokens_total,
            costo_usd=result.costo_usd,
            latencia_ms=result.latency_ms,
            model=result.model_used,
            provider=result.provider_used,
            status="COMPLETED",
            is_llm_call=True,
            token_source=result.token_source,
            query_preview=(request.user_prompt or "")[:150],
        )

        return ChatResponse(
            response=result.text,
            model_used=result.model_used,
            provider_used=result.provider_used,
            tokens_input=result.tokens_input,
            tokens_output=result.tokens_output,
            tokens_total=result.tokens_total,
            costo_usd=result.costo_usd,
            latencia_ms=result.latency_ms,
            token_source=result.token_source,
        )

    # 2. Caso Streaming (SSE)
    async def sse_event_stream() -> AsyncGenerator[str, None]:
        start_time = time.perf_counter()
        full_text_accum = []

        try:
            async for token in _engine_client.generate_stream(
                system_prompt=request.system_prompt,
                user_prompt=request.user_prompt,
                history=request.history,
                model_override=caller.model_requested,
            ):
                full_text_accum.append(token)
                chunk_data = json.dumps({"text": token}, ensure_ascii=False)
                yield f"event: chunk\ndata: {chunk_data}\n\n"
        except Exception as exc:
            audit_logger.log_system_error(
                error_type="LLM_STREAM_EXCEPTION",
                message=str(exc),
                client_id=caller.client_id,
                tenant_id=caller.tenant_id,
                usuario=caller.usuario,
                request_id=caller.request_id,
            )
            err_data = json.dumps({"error": f"Error en inferencia LLM: {str(exc)}"})
            yield f"event: error\ndata: {err_data}\n\n"

        latency_ms = int((time.perf_counter() - start_time) * 1000)
        full_text = "".join(full_text_accum)
        tokens_in = max(1, (len(request.system_prompt) + len(request.user_prompt)) // 4)
        tokens_out = max(1, len(full_text) // 4)
        cost_usd = _engine_client._calculate_cost(tokens_in, tokens_out, _engine_client.model)

        # Grabar en ledger
        ledger_repo.record_usage(
            request_id=caller.request_id,
            client_id=caller.client_id,
            tenant_id=caller.tenant_id,
            usuario=caller.usuario,
            rol=caller.rol,
            ips_code=caller.ips_code,
            operacion=caller.operacion,
            tokens_input=tokens_in,
            tokens_output=tokens_out,
            tokens_total=tokens_in + tokens_out,
            costo_usd=cost_usd,
            latencia_ms=latency_ms,
            model=_engine_client.model,
            provider=_engine_client.provider,
            status="COMPLETED",
            is_llm_call=True,
            token_source="estimated",
            query_preview=(request.user_prompt or "")[:150],
        )

        done_payload = {
            "status": "COMPLETED",
            "model_used": _engine_client.model,
            "provider_used": _engine_client.provider,
            "tokens_input": tokens_in,
            "tokens_output": tokens_out,
            "tokens_total": tokens_in + tokens_out,
            "costo_usd": cost_usd,
            "latencia_ms": latency_ms,
        }
        yield f"event: done\ndata: {json.dumps(done_payload)}\n\n"

    return StreamingResponse(
        sse_event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@router.post(
    "/usage/events",
    status_code=status.HTTP_201_CREATED,
    summary="Registrar Evento en el Usage Ledger",
    description="Permite registrar operaciones que no llaman al LLM (Fast-Path de saludos, bloqueos de seguridad)."
)
async def record_usage_event(
    event: UsageEventRecordRequest,
    db: Session = Depends(get_db),
):
    caller = event.caller
    ledger_repo = LedgerRepository(db)
    record = ledger_repo.record_usage(
        request_id=caller.request_id,
        client_id=caller.client_id,
        tenant_id=caller.tenant_id,
        usuario=caller.usuario,
        rol=caller.rol,
        ips_code=caller.ips_code,
        operacion=caller.operacion,
        tokens_input=event.tokens_input,
        tokens_output=event.tokens_output,
        tokens_total=event.tokens_input + event.tokens_output,
        costo_usd=event.costo_usd,
        latencia_ms=event.latencia_ms,
        model="none",
        provider="internal",
        status=event.status,
        is_llm_call=event.is_llm_call,
        token_source="direct_event",
        query_preview=event.query_preview,
    )
    return {"status": "recorded", "ledger_id": record.ledger_id}
