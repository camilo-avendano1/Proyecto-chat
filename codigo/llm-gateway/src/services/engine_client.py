"""
Cliente de inferencia LLM (LM Studio, Ollama, OpenAI, DeepSeek) con contingencia simulada.
Calcula tokens reales reportados por el proveedor (o heurísticos) y costos en USD.
"""

import asyncio
from dataclasses import dataclass
import json
import logging
import re
import time
from typing import Any, AsyncGenerator, Dict, List, Optional
import httpx

from src.config import settings

logger = logging.getLogger("llm_gateway.engine")


@dataclass
class GenerationResult:
    text: str
    tokens_input: int
    tokens_output: int
    tokens_total: int
    costo_usd: float
    model_used: str
    provider_used: str
    token_source: str  # "provider" or "estimated"
    latency_ms: int


class EngineClient:
    def __init__(
        self,
        api_key: str = settings.LLM_API_KEY,
        base_url: str = settings.LLM_BASE_URL,
        model: str = settings.LLM_MODEL,
        provider: str = settings.LLM_PROVIDER,
        temperature: float = settings.LLM_TEMPERATURE,
        max_tokens: int = settings.LLM_MAX_TOKENS,
        fallback_on_error: bool = settings.FALLBACK_SIMULATION_ON_LLM_ERROR,
    ):
        self.api_key = api_key or "lm-studio"
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.provider = provider
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.fallback_on_error = fallback_on_error

    def _calculate_cost(self, tokens_in: int, tokens_out: int, model: str) -> float:
        # Modelos locales en LM Studio / Ollama no tienen costo de facturación por token
        if self.provider in ("lmstudio", "ollama") or "local" in model.lower():
            return 0.0
        cost_in = (tokens_in / 1_000_000.0) * settings.INPUT_TOKEN_PRICE_PER_M
        cost_out = (tokens_out / 1_000_000.0) * settings.OUTPUT_TOKEN_PRICE_PER_M
        return round(cost_in + cost_out, 6)

    async def generate_response(
        self,
        system_prompt: str,
        user_prompt: str,
        history: Optional[List[Dict[str, str]]] = None,
        model_override: Optional[str] = None,
    ) -> GenerationResult:
        start_time = time.perf_counter()
        target_model = model_override or self.model

        messages = [{"role": "system", "content": system_prompt}]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": user_prompt})

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": target_model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "stream": False,
        }

        try:
            async with httpx.AsyncClient(timeout=35.0) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                latency_ms = int((time.perf_counter() - start_time) * 1000)

                # Extraer métricas de tokens si están presentes
                usage = data.get("usage", {})
                if usage and "prompt_tokens" in usage:
                    tokens_in = usage.get("prompt_tokens", 0)
                    tokens_out = usage.get("completion_tokens", 0)
                    token_source = "provider"
                else:
                    tokens_in = max(1, (len(system_prompt) + len(user_prompt)) // 4)
                    tokens_out = max(1, len(content) // 4)
                    token_source = "estimated"

                cost = self._calculate_cost(tokens_in, tokens_out, target_model)
                return GenerationResult(
                    text=content,
                    tokens_input=tokens_in,
                    tokens_output=tokens_out,
                    tokens_total=tokens_in + tokens_out,
                    costo_usd=cost,
                    model_used=target_model,
                    provider_used=self.provider,
                    token_source=token_source,
                    latency_ms=latency_ms,
                )

        except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError) as exc:
            logger.warning(
                f"No se pudo contactar al servidor LLM en {self.base_url} ({exc}). "
                "Activando motor de inferencia simulado de contingencia."
            )
            if self.fallback_on_error:
                simulated_text = self._generate_simulated_response(user_prompt)
                latency_ms = int((time.perf_counter() - start_time) * 1000)
                tokens_in = max(1, (len(system_prompt) + len(user_prompt)) // 4)
                tokens_out = max(1, len(simulated_text) // 4)
                return GenerationResult(
                    text=simulated_text,
                    tokens_input=tokens_in,
                    tokens_output=tokens_out,
                    tokens_total=tokens_in + tokens_out,
                    costo_usd=0.0,
                    model_used="simulated-fallback",
                    provider_used="contingency-engine",
                    token_source="estimated",
                    latency_ms=latency_ms,
                )
            raise

    async def generate_stream(
        self,
        system_prompt: str,
        user_prompt: str,
        history: Optional[List[Dict[str, str]]] = None,
        model_override: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        target_model = model_override or self.model
        messages = [{"role": "system", "content": system_prompt}]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": user_prompt})

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": target_model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "stream": True,
        }

        stream_failed = False
        try:
            async with httpx.AsyncClient(timeout=45.0) as client:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload
                ) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if not line:
                            continue
                        if line.startswith("data: "):
                            data_str = line[6:].strip()
                            if data_str == "[DONE]":
                                break
                            try:
                                chunk_json = json.loads(data_str)
                                delta = chunk_json["choices"][0].get("delta", {})
                                content = delta.get("content")
                                if content:
                                    yield content
                            except json.JSONDecodeError:
                                continue
        except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError) as exc:
            logger.warning(
                f"Error al conectar con servidor LLM en streaming {self.base_url} ({exc}). "
                "Emitiendo respuesta de contingencia simulada."
            )
            stream_failed = True

        if stream_failed and self.fallback_on_error:
            simulated_text = self._generate_simulated_response(user_prompt)
            words = simulated_text.split(" ")
            for i, word in enumerate(words):
                chunk = word + (" " if i < len(words) - 1 else "")
                yield chunk
                await asyncio.sleep(0.01)

    @staticmethod
    def _extract_clean_query(query_match: Optional[re.Match], user_prompt: str) -> str:
        if query_match:
            raw_query = query_match.group(1)
        else:
            non_empty_lines = [line.strip() for line in user_prompt.splitlines() if line.strip()]
            raw_query = non_empty_lines[-1] if non_empty_lines else "consulta general"
        raw_query = raw_query.strip()
        if len(raw_query) >= 2 and raw_query[0] == raw_query[-1] and raw_query[0] in ('"', "'"):
            raw_query = raw_query[1:-1].strip()
        else:
            raw_query = raw_query.strip('"').strip()
        return raw_query[:160] or "consulta general"

    def _generate_simulated_response(self, user_prompt: str) -> str:
        """
        Genera una respuesta de contingencia adaptativa a partir del contexto y fragmentos
        de búsqueda presentes en `user_prompt` cuando el motor LLM principal no está activo.
        """
        code_match = re.search(r"-\s*Código de Error:\s*(.+)", user_prompt)
        phase_match = re.search(r"-\s*Fase / Categoría de Validación:\s*(.+)", user_prompt)
        field_match = re.search(r"-\s*Campo / Variable / Columna Afectada:\s*(.+)", user_prompt)
        format_match = re.search(
            r"-\s*(?:Formato de Formulario o Archivo|formato_archivo|file_format):\s*(.+)",
            user_prompt,
        )
        query_match = re.search(
            r'CONSULTA DEL (?:USUARIO|PROFESIONAL):\s*\n\s*"?(.+?)"?\s*(?:\n|$)',
            user_prompt,
        )

        source_header_match = re.search(r"1\.\s*\[[^\]]+\]\s*\*\*(.+?)\*\*\s*-\s*(.+?):", user_prompt)
        snippet_match = (
            re.search(r'^\s*"(.+?)"\s*$', user_prompt[source_header_match.end():], re.MULTILINE)
            if source_header_match
            else None
        )

        # Caso 1: Diagnóstico técnico con código de error y fragmento RAG recuperado
        if code_match and source_header_match and snippet_match:
            error_code = code_match.group(1).strip()
            phase_info = phase_match.group(1).strip() if phase_match else "Validación de Estructura"
            field_info = field_match.group(1).strip() if field_match else "Campo reportado"
            formato = format_match.group(1).strip() if format_match else None
            doc_title = source_header_match.group(1).strip()
            doc_section = source_header_match.group(2).strip()
            rule_snippet = snippet_match.group(1).strip()

            formato_diag = f" en el formato `{formato}`" if formato else ""
            formato_step = f" (`{formato}`)" if formato else ""

            return (
                f"### 1. Diagnóstico:\n"
                f"Se identificó una inconsistencia (`{error_code}`) en **{phase_info}** asociada a **{field_info}**"
                f"{formato_diag}.\n\n"
                f"### 2. Regla Técnica:\n"
                f"{rule_snippet}\n\n"
                f"### 3. Pasos de Solución:\n"
                f"1. Ubique el registro o campo señalado{formato_step}.\n"
                f"2. Ajuste el valor conforme a la regla técnica de la documentación recuperada.\n"
                f"3. Verifique la estructura y vuelva a validar la operación.\n\n"
                f"### 4. Fundamento Normativo:\n"
                f"{doc_title} - {doc_section}."
            )

        # Caso 2: Consulta RAG general sin código de error
        if source_header_match and snippet_match:
            doc_title = source_header_match.group(1).strip()
            doc_section = source_header_match.group(2).strip()
            rule_snippet = snippet_match.group(1).strip()
            query_text = self._extract_clean_query(query_match, user_prompt) if query_match else None

            intro = (
                f"Con respecto a su consulta (\"{query_text}\"), según la documentación recuperada:\n\n"
                if query_text
                else "Según la documentación recuperada:\n\n"
            )
            return (
                f"{intro}"
                f"{rule_snippet}\n\n"
                f"**Fuente:** {doc_title} - {doc_section}."
            )

        # Caso 3: Prompt corto directo o sin fragmento RAG recuperado
        clean_summary = self._extract_clean_query(query_match, user_prompt)
        return (
            f"Consulta recibida sobre: \"{clean_summary}\".\n\n"
            f"El motor de lenguaje principal no se encuentra disponible temporalmente (respuesta de contingencia). "
            f"Por favor, revise la documentación vigente provista por el servicio de búsqueda o intente nuevamente más tarde."
        )

    _generate_simulated_clinical_response = _generate_simulated_response
