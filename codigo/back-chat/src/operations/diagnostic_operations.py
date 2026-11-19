"""
Chat and Diagnostic orchestration operations.
Developed by: Juan Camilo Avendaño, Fran Sneider Quincha, Adriana Moreno.

Executes the full pipeline:
1. PII/PHI Sanitization (Ley 1581 de 2012)
2. Inbound message audit & Security Guardrails check (Greetings, Injections, Out-of-Domain)
   - Fast-path for greetings & off-topic: 0 LLM tokens, instant response.
3. Optional Log parsing & Error Diagnostic classification (only when error signals exist)
4. Organization-specific Knowledge retrieval via Back - Busqueda
5. Contextual adaptive Prompt assembly with Hardened System Guardrails
6. LLM streaming/sync inference (via LLM Gateway / OpenAI-compatible server)
7. SSE event emission conforming to integration contract
8. Outbound message audit and token ledger recording per User and Site
"""

import asyncio
import json
import time
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple
import uuid

from src.domain.entities import ErrorDiagnostic, KnowledgeSource, UsageLedgerRecord
from src.infrastructure.security.audit_logger import audit_logger
from src.models.common import ErrorDiagnosticModel, SourceItem
from src.models.diagnostic import (
    ChatQueryResponse,
    ChatRequest,
)
from src.operations.guardrails import ChatGuardrails, GuardrailResult
from src.operations.interfaces import (
    LedgerRepositoryProtocol,
    LLMServiceProtocol,
    SearchServiceProtocol,
)
from src.operations.log_parser_operations import LogParserOperations
from src.operations.prompt_builder import PromptBuilder
from src.operations.sanitizer_operations import PIISanitizer


