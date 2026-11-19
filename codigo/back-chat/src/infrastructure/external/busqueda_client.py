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
from src.infrastructure.repositories.document_repo import get_document_repository
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
        "scope": KnowledgeScope.ORGANIZATION,
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
    "title": "Base de Conocimiento General (Modo Contingencia)",
    "scope": KnowledgeScope.GLOBAL,
    "section": "Orientación General",
    "snippet": (
        "El servicio de búsqueda documental del cliente no se encuentra disponible temporalmente. "
        "La respuesta se basa únicamente en el contexto proporcionado en la consulta."
    ),
}


class BusquedaHttpClient(SearchServiceProtocol):
    """
    HTTP client for querying the Back - Busqueda retrieval microservice.
    If the service is unavailable or in local fallback mode, leverages
    the built-in contingency knowledge bank.
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
        org_id: Optional[str] = None,
        busqueda_api_url: Optional[str] = None,
        site_id: Optional[str] = None,
        category: Optional[str] = None,
        variable_num: Optional[int] = None,
        error_code: Optional[str] = None,
        extras: Optional[Dict[str, Any]] = None,
        top_k: int = 5,
    ) -> List[KnowledgeSource]:
        """
        Sends search request to the organization-specific Back - Busqueda service.
        Falls back to local knowledge base if remote service is unreachable.
        """
        sources = []

        # Determine target search API URL for this organization
        target_url = (
            busqueda_api_url
            or settings.ORG_BUSQUEDA_URLS.get(org_id or "default")
            or settings.ORG_BUSQUEDA_URLS.get("default")
            or self.base_url
        )
        target_url = target_url.rstrip("/")

        merged_extras: Dict[str, Any] = dict(extras or {})
        if category is not None:
            merged_extras.setdefault("category", category)
        if variable_num is not None:
            merged_extras.setdefault("variable_number", variable_num)
        if error_code is not None:
            merged_extras.setdefault("error_code", error_code)

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                # Contrato genérico: núcleo fijo + `extras` dependientes de la organización
                payload = {
                    "query": query,
                    "org_id": org_id,
                    "site_id": site_id,
                    "top_k": top_k,
                    "extras": sanitize_extras(merged_extras),
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
                        raw_scope = str(item.get("scope") or "GLOBAL").upper()
                        try:
                            parsed_scope = KnowledgeScope(raw_scope)
                        except ValueError:
                            parsed_scope = KnowledgeScope.GLOBAL
                        sources.append(
                            KnowledgeSource(
                                document_title=item.get("title", item.get("document_title", "Documento de Referencia")),
                                scope=parsed_scope,
                                section=item.get("section", "General"),
                                score=item.get("score", 1.0),
                                snippet=item.get("content", item.get("snippet", "")),
                            )
                        )
                    if sources:
                        return sources[:top_k]
        except Exception as exc:
            logger.warning(
                f"Servicio de Búsqueda no disponible en {target_url} para la organización '{org_id}' ({exc}). "
                "Activando motor de conocimiento local de contingencia."
            )

        if self.fallback_enabled:
            sources = self._local_search(
                query,
                variable_num,
                error_code,
                top_k,
                org_id=org_id,
                site_id=site_id,
            )

        return sources

    def _local_search(
        self,
        query: str,
        variable_num: Optional[int],
        error_code: Optional[str],
        top_k: int = 5,
        org_id: Optional[str] = None,
        site_id: Optional[str] = None,
    ) -> List[KnowledgeSource]:
        """Local uploaded knowledge search first, falling back to built-in contingency bank."""
        uploaded_matches = get_document_repository().search_chunks(
            query=query,
            org_id=org_id,
            site_id=site_id,
            top_k=top_k,
        )
        if uploaded_matches:
            uploaded_sources: List[KnowledgeSource] = []
            for item in uploaded_matches:
                raw_scope = str(item.get("scope") or "GLOBAL").upper()
                try:
                    parsed_scope = KnowledgeScope(raw_scope)
                except ValueError:
                    parsed_scope = KnowledgeScope.GLOBAL
                snippet_text = " ".join(str(item.get("content", "")).splitlines()).strip()
                uploaded_sources.append(
                    KnowledgeSource(
                        document_title=item.get("title", "Documento de Referencia"),
                        scope=parsed_scope,
                        section=item.get("section", "General"),
                        score=float(item.get("score", 0.9)),
                        snippet=snippet_text,
                    )
                )
            return uploaded_sources[:top_k]

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
