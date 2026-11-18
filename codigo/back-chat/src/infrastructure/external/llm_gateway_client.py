"""
Client adapter communicating with the dedicated LLM Gateway microservice (Port 8003).
Implements LLMServiceProtocol with caller segmentation and resilient fallbacks.
Developed by: Juan Camilo Avendaño, Fran Sneider Quincha, Adriana Moreno.
"""

import asyncio
import json
import logging
from typing import Any, AsyncGenerator, Dict, List, Optional
import httpx

from src.config import settings
from src.operations.interfaces import LLMServiceProtocol

logger = logging.getLogger(__name__)


class LLMGatewayClient(LLMServiceProtocol):
    """
    HTTP client for the dedicated LLM Gateway service.
    Segregates inference, security authentication via X-Internal-Key,
    and forwards caller attribution (client, tenant, user, role).
    """

    def __init__(
        self,
        gateway_url: str = settings.LLM_GATEWAY_URL,
        internal_key: str = settings.INTERNAL_SERVICE_KEY,
        timeout_seconds: float = 45.0,
        fallback_on_error: bool = settings.FALLBACK_SIMULATION_ON_LLM_ERROR,
    ):
        self.gateway_url = gateway_url.rstrip("/")
        self.internal_key = internal_key
        self.timeout_seconds = timeout_seconds
        self.fallback_on_error = fallback_on_error

    async def generate_response(
        self,
        system_prompt: str,
        user_prompt: str,
        history: Optional[List[Dict[str, str]]] = None,
        **kwargs: Any,
    ) -> str:
        if settings.ENVIRONMENT == "testing":
            return self._generate_simulated_response(user_prompt)

        payload = {
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
            "history": history or [],
            "caller": {
                "client_id": kwargs.get("client_id", "default"),
                "tenant_id": kwargs.get("tenant_id", "default"),
                "usuario": kwargs.get("usuario", "anonimo"),
                "rol": kwargs.get("rol", "usuario"),
                "operacion": kwargs.get("operacion", "CHAT_QUERY"),
                "ips_code": kwargs.get("ips_code"),
                "request_id": kwargs.get("request_id"),
                "model_requested": kwargs.get("model_requested"),
            },
            "stream": False,
        }
        headers = {
            "X-Internal-Key": self.internal_key,
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                resp = await client.post(
                    f"{self.gateway_url}/internal/v1/chat",
                    headers=headers,
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()
                return data.get("response") or data.get("content", "")
        except Exception as exc:
            logger.warning(
                "No se pudo comunicar con llm-gateway en %s (%s). Activando fallback de contingencia.",
                self.gateway_url,
                exc,
            )
            if self.fallback_on_error:
                return self._generate_simulated_response(user_prompt)
            raise

    async def generate_stream(
        self,
        system_prompt: str,
        user_prompt: str,
        history: Optional[List[Dict[str, str]]] = None,
        **kwargs: Any,
    ) -> AsyncGenerator[str, None]:
        if settings.ENVIRONMENT == "testing":
            simulated = self._generate_simulated_response(user_prompt)
            for word in simulated.split(" "):
                yield word + " "
                await asyncio.sleep(0.001)
            return

        payload = {
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
            "history": history or [],
            "caller": {
                "client_id": kwargs.get("client_id", "default"),
                "tenant_id": kwargs.get("tenant_id", "default"),
                "usuario": kwargs.get("usuario", "anonimo"),
                "rol": kwargs.get("rol", "usuario"),
                "operacion": kwargs.get("operacion", "CHAT_STREAM"),
                "ips_code": kwargs.get("ips_code"),
                "request_id": kwargs.get("request_id"),
                "model_requested": kwargs.get("model_requested"),
            },
            "stream": True,
        }
        headers = {
            "X-Internal-Key": self.internal_key,
            "Content-Type": "application/json",
        }

        stream_failed = False
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                async with client.stream(
                    "POST",
                    f"{self.gateway_url}/internal/v1/chat",
                    headers=headers,
                    json=payload,
                ) as resp:
                    resp.raise_for_status()
                    async for line in resp.aiter_lines():
                        if not line:
                            continue
                        if line.startswith("data: "):
                            raw_data = line[6:].strip()
                            if raw_data == "[DONE]":
                                break
                            try:
                                parsed = json.loads(raw_data)
                                if parsed.get("done") or parsed.get("status") == "COMPLETED":
                                    break
                                chunk = parsed.get("text") or parsed.get("chunk")
                                if chunk:
                                    yield chunk
                            except json.JSONDecodeError:
                                continue
        except Exception as exc:
            logger.warning(
                "Error en stream con llm-gateway en %s (%s). Activando emisión simulada.",
                self.gateway_url,
                exc,
            )
            stream_failed = True

        if stream_failed and self.fallback_on_error:
            simulated = self._generate_simulated_response(user_prompt)
            words = simulated.split(" ")
            for i, word in enumerate(words):
                chunk = word + (" " if i < len(words) - 1 else "")
                yield chunk
                await asyncio.sleep(0.01)

    async def record_usage_event(
        self,
        client_id: str,
        tenant_id: str,
        usuario: str,
        operacion: str,
        is_llm_call: bool = False,
        tokens_input: int = 0,
        tokens_output: int = 0,
        costo_usd: float = 0.0,
        latencia_ms: int = 0,
        rol: str = "usuario",
        status: str = "COMPLETED",
        request_id: Optional[str] = None,
    ) -> None:
        """Notifica al gateway de un evento que no consumió LLM (guardrails / fast-path)."""
        payload = {
            "caller": {
                "client_id": client_id,
                "tenant_id": tenant_id,
                "usuario": usuario,
                "rol": rol,
                "operacion": operacion,
                "request_id": request_id,
            },
            "is_llm_call": is_llm_call,
            "tokens_input": tokens_input,
            "tokens_output": tokens_output,
            "costo_usd": costo_usd,
            "latencia_ms": latencia_ms,
            "status": status,
        }
        headers = {
            "X-Internal-Key": self.internal_key,
            "Content-Type": "application/json",
        }
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                await client.post(
                    f"{self.gateway_url}/internal/v1/usage/events",
                    headers=headers,
                    json=payload,
                )
        except Exception:
            logger.debug("No se pudo notificar evento de uso al gateway (servicio auxiliar).")

    def _generate_simulated_response(self, user_prompt: str) -> str:
        """
        Respuesta de contingencia adaptativa cuando ningún modelo responde o en entorno de pruebas.
        Cubre tres casos:
        1. Diagnóstico técnico con código de error y/o fragmentos RAG -> formato estructurado en 4 secciones.
        2. Consulta general con fragmentos RAG -> respuesta directa citando el documento recuperado.
        3. Consulta sin fragmentos RAG / prompt corto -> orientación neutral de contingencia >50 chars.
        """
        import re

        code_match = re.search(r"-\s*Código de Error:\s*(.+)", user_prompt)
        phase_match = re.search(r"-\s*Fase / Categoría de Validación:\s*(.+)", user_prompt)
        field_match = re.search(r"-\s*Campo / Variable / Columna Afectada:\s*(.+)", user_prompt)
        format_match = re.search(
            r"-\s*(?:Formato de Formulario o Archivo|formato_archivo|file_format):\s*(.+)",
            user_prompt,
        )
        query_match = re.search(
            r'CONSULTA DEL (?:USUARIO|PROFESIONAL):\s*\n\s*"(.+?)"',
            user_prompt,
            re.DOTALL,
        )

        rag_section = user_prompt.split("### DOCUMENTOS", 1)[1] if "### DOCUMENTOS" in user_prompt else ""
        source_header_match = re.search(r"1\.\s*\[[^\]]+\]\s*\*\*(.+?)\*\*\s*-\s*(.+?):", rag_section)
        snippet_match = re.search(r'^\s*"(.+?)"\s*$', rag_section, re.MULTILINE)

        # Caso 1: Existe código de error explícito -> diagnóstico técnico estructurado en 4 secciones
        if code_match:
            error_code = code_match.group(1).strip()
            phase_info = phase_match.group(1).strip() if phase_match else "Validación Técnica"
            field_info = field_match.group(1).strip() if field_match else "Campo reportado"
            formato = format_match.group(1).strip() if format_match else "recurso activo"

            if source_header_match and snippet_match:
                doc_title = source_header_match.group(1).strip()
                doc_section = source_header_match.group(2).strip()
                rule_snippet = snippet_match.group(1).strip()
                normative_ref = f"{doc_title} - {doc_section}."
            else:
                rule_snippet = (
                    "El campo o registro reportado debe cumplir con el tipo de dato, catálogo de valores "
                    "y reglas de validación definidos en la documentación técnica aplicable."
                )
                normative_ref = "Documentación técnica y manual de validación recuperado por el buscador."

            return (
                f"### 1. Diagnóstico:\n"
                f"Se identificó una inconsistencia (`{error_code}`) en **{phase_info}** asociada a **{field_info}** "
                f"en `{formato}`.\n\n"
                f"### 2. Regla Técnica:\n"
                f"{rule_snippet}\n\n"
                f"### 3. Pasos de Solución:\n"
                f"1. Ubique el registro o campo señalado en `{formato}`.\n"
                f"2. Ajuste el valor conforme a la regla técnica y los lineamientos vigentes.\n"
                f"3. Verifique la estructura y formato general antes de guardar.\n"
                f"4. Ejecute nuevamente el proceso o validación en la plataforma.\n\n"
                f"### 4. Fundamento Normativo:\n"
                f"{normative_ref}"
            )

        # Caso 2: Consulta general con fragmentos RAG -> respuesta directa citando la fuente
        if source_header_match and snippet_match:
            query_text = query_match.group(1).strip() if query_match else "su consulta"
            doc_title = source_header_match.group(1).strip()
            doc_section = source_header_match.group(2).strip()
            rule_snippet = snippet_match.group(1).strip()
            return (
                f'De acuerdo con la documentación disponible para "{query_text}":\n\n'
                f"{rule_snippet}\n\n"
                f"**Pasos recomendados:**\n"
                f"1. Verifique los requisitos aplicables en el módulo correspondiente de la plataforma.\n"
                f"2. Confirme que los datos ingresados cumplan con los lineamientos indicados.\n\n"
                f"**Fuente:** {doc_title} - {doc_section}."
            )

        # Caso 3: Sin fragmentos RAG o prompt directo corto -> respuesta neutral de contingencia
        clean_query = (
            query_match.group(1).strip()
            if query_match
            else (user_prompt.strip().splitlines()[-1][:160] if user_prompt.strip() else "su solicitud")
        )
        return (
            f'Respecto a su consulta ("{clean_query}"), el motor de lenguaje opera en modo de '
            f"contingencia local. Por favor revise la guía operativa o consulte con el área de soporte "
            f"de la plataforma para validar los detalles específicos aplicables."
        )

    _generate_simulated_clinical_response = _generate_simulated_response
