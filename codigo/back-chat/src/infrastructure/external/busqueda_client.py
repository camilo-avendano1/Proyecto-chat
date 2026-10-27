"""
Client adapter for Back - Busqueda (Retrieval & Vector Search Service).
Implements SearchServiceProtocol.
Connects via HTTPX AsyncClient to BACK_BUSQUEDA_URL.
Includes fallback knowledge base for high availability and offline development.
"""

import logging
import re
import uuid
from typing import Any, Dict, List, Optional
import httpx

from src.config import settings
from src.domain.entities import KnowledgeSource
from src.domain.value_objects import KnowledgeScope
from src.operations.interfaces import SearchServiceProtocol

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Límites de seguridad del campo `extras` (metadatos específicos por cliente)
# ---------------------------------------------------------------------------
EXTRAS_MAX_KEYS = 20
EXTRAS_MAX_STR_LEN = 500
EXTRAS_KEY_REGEX = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_ALLOWED_SCALARS = (str, int, float, bool)


def sanitize_extras(extras: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Normaliza y valida los metadatos opcionales enviados a la API de búsqueda.
    - Solo claves snake_case seguras (evita inyección de claves arbitrarias).
    - Solo valores escalares (str, int, float, bool) o listas planas de escalares.
    - Sin objetos anidados, sin None, strings truncados y número de claves acotado.
    Las entradas inválidas se descartan silenciosamente (y se registran en debug).
    """
    clean: Dict[str, Any] = {}
    for key, value in (extras or {}).items():
        if len(clean) >= EXTRAS_MAX_KEYS:
            break
        if not isinstance(key, str) or not EXTRAS_KEY_REGEX.match(key):
            logger.debug("extras: clave descartada %r", key)
            continue
        if value is None:
            continue
        if isinstance(value, _ALLOWED_SCALARS):
            clean[key] = value[:EXTRAS_MAX_STR_LEN] if isinstance(value, str) else value
        elif isinstance(value, (list, tuple)) and all(isinstance(v, _ALLOWED_SCALARS) for v in value):
            clean[key] = [v[:EXTRAS_MAX_STR_LEN] if isinstance(v, str) else v for v in value][:EXTRAS_MAX_KEYS]
        else:
            logger.debug("extras: valor no permitido para %r", key)
    return clean


# Contingency Knowledge Bank (Fallback ONLY when back-busqueda microservice is offline)
# In production, all situations, documents, forms, and regulations come dynamically from back-busqueda.
BUILTIN_KNOWLEDGE_BANK = [
    {
        "keywords": ["formulario", "enfermeria", "signos vitales", "nota", "historia clinica", "formato clinico"],
        "title": "Reglamento Técnico de Formularios Clínicos y de Enfermería",
        "scope": KnowledgeScope.GLOBAL,
        "section": "Validación de Campos Obligatorios y Rangos Fisiológicos",
        "snippet": "Todo formulario clínico o registro de enfermería debe incluir identificación del profesional, fecha/hora en formato ISO (AAAA-MM-DD HH:MM) y valores dentro de rangos clínicos válidos antes de su radicación."
    },
    {
        "keywords": ["delimitador", "pipeline", "pipe", "csv", "txt", "xml", "json", "fase 1", "ca_", "columnas", "estructura"],
        "title": "Lineamientos Técnicos de Estructura y Formatos de Cargue",
        "scope": KnowledgeScope.ACCOUNT,
        "section": "Fase 1: Calidad de Archivo y Formato (CA)",
        "snippet": "El archivo o formulario debe respetar el delimitador y esquema definido por el reglamento del formato (TXT, CSV, XML o JSON), codificación UTF-8 sin caracteres de control inválidos y el número exacto de campos exigidos por la plantilla."
    },
    {
        "keywords": ["fecha", "nacimiento", "futura", "rango", "formato fecha", "aaaa-mm-dd", "ca_var_009", "var_009"],
        "title": "Manual de Validación de Estructura de Campos",
        "scope": KnowledgeScope.GLOBAL,
        "section": "Fase 2: Validación de Fechas y Tipos de Dato (CE)",
        "snippet": "Los campos de tipo fecha deben registrarse en el formato exigido por el reglamento del formulario (ej. AAAA-MM-DD) y ser cronológicamente coherentes con el periodo de reporte; no se admiten fechas posteriores al corte."
    },
    {
        "keywords": ["rips", "3374", "2275", "facturacion", "consulta rips", "cie-10", "cups"],
        "title": "Reglamento Técnico de Soportes y Registros RIPS",
        "scope": KnowledgeScope.GLOBAL,
        "section": "Coherencia de Códigos de Prestación (CUPS) y Diagnóstico (CIE-10)",
        "snippet": "En los formularios y archivos de facturación y RIPS, el código del servicio o procedimiento debe guardar coherencia normativa con el diagnóstico principal CIE-10, la edad y el sexo del paciente."
    },
    {
        "keywords": ["14", "gestante", "embarazo", "condicion_usuaria", "ce_var_014"],
        "title": "Anexo Técnico Normativo - Reglas de Coherencia por Sexo y Condición",
        "scope": KnowledgeScope.GLOBAL,
        "section": "Validación de Campo Condición de la Usuaria / Gestante (Campo 14)",
        "snippet": "Campo/Variable 14 (Condición de la Usuaria): Cuando el campo de Sexo reporta Masculino ('M'), la condición de gestación debe registrarse como 'No aplica' (0). Reportar valores de gestante en sexo masculino genera rechazo de validación."
    },
    {
        "keywords": ["11", "sexo", "masculino", "femenino", "mayuscula"],
        "title": "Anexo Técnico Normativo - Catálogos de Identificación",
        "scope": KnowledgeScope.GLOBAL,
        "section": "Validación del Campo Sexo / Género",
        "snippet": "El campo de Sexo debe diligenciarse únicamente con los códigos permitidos en el catálogo oficial del reglamento en letra mayúscula sostenida."
    },
]

DEFAULT_FALLBACK_SOURCE = {
    "title": "Guía General de Validación de Formularios y Reglamentos Técnicos",
    "scope": KnowledgeScope.GLOBAL,
    "section": "Reglas Generales de Diligenciamiento y Cargue de Formatos",
    "snippet": (
        "Verifique que cada campo del formulario o archivo cumpla con el tipo de dato, "
        "catálogo de valores permitidos, formato de fecha y reglas de coherencia cruzada "
        "establecidos en el reglamento técnico correspondiente al formato que está subiendo."
    ),
}


class BusquedaHttpClient(SearchServiceProtocol):
    """
    HTTP client for querying the Back - Busqueda retrieval microservice.
    If the service is unavailable or in local fallback mode, leverages
    the built-in Colombian Healthcare Knowledge Bank.
    """

    def __init__(
        self,
        base_url: str = settings.BACK_BUSQUEDA_URL,
        timeout: float = settings.BACK_BUSQUEDA_TIMEOUT_SECONDS,
        fallback_enabled: bool = settings.FALLBACK_LOCAL_SEARCH,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.fallback_enabled = fallback_enabled

    async def search(
        self,
        query: str,
        client_id: Optional[str] = "sigires",
        busqueda_api_url: Optional[str] = None,
        tenant_id: Optional[str] = None,
        category: Optional[str] = None,
        variable_num: Optional[int] = None,
        error_code: Optional[str] = None,
        top_k: int = 5,
    ) -> List[KnowledgeSource]:
        """
        Sends search request to the client-specific Back - Busqueda service.
        Falls back to local knowledge base if remote service is unreachable.
        """
        sources = []

        # Determine target search API URL for this client
        target_url = busqueda_api_url or settings.CLIENT_BUSQUEDA_URLS.get(
            client_id or "sigires", self.base_url
        )
        target_url = target_url.rstrip("/")

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                # Contrato genérico: núcleo fijo + `extras` dependientes del cliente
                payload = {
                    "query": query,
                    "client_id": client_id,
                    "tenant_id": tenant_id,
                    "top_k": top_k,
                    "extras": sanitize_extras({
                        "category": category,
                        "variable_number": variable_num,
                        "error_code": error_code,
                    }),
                }
                headers = {
                    "X-Internal-Key": settings.BUSQUEDA_SERVICE_KEY,
                    "X-Request-ID": str(uuid.uuid4()),
                }
                response = await client.post(
                    f"{target_url}/api/v1/search",
                    json=payload,
                    headers=headers,
                )
                if response.status_code == 200:
                    data = response.json()
                    raw_chunks = data.get("chunks", data.get("results", []))
                    for item in raw_chunks:
                        sources.append(
                            KnowledgeSource(
                                document_title=item.get("title", item.get("document_title", "Documento Normativo")),
                                scope=KnowledgeScope(item.get("scope", "GLOBAL")),
                                section=item.get("section", "General"),
                                score=item.get("score", 1.0),
                                snippet=item.get("content", item.get("snippet", "")),
                            )
                        )
                    if sources:
                        return sources[:top_k]
        except Exception as exc:
            logger.warning(
                f"Servicio de Búsqueda no disponible en {target_url} para el cliente '{client_id}' ({exc}). "
                "Activando motor de conocimiento local de contingencia."
            )

        if self.fallback_enabled:
            sources = self._local_search(query, variable_num, error_code, top_k)

        return sources

    def _local_search(
        self,
        query: str,
        variable_num: Optional[int],
        error_code: Optional[str],
        top_k: int = 5
    ) -> List[KnowledgeSource]:
        """Local keyword and variable matching heuristic."""
        search_terms = query.lower()
        if error_code:
            search_terms += f" {error_code.lower()}"
        if variable_num:
            search_terms += f" {variable_num}"

        matched = []
        for item in BUILTIN_KNOWLEDGE_BANK:
            score = 0.0
            for kw in item["keywords"]:
                if kw in search_terms:
                    score += 1.0

            if variable_num and str(variable_num) in item["keywords"]:
                score += 3.0  # High priority match for specific variable

            if score > 0:
                matched.append((
                    score,
                    KnowledgeSource(
                        document_title=item["title"],
                        scope=item["scope"],
                        section=item["section"],
                        score=round(min(1.0, 0.5 + (score * 0.1)), 2),
                        snippet=item["snippet"],
                    )
                ))

        # Sort by relevance score descending
        matched.sort(key=lambda x: x[0], reverse=True)
        results = [m[1] for m in matched[:top_k]]

        # Default neutral fallback if no specific keyword matched (never force a specific case like Var 14)
        if not results:
            results.append(
                KnowledgeSource(
                    document_title=DEFAULT_FALLBACK_SOURCE["title"],
                    scope=DEFAULT_FALLBACK_SOURCE["scope"],
                    section=DEFAULT_FALLBACK_SOURCE["section"],
                    score=0.7,
                    snippet=DEFAULT_FALLBACK_SOURCE["snippet"],
                )
            )

        return results
