"""
Diagnostic and Chat orchestration operations.
Developed by: Juan Camilo Avendaño, Fran Sneider Quincha, Adriana Moreno.

Executes the full pipeline:
1. PII/PHI Sanitization (Ley 1581 de 2012)
2. Inbound message audit & Security Guardrails check (Greetings, Injections, Out-of-Domain)
   - Fast-path for greetings & off-topic: 0 LLM tokens, instant response.
3. Log parsing & Error Diagnostic classification
4. Client-specific Knowledge retrieval via Back - Busqueda
5. Contextual Clinical Prompt assembly with Hardened System Guardrails
6. LLM streaming inference (LM Studio / Ollama / OpenAI)
7. SSE event emission conforming to integration contract
8. Outbound message audit and token ledger recording per User and Tenant
"""

import asyncio
import json
import time
from typing import Any, AsyncGenerator, Dict, List, Optional
import uuid

from src.domain.entities import ErrorDiagnostic, KnowledgeSource, UsageLedgerRecord
from src.infrastructure.security.audit_logger import audit_logger
from src.models.common import ErrorDiagnosticModel, SourceItem
from src.models.diagnostic import (
    DiagnosticQueryResponse,
    DiagnosticStreamRequest,
)
from src.operations.guardrails import ChatGuardrails
from src.operations.interfaces import (
    LedgerRepositoryProtocol,
    LLMServiceProtocol,
    SearchServiceProtocol,
)
from src.operations.log_parser_operations import LogParserOperations
from src.operations.prompt_builder import PromptBuilder
from src.operations.sanitizer_operations import PIISanitizer