class DiagnosticOperations:
    """Core orchestration service for multi-organization chat and diagnostic assistance."""

    def __init__(
        self,
        search_service: SearchServiceProtocol,
        llm_service: LLMServiceProtocol,
        ledger_repo: LedgerRepositoryProtocol,
        enable_pii_scrubbing: bool = True,
    ):
        self.search_service = search_service
        self.llm_service = llm_service
        self.ledger_repo = ledger_repo
        self.enable_pii_scrubbing = enable_pii_scrubbing

    def _sanitize_inputs(
        self,
        raw_query: str,
        raw_logs: Optional[str],
        org_id: str,
        site_id: str,
        usuario: str,
        site_code: Optional[str],
        request_id: str,
    ) -> Tuple[str, Optional[str]]:
        if not self.enable_pii_scrubbing:
            return raw_query, raw_logs

        sanitized_query = PIISanitizer.sanitize(raw_query) or raw_query
        sanitized_logs = PIISanitizer.sanitize(raw_logs)
        if sanitized_query != raw_query or sanitized_logs != raw_logs:
            audit_logger.log_security_event(
                event_type="PII_MASKED_IN_PAYLOAD",
                severity="LOW",
                org_id=org_id,
                site_id=site_id,
                usuario=usuario,
                details={"field": "query_or_logs", "rule": "Ley 1581 de 2012"},
                site_code=site_code,
                request_id=request_id,
            )
        return sanitized_query, sanitized_logs

    async def _record_interception(
        self,
        guardrail: GuardrailResult,
        org_id: str,
        site_id: str,
        usuario: str,
        effective_role: str,
        site_code: Optional[str],
        request_id: str,
        query: str,
        start_time: float,
    ) -> None:
        latency_ms = int((time.perf_counter() - start_time) * 1000)
        direct_text = guardrail.direct_response or ""

        if guardrail.status == "SECURITY_BLOCKED":
            audit_logger.log_security_event(
                event_type="PROMPT_INJECTION_ATTEMPT",
                severity="HIGH",
                org_id=org_id,
                site_id=site_id,
                usuario=usuario,
                details={"query": query, "reason": guardrail.reason},
                site_code=site_code,
                request_id=request_id,
            )
        elif guardrail.status == "OUT_OF_DOMAIN":
            audit_logger.log_security_event(
                event_type="OUT_OF_DOMAIN_QUERY",
                severity="MEDIUM",
                org_id=org_id,
                site_id=site_id,
                usuario=usuario,
                details={"query": query},
                site_code=site_code,
                request_id=request_id,
            )

        await self.ledger_repo.record_usage(
            UsageLedgerRecord(
                org_id=org_id,
                site_id=site_id,
                usuario=usuario,
                site_code=site_code,
                operacion=guardrail.status,
                tokens_input=0,
                tokens_output=0,
                costo_usd=0.0,
                latencia_ms=latency_ms,
                status=guardrail.status,
                is_llm_call=False,
                request_id=request_id,
                query_preview=query[:100],
            )
        )

        if hasattr(self.llm_service, "record_usage_event"):
            try:
                await self.llm_service.record_usage_event(
                    org_id=org_id,
                    site_id=site_id,
                    site_code=site_code,
                    usuario=usuario,
                    operacion=guardrail.status,
                    is_llm_call=False,
                    tokens_input=0,
                    tokens_output=0,
                    costo_usd=0.0,
                    latencia_ms=latency_ms,
                    rol=effective_role,
                    status=guardrail.status,
                    request_id=request_id,
                )
            except Exception:
                pass

        audit_logger.log_message_out(
            org_id=org_id,
            site_id=site_id,
            usuario=usuario,
            content=direct_text,
            tokens=0,
            costo_usd=0.0,
            latencia_ms=latency_ms,
            status=guardrail.status,
            site_code=site_code,
            request_id=request_id,
            rol=effective_role,
        )

    async def _prepare_llm_context(
        self,
        request: ChatRequest,
        query: str,
        system_logs: Optional[str],
        org_id: str,
        org_name: str,
        site_id: str,
        busqueda_api_url: Optional[str],
        usuario: str,
        role: Optional[str],
        user_attrs: Dict[str, Any],
        context_dict: Dict[str, Any],
        formato_archivo: Optional[str],
    ) -> Tuple[Optional[ErrorDiagnostic], List[KnowledgeSource], str, str, List[Dict[str, str]]]:
        diagnostic = LogParserOperations.parse_log_or_query(
            system_logs=system_logs,
            query=query,
            formato_archivo=formato_archivo,
        )

        sources = await self.search_service.search(
            query=query,
            org_id=org_id,
            busqueda_api_url=busqueda_api_url,
            site_id=site_id,
            category=diagnostic.category if diagnostic else None,
            variable_num=diagnostic.affected_variable_number if diagnostic else None,
            error_code=diagnostic.detected_code if diagnostic else None,
            extras=request.extras,
            top_k=4,
        )

        system_prompt = PromptBuilder.build_system_prompt(
            user_context=request.user_context,
            org_id=org_id,
            org_name=org_name,
            usuario=usuario,
            role=role,
            user_attributes=user_attrs,
        )
        user_prompt = PromptBuilder.build_user_prompt(
            query=query,
            system_logs=system_logs,
            ui_context=request.ui_context,
            user_context=request.user_context,
            diagnostic=diagnostic,
            knowledge_sources=sources,
            org_name=org_name,
            context=context_dict,
            usuario=usuario,
            role=role,
            user_attributes=user_attrs,
        )

        history: List[Dict[str, str]] = [
            {"role": msg.role, "content": msg.content}
            for msg in (request.conversation_history or [])
        ]
        return diagnostic, sources, system_prompt, user_prompt, history

    async def _finalize_usage_and_audit(
        self,
        org_id: str,
        site_id: str,
        usuario: str,
        effective_role: str,
        site_code: Optional[str],
        operacion: str,
        request_id: str,
        query: str,
        system_prompt: str,
        user_prompt: str,
        response_text: str,
        start_time: float,
    ) -> None:
        latency_ms = int((time.perf_counter() - start_time) * 1000)
        tokens_in = (len(system_prompt) + len(user_prompt)) // 4
        tokens_out = max(1, len(response_text) // 4)
        cost_usd = round((tokens_in * 0.00000015) + (tokens_out * 0.0000006), 6)

        await self.ledger_repo.record_usage(
            UsageLedgerRecord(
                org_id=org_id,
                site_id=site_id,
                usuario=usuario,
                site_code=site_code,
                operacion=operacion,
                tokens_input=tokens_in,
                tokens_output=tokens_out,
                costo_usd=cost_usd,
                latencia_ms=latency_ms,
                status="COMPLETED",
                is_llm_call=True,
                request_id=request_id,
                query_preview=query[:100],
            )
        )

        audit_logger.log_message_out(
            org_id=org_id,
            site_id=site_id,
            usuario=usuario,
            content=response_text,
            tokens=tokens_in + tokens_out,
            costo_usd=cost_usd,
            latencia_ms=latency_ms,
            status="COMPLETED",
            site_code=site_code,
            request_id=request_id,
            rol=effective_role,
        )

    async def execute_query(
        self,
        request: ChatRequest,
        site_id: str,
        org_id: str = "default",
        busqueda_api_url: Optional[str] = None,
        org_name: str = "la Plataforma",
        session_metadata: Optional[Dict[str, Any]] = None,
        session_site_code: Optional[str] = None,
    ) -> ChatQueryResponse:
        """Executes a synchronous chat or diagnostic query (non-streaming)."""
        start_time = time.perf_counter()
        request_id = str(uuid.uuid4())

        usuario = request.get_usuario()
        role = request.get_role()
        effective_role = role or "usuario"
        site_code = request.get_site_code() or session_site_code
        raw_logs = request.get_logs()
        context_dict = request.get_context_dict()
        user_attrs = {**(session_metadata or {}), **request.get_user_attributes()}
        formato_archivo = request.get_formato_archivo()

        query, system_logs = self._sanitize_inputs(
            raw_query=request.query,
            raw_logs=raw_logs,
            org_id=org_id,
            site_id=site_id,
            usuario=usuario,
            site_code=site_code,
            request_id=request_id,
        )

        audit_logger.log_message_in(
            org_id=org_id,
            site_id=site_id,
            usuario=usuario,
            content=query,
            site_code=site_code,
            request_id=request_id,
            rol=effective_role,
        )

        guardrail = ChatGuardrails.evaluate(
            query=query,
            system_logs=system_logs,
            org_name=org_name,
        )
        if guardrail.is_intercepted:
            await self._record_interception(
                guardrail=guardrail,
                org_id=org_id,
                site_id=site_id,
                usuario=usuario,
                effective_role=effective_role,
                site_code=site_code,
                request_id=request_id,
                query=query,
                start_time=start_time,
            )
            return ChatQueryResponse(
                response=guardrail.direct_response or "",
                error_diagnostic=None,
                sources=[],
            )

        diagnostic, sources, system_prompt, user_prompt, history = await self._prepare_llm_context(
            request=request,
            query=query,
            system_logs=system_logs,
            org_id=org_id,
            org_name=org_name,
            site_id=site_id,
            busqueda_api_url=busqueda_api_url,
            usuario=usuario,
            role=role,
            user_attrs=user_attrs,
            context_dict=context_dict,
            formato_archivo=formato_archivo,
        )

        response_text = await self.llm_service.generate_response(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            history=history,
            org_id=org_id,
            site_id=site_id,
            usuario=usuario,
            rol=effective_role,
            site_code=site_code,
            operacion="CHAT_QUERY",
            request_id=request_id,
        )

        await self._finalize_usage_and_audit(
            org_id=org_id,
            site_id=site_id,
            usuario=usuario,
            effective_role=effective_role,
            site_code=site_code,
            operacion="CHAT_QUERY",
            request_id=request_id,
            query=query,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_text=response_text,
            start_time=start_time,
        )

        error_model = ErrorDiagnosticModel(**diagnostic.to_dict()) if diagnostic else None
        source_items = [
            SourceItem(
                document_title=s.document_title,
                scope=s.scope.value if hasattr(s.scope, "value") else str(s.scope),
                section=s.section,
            )
            for s in sources
        ]

        return ChatQueryResponse(
            response=response_text,
            error_diagnostic=error_model,
            sources=source_items,
        )

    async def execute_stream(
        self,
        request: ChatRequest,
        site_id: str,
        org_id: str = "default",
        busqueda_api_url: Optional[str] = None,
        org_name: str = "la Plataforma",
        session_metadata: Optional[Dict[str, Any]] = None,
        session_site_code: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """
        Executes a real-time chat or diagnostic stream emitting Server-Sent Events (SSE):
        - event: chunk
        - event: error_diagnostic
        - event: sources
        - event: done
        """
        start_time = time.perf_counter()
        request_id = str(uuid.uuid4())

        usuario = request.get_usuario()
        role = request.get_role()
        effective_role = role or "usuario"
        site_code = request.get_site_code() or session_site_code
        raw_logs = request.get_logs()
        context_dict = request.get_context_dict()
        user_attrs = {**(session_metadata or {}), **request.get_user_attributes()}
        formato_archivo = request.get_formato_archivo()

        query, system_logs = self._sanitize_inputs(
            raw_query=request.query,
            raw_logs=raw_logs,
            org_id=org_id,
            site_id=site_id,
            usuario=usuario,
            site_code=site_code,
            request_id=request_id,
        )

        audit_logger.log_message_in(
            org_id=org_id,
            site_id=site_id,
            usuario=usuario,
            content=query,
            site_code=site_code,
            request_id=request_id,
            rol=effective_role,
        )

        guardrail = ChatGuardrails.evaluate(
            query=query,
            system_logs=system_logs,
            org_name=org_name,
        )
        if guardrail.is_intercepted:
            direct_text = guardrail.direct_response or ""
            words = direct_text.split(" ")
            for i, word in enumerate(words):
                chunk = word + (" " if i < len(words) - 1 else "")
                chunk_data = json.dumps({"text": chunk}, ensure_ascii=False)
                yield f"event: chunk\ndata: {chunk_data}\n\n"
                await asyncio.sleep(0.005)

            yield "event: error_diagnostic\ndata: null\n\n"
            yield "event: sources\ndata: []\n\n"
            yield f"event: done\ndata: {json.dumps({'status': guardrail.status})}\n\n"

            await self._record_interception(
                guardrail=guardrail,
                org_id=org_id,
                site_id=site_id,
                usuario=usuario,
                effective_role=effective_role,
                site_code=site_code,
                request_id=request_id,
                query=query,
                start_time=start_time,
            )
            return

        diagnostic, sources, system_prompt, user_prompt, history = await self._prepare_llm_context(
            request=request,
            query=query,
            system_logs=system_logs,
            org_id=org_id,
            org_name=org_name,
            site_id=site_id,
            busqueda_api_url=busqueda_api_url,
            usuario=usuario,
            role=role,
            user_attrs=user_attrs,
            context_dict=context_dict,
            formato_archivo=formato_archivo,
        )

        full_text_accum = []
        try:
            async for token in self.llm_service.generate_stream(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                history=history,
                org_id=org_id,
                site_id=site_id,
                usuario=usuario,
                rol=effective_role,
                site_code=site_code,
                operacion="CHAT_STREAM",
                request_id=request_id,
            ):
                full_text_accum.append(token)
                chunk_data = json.dumps({"text": token}, ensure_ascii=False)
                yield f"event: chunk\ndata: {chunk_data}\n\n"
        except Exception as e:
            audit_logger.log_system_error(
                error_type="LLM_STREAM_ERROR",
                message=str(e),
                org_id=org_id,
                site_id=site_id,
                usuario=usuario,
                request_id=request_id,
            )
            error_data = json.dumps({"error": f"Error en inferencia LLM: {str(e)}"})
            yield f"event: error\ndata: {error_data}\n\n"

        if diagnostic is not None:
            diag_json = json.dumps(diagnostic.to_dict(), ensure_ascii=False)
            yield f"event: error_diagnostic\ndata: {diag_json}\n\n"
        else:
            yield "event: error_diagnostic\ndata: null\n\n"

        sources_list = [s.to_dict() for s in sources]
        sources_json = json.dumps(sources_list, ensure_ascii=False)
        yield f"event: sources\ndata: {sources_json}\n\n"

        done_json = json.dumps({"status": "COMPLETED"})
        yield f"event: done\ndata: {done_json}\n\n"

        full_text = "".join(full_text_accum)
        await self._finalize_usage_and_audit(
            org_id=org_id,
            site_id=site_id,
            usuario=usuario,
            effective_role=effective_role,
            site_code=site_code,
            operacion="CHAT_STREAM",
            request_id=request_id,
            query=query,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_text=full_text,
            start_time=start_time,
        )
