"""
LLM client adapter supporting Local LM Studio, Ollama, OpenAI, DeepSeek, and fallbacks.
Implements LLMServiceProtocol.
Supports streaming token generation (SSE) and full response generation.
"""

import asyncio
import json
import logging
from typing import Any, AsyncGenerator, Dict, List, Optional
import httpx

from src.config import settings
from src.operations.interfaces import LLMServiceProtocol

logger = logging.getLogger(__name__)


class HttpLLMClient(LLMServiceProtocol):
    """
    Client for OpenAI-compatible chat completion APIs with streaming.
    Supports:
    1. Local LM Studio: http://localhost:1234/v1
    2. Local Ollama:    http://localhost:11434/v1
    3. Production:      https://api.openai.com/v1 (or DeepSeek / Azure)
    """

    def __init__(
        self,
        api_key: str = settings.LLM_API_KEY,
        base_url: str = settings.LLM_BASE_URL,
        model: str = settings.LLM_MODEL,
        temperature: float = settings.LLM_TEMPERATURE,
        max_tokens: int = settings.LLM_MAX_TOKENS,
        fallback_on_error: bool = settings.FALLBACK_SIMULATION_ON_LLM_ERROR,
    ):
        self.api_key = api_key or "lm-studio"
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.fallback_on_error = fallback_on_error

    async def generate_response(
        self,
        system_prompt: str,
        user_prompt: str,
        history: Optional[List[Dict[str, str]]] = None,
    ) -> str:
        messages = [{"role": "system", "content": system_prompt}]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": user_prompt})

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "stream": False,
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload
                )
                response.raise_for_status()
                data = response.json()
                return data["choices"][0]["message"]["content"]
        except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError) as exc:
            logger.warning(
                f"No se pudo contactar al servidor LLM en {self.base_url} ({exc}). "
                "Si estás usando LM Studio, asegúrate de haber presionado 'Start Server' en el puerto 1234. "
                "Activando motor de inferencia simulado de contingencia."
            )
            if self.fallback_on_error:
                return self._generate_simulated_clinical_response(user_prompt)
            raise

    async def generate_stream(
        self,
        system_prompt: str,
        user_prompt: str,
        history: Optional[List[Dict[str, str]]] = None,
    ) -> AsyncGenerator[str, None]:
        messages = [{"role": "system", "content": system_prompt}]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": user_prompt})

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
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
                f"No se pudo conectar al servidor LLM en {self.base_url} ({exc}). "
                "Si estás usando LM Studio, verifica que el Local Server esté activo en el puerto 1234. "
                "Emitiendo respuesta del motor simulado."
            )
            stream_failed = True

        if stream_failed and self.fallback_on_error:
            simulated_text = self._generate_simulated_clinical_response(user_prompt)
            words = simulated_text.split(" ")
            for i, word in enumerate(words):
                chunk = word + (" " if i < len(words) - 1 else "")
                yield chunk
                await asyncio.sleep(0.01)

    def _generate_simulated_clinical_response(self, user_prompt: str) -> str:
        """
        Generates a structured technical response based dynamically on the search context
        and metadata injected in user_prompt when the LLM server is offline.
        Never hardcodes a specific client case or regulation.
        """
        import re

        code_match = re.search(r"-\s*Código de Error:\s*(.+)", user_prompt)
        phase_match = re.search(r"-\s*Fase / Categoría de Validación:\s*(.+)", user_prompt)
        field_match = re.search(r"-\s*Campo / Variable / Columna Afectada:\s*(.+)", user_prompt)
        format_match = re.search(r"-\s*Formato de Formulario o Archivo:\s*(.+)", user_prompt)

        source_header_match = re.search(r"1\.\s*\[[^\]]+\]\s*\*\*(.+?)\*\*\s*-\s*(.+?):", user_prompt)
        snippet_match = re.search(r'^\s*"(.+?)"\s*$', user_prompt, re.MULTILINE)

        error_code = code_match.group(1).strip() if code_match else "VALIDACION_TECNICA"
        phase_info = phase_match.group(1).strip() if phase_match else "Validación de Estructura"
        field_info = field_match.group(1).strip() if field_match else "Campo reportado"
        formato = format_match.group(1).strip() if format_match else "formulario activo"

        if source_header_match and snippet_match:
            doc_title = source_header_match.group(1).strip()
            doc_section = source_header_match.group(2).strip()
            rule_snippet = snippet_match.group(1).strip()
            normative_ref = f"{doc_title} - {doc_section}."
        else:
            rule_snippet = (
                "El campo o registro reportado debe cumplir con el tipo de dato, catálogo de valores "
                "y reglas de coherencia definidos en el reglamento técnico del formulario."
            )
            normative_ref = "Reglamento técnico y manual de validación recuperado por el buscador."

        return (
            f"### 1. Diagnóstico:\n"
            f"Se identificó una inconsistencia (`{error_code}`) en **{phase_info}** asociada a **{field_info}** "
            f"en el formato `{formato}`.\n\n"
            f"### 2. Regla Técnica:\n"
            f"{rule_snippet}\n\n"
            f"### 3. Pasos de Solución:\n"
            f"1. Ubique el registro o campo señalado en su formulario o archivo (`{formato}`).\n"
            f"2. Ajuste el valor conforme a la regla técnica y catálogo del reglamento vigente.\n"
            f"3. Verifique la codificación y estructura general del formato antes de guardar.\n"
            f"4. Vuelva a validar o cargar el formulario en la plataforma.\n\n"
            f"### 4. Fundamento Normativo:\n"
            f"{normative_ref}"
        )