class DiagnosticOperations:
    """Core orchestration service for diagnostic assistance and chat."""

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

    async def execute_query(
        self,
        request: DiagnosticStreamRequest,
        tenant_id: str,
        client_id: str = "sigires",
        busqueda_api_url: Optional[str] = None,
        client_name: str = "SIGIRES",
    ) -> DiagnosticQueryResponse:
        """Executes a synchronous diagnostic query (non-streaming)."""
        start_time = time.perf_counter()
        request_id = str(uuid.uuid4())
        usuario = request.user_context.usuario or "anonimo"
        ips_code = request.user_context.ips_code

        # 1. PII Sanitization
        query = request.query
        system_logs = request.system_logs
        if self.enable_pii_scrubbing:
            sanitized_query = PIISanitizer.sanitize(query) or query
            sanitized_logs = PIISanitizer.sanitize(system_logs)
            if sanitized_query != query or sanitized_logs != system_logs:
                audit_logger.log_security_event(
                    event_type="PII_MASKED_IN_PAYLOAD",
                    severity="LOW",
                    client_id=client_id,
                    tenant_id=tenant_id,
                    usuario=usuario,
                    details={"field": "query_or_logs", "rule": "Ley 1581 de 2012"},
                    ips_code=ips_code,
                    request_id=request_id,
                )
            query = sanitized_query
            system_logs = sanitized_logs

        # 2. Audit inbound message
        audit_logger.log_message_in(
            client_id=client_id,
            tenant_id=tenant_id,
            usuario=usuario,
            content=query,
            ips_code=ips_code,
            request_id=request_id,
        )

        # 3. Guardrails Pre-LLM check (Greetings, Prompt Injections, Out-of-Domain)
        guardrail = ChatGuardrails.evaluate(
            query=query,
            system_logs=system_logs,
            client_name=client_name
        )

        if guardrail.is_intercepted:
            latency_ms = int((time.perf_counter() - start_time) * 1000)

            # Security audit logging if blocked or out-of-domain
            if guardrail.status == "SECURITY_BLOCKED":
                audit_logger.log_security_event(
                    event_type="PROMPT_INJECTION_ATTEMPT",
                    severity="HIGH",
                    client_id=client_id,
                    tenant_id=tenant_id,
                    usuario=usuario,
                    details={"query": query, "reason": guardrail.reason},
                    ips_code=ips_code,
                    request_id=request_id,
                )
            elif guardrail.status == "OUT_OF_DOMAIN":
                audit_logger.log_security_event(
                    event_type="OUT_OF_DOMAIN_QUERY",
                    severity="MEDIUM",
                    client_id=client_id,
                    tenant_id=tenant_id,
                    usuario=usuario,
                    details={"query": query},
                    ips_code=ips_code,
                    request_id=request_id,
                )

            # Record in ledger with 0 LLM tokens consumed
            await self.ledger_repo.record_usage(
                UsageLedgerRecord(
                    client_id=client_id,
                    tenant_id=tenant_id,
                    usuario=usuario,
                    ips_code=ips_code,
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

            # Notificar al LLM Gateway de evento no-LLM si está disponible
            if hasattr(self.llm_service, "record_usage_event"):
                try:
                    await self.llm_service.record_usage_event(
                        client_id=client_id,
                        tenant_id=tenant_id,
                        usuario=usuario,
                        operacion=guardrail.status,
                        is_llm_call=False,
                        tokens_input=0,
                        tokens_output=0,
                        costo_usd=0.0,
                        latencia_ms=latency_ms,
                        rol=request.user_context.permisos or "usuario",
                        status=guardrail.status,
                        request_id=request_id,
                    )
                except Exception:
                    pass

            # Audit outbound response
            audit_logger.log_message_out(
                client_id=client_id,
                tenant_id=tenant_id,
                usuario=usuario,
                content=guardrail.direct_response or "",
                tokens=0,
                costo_usd=0.0,
                latencia_ms=latency_ms,
                status=guardrail.status,
                ips_code=ips_code,
                request_id=request_id,
            )

            return DiagnosticQueryResponse(
                response=guardrail.direct_response or "",
                error_diagnostic=None,
                sources=[],
            )

        # 4. Parse log and classify error
        diagnostic = LogParserOperations.parse_log_or_query(
            system_logs=system_logs,
            query=query,
            formato_archivo=request.ui_context.formato_archivo
        )

        # 5. Retrieve relevant knowledge from Client's Back - Busqueda
        sources = await self.search_service.search(
            query=query,
            client_id=client_id,
            busqueda_api_url=busqueda_api_url,
            tenant_id=tenant_id,
            category=diagnostic.category,
            variable_num=diagnostic.affected_variable_number,
            error_code=diagnostic.detected_code,
            top_k=4,
        )

        # 6. Build specialized prompt with hardened behavioral constraints
        system_prompt = PromptBuilder.build_system_prompt(
            request.user_context,
            client_id=client_id,
            client_name=client_name
        )
        user_prompt = PromptBuilder.build_user_prompt(
            query=query,
            system_logs=system_logs,
            ui_context=request.ui_context,
            user_context=request.user_context,
            diagnostic=diagnostic,
            knowledge_sources=sources,
            client_name=client_name,
        )

        # Format history for LLM
        history: List[Dict[str, str]] = [
            {"role": msg.role, "content": msg.content}
            for msg in (request.conversation_history or [])
        ]

        # 7. Call LLM con contexto de atribución del llamador
        response_text = await self.llm_service.generate_response(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            history=history,
            client_id=client_id,
            tenant_id=tenant_id,
            usuario=usuario,
            rol=request.user_context.permisos or "usuario",
            operacion="DIAGNOSTIC_QUERY",
            request_id=request_id,
        )

        # 8. Record usage metrics per user and tenant
        latency_ms = int((time.perf_counter() - start_time) * 1000)
        tokens_in = (len(system_prompt) + len(user_prompt)) // 4
        tokens_out = max(1, len(response_text) // 4)
        cost_usd = (tokens_in * 0.00000015) + (tokens_out * 0.0000006)

        await self.ledger_repo.record_usage(
            UsageLedgerRecord(
                client_id=client_id,
                tenant_id=tenant_id,
                usuario=usuario,
                ips_code=ips_code,
                operacion="DIAGNOSTIC_QUERY",
                tokens_input=tokens_in,
                tokens_output=tokens_out,
                costo_usd=round(cost_usd, 6),
                latencia_ms=latency_ms,
                status="COMPLETED",
                is_llm_call=True,
                request_id=request_id,
                query_preview=query[:100],
            )
        )

        # 9. Audit outbound response
        audit_logger.log_message_out(
            client_id=client_id,
            tenant_id=tenant_id,
            usuario=usuario,
            content=response_text,
            tokens=tokens_in + tokens_out,
            costo_usd=round(cost_usd, 6),
            latencia_ms=latency_ms,
            status="COMPLETED",
            ips_code=ips_code,
            request_id=request_id,
        )

        # 10. Build Response
        error_model = ErrorDiagnosticModel(**diagnostic.to_dict())
        source_items = [
            SourceItem(
                document_title=s.document_title,
                scope=s.scope.value if hasattr(s.scope, "value") else str(s.scope),
                section=s.section,
            )
            for s in sources
        ]

        return DiagnosticQueryResponse(
            response=response_text,
            error_diagnostic=error_model,
            sources=source_items,
        )

    async def execute_stream(
        self,
        request: DiagnosticStreamRequest,
        tenant_id: str,
        client_id: str = "sigires",
        busqueda_api_url: Optional[str] = None,
        client_name: str = "SIGIRES",
    ) -> AsyncGenerator[str, None]:
        """
        Executes a real-time diagnostic stream emitting Server-Sent Events (SSE).
        Conforms strictly to the contract in especificacion-api-integracion-widget.md:
        - event: chunk
        - event: error_diagnostic
        - event: sources
        - event: done
        """
        start_time = time.perf_counter()
        request_id = str(uuid.uuid4())
        usuario = request.user_context.usuario or "anonimo"
        ips_code = request.user_context.ips_code

        # 1. PII Sanitization
        query = request.query
        system_logs = request.system_logs
        if self.enable_pii_scrubbing:
            sanitized_query = PIISanitizer.sanitize(query) or query
            sanitized_logs = PIISanitizer.sanitize(system_logs)
            if sanitized_query != query or sanitized_logs != system_logs:
                audit_logger.log_security_event(
                    event_type="PII_MASKED_IN_PAYLOAD",
                    severity="LOW",
                    client_id=client_id,
                    tenant_id=tenant_id,
                    usuario=usuario,
                    details={"field": "query_or_logs", "rule": "Ley 1581 de 2012"},
                    ips_code=ips_code,
                    request_id=request_id,
                )
            query = sanitized_query
            system_logs = sanitized_logs

        # 2. Audit inbound message
        audit_logger.log_message_in(
            client_id=client_id,
            tenant_id=tenant_id,
            usuario=usuario,
            content=query,
            ips_code=ips_code,
            request_id=request_id,
        )

        # 3. Guardrails Pre-LLM check (Greetings, Prompt Injections, Out-of-Domain)
        guardrail = ChatGuardrails.evaluate(
            query=query,
            system_logs=system_logs,
            client_name=client_name
        )

        if guardrail.is_intercepted:
            direct_text = guardrail.direct_response or ""

            # Security audit logging if blocked or out-of-domain
            if guardrail.status == "SECURITY_BLOCKED":
                audit_logger.log_security_event(
                    event_type="PROMPT_INJECTION_ATTEMPT",
                    severity="HIGH",
                    client_id=client_id,
                    tenant_id=tenant_id,
                    usuario=usuario,
                    details={"query": query, "reason": guardrail.reason},
                    ips_code=ips_code,
                    request_id=request_id,
                )
            elif guardrail.status == "OUT_OF_DOMAIN":
                audit_logger.log_security_event(
                    event_type="OUT_OF_DOMAIN_QUERY",
                    severity="MEDIUM",
                    client_id=client_id,
                    tenant_id=tenant_id,
                    usuario=usuario,
                    details={"query": query},
                    ips_code=ips_code,
                    request_id=request_id,
                )

            # Stream direct text via SSE chunks with natural pacing
            words = direct_text.split(" ")
            for i, word in enumerate(words):
                chunk = word + (" " if i < len(words) - 1 else "")
                chunk_data = json.dumps({"text": chunk}, ensure_ascii=False)
                yield f"event: chunk\ndata: {chunk_data}\n\n"
                await asyncio.sleep(0.005)

            # Emit clean/empty error diagnostic
            yield f"event: error_diagnostic\ndata: null\n\n"

            # Emit empty sources
            yield f"event: sources\ndata: []\n\n"

            # Emit done
            done_json = json.dumps({"status": guardrail.status})
            yield f"event: done\ndata: {done_json}\n\n"

            # Record usage with 0 LLM tokens
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            await self.ledger_repo.record_usage(
                UsageLedgerRecord(
                    client_id=client_id,
                    tenant_id=tenant_id,
                    usuario=usuario,
                    ips_code=ips_code,
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

            # Notificar al LLM Gateway de evento no-LLM si está disponible
            if hasattr(self.llm_service, "record_usage_event"):
                try:
                    await self.llm_service.record_usage_event(
                        client_id=client_id,
                        tenant_id=tenant_id,
                        usuario=usuario,
                        operacion=guardrail.status,
                        is_llm_call=False,
                        tokens_input=0,
                        tokens_output=0,
                        costo_usd=0.0,
                        latencia_ms=latency_ms,
                        rol=request.user_context.permisos or "usuario",
                        status=guardrail.status,
                        request_id=request_id,
                    )
                except Exception:
                    pass

            # Audit outbound response
            audit_logger.log_message_out(
                client_id=client_id,
                tenant_id=tenant_id,
                usuario=usuario,
                content=direct_text,
                tokens=0,
                costo_usd=0.0,
                latencia_ms=latency_ms,
                status=guardrail.status,
                ips_code=ips_code,
                request_id=request_id,
            )
            return

        # 4. Parse log and classify error
        diagnostic = LogParserOperations.parse_log_or_query(
            system_logs=system_logs,
            query=query,
            formato_archivo=request.ui_context.formato_archivo
        )

        # 5. Retrieve relevant knowledge from Client's Back - Busqueda
        sources = await self.search_service.search(
            query=query,
            client_id=client_id,
            busqueda_api_url=busqueda_api_url,
            tenant_id=tenant_id,
            category=diagnostic.category,
            variable_num=diagnostic.affected_variable_number,
            error_code=diagnostic.detected_code,
            top_k=4,
        )

        # 6. Build specialized prompt with hardened boundaries
        system_prompt = PromptBuilder.build_system_prompt(
            request.user_context,
            client_id=client_id,
            client_name=client_name
        )
        user_prompt = PromptBuilder.build_user_prompt(
            query=query,
            system_logs=system_logs,
            ui_context=request.ui_context,
            user_context=request.user_context,
            diagnostic=diagnostic,
            knowledge_sources=sources,
            client_name=client_name,
        )

        history: List[Dict[str, str]] = [
            {"role": msg.role, "content": msg.content}
            for msg in (request.conversation_history or [])
        ]

        # 7. Stream LLM tokens as SSE chunks con contexto de atribución
        full_text_accum = []
        try:
            async for token in self.llm_service.generate_stream(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                history=history,
                client_id=client_id,
                tenant_id=tenant_id,
                usuario=usuario,
                rol=request.user_context.permisos or "usuario",
                operacion="DIAGNOSTIC_STREAM",
                request_id=request_id,
            ):
                full_text_accum.append(token)
                chunk_data = json.dumps({"text": token}, ensure_ascii=False)
                yield f"event: chunk\ndata: {chunk_data}\n\n"
        except Exception as e:
            audit_logger.log_system_error(
                error_type="LLM_STREAM_ERROR",
                message=str(e),
                client_id=client_id,
                tenant_id=tenant_id,
                usuario=usuario,
                request_id=request_id,
            )
            error_data = json.dumps({"error": f"Error en inferencia LLM: {str(e)}"})
            yield f"event: error\ndata: {error_data}\n\n"

        # 8. Emit error_diagnostic event
        diag_dict = diagnostic.to_dict()
        diag_json = json.dumps(diag_dict, ensure_ascii=False)
        yield f"event: error_diagnostic\ndata: {diag_json}\n\n"

        # 9. Emit sources event
        sources_list = [s.to_dict() for s in sources]
        sources_json = json.dumps(sources_list, ensure_ascii=False)
        yield f"event: sources\ndata: {sources_json}\n\n"

        # 10. Emit done event
        done_json = json.dumps({"status": "COMPLETED"})
        yield f"event: done\ndata: {done_json}\n\n"

        # 11. Record usage metrics per user and tenant
        latency_ms = int((time.perf_counter() - start_time) * 1000)
        full_text = "".join(full_text_accum)
        tokens_in = (len(system_prompt) + len(user_prompt)) // 4
        tokens_out = max(1, len(full_text) // 4)
        cost_usd = (tokens_in * 0.00000015) + (tokens_out * 0.0000006)

        await self.ledger_repo.record_usage(
            UsageLedgerRecord(
                client_id=client_id,
                tenant_id=tenant_id,
                usuario=usuario,
                ips_code=ips_code,
                operacion="DIAGNOSTIC_STREAM",
                tokens_input=tokens_in,
                tokens_output=tokens_out,
                costo_usd=round(cost_usd, 6),
                latencia_ms=latency_ms,
                status="COMPLETED",
                is_llm_call=True,
                request_id=request_id,
                query_preview=query[:100],
            )
        )

        # 12. Audit outbound response
        audit_logger.log_message_out(
            client_id=client_id,
            tenant_id=tenant_id,
            usuario=usuario,
            content=full_text,
            tokens=tokens_in + tokens_out,
            costo_usd=round(cost_usd, 6),
            latencia_ms=latency_ms,
            status="COMPLETED",
            ips_code=ips_code,
            request_id=request_id,
        )
