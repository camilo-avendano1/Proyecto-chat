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
        **kwargs: Any,
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
                return self._generate_simulated_response(user_prompt)
            raise

    async def generate_stream(
        self,
        system_prompt: str,
        user_prompt: str,
        history: Optional[List[Dict[str, str]]] = None,
        **kwargs: Any,
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
            simulated_text = self._generate_simulated_response(user_prompt)
            words = simulated_text.split(" ")
            for i, word in enumerate(words):
                chunk = word + (" " if i < len(words) - 1 else "")
                yield chunk
                await asyncio.sleep(0.01)

    def _generate_simulated_response(self, user_prompt: str) -> str:
        """
        Generates an adaptive contingency response when the LLM server is offline:
        1. Error code present -> 4-section technical diagnosis.
        2. RAG snippet without error code -> direct answer citing snippet.
        3. No snippet / short prompt -> neutral contingency response addressing the user's query.
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
