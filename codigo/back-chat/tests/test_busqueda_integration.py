"""
Tests for Back - Busqueda client adapter, multi-organization routing, and fallback knowledge base.
"""

from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from src.domain.value_objects import KnowledgeScope
from src.infrastructure.external.busqueda_client import BusquedaHttpClient


@pytest.mark.asyncio
async def test_busqueda_client_local_fallback():
    client = BusquedaHttpClient(
        base_url="http://non-existent-host:9999",
        fallback_enabled=True,
    )
    sources = await client.search(
        query="Error en el formulario de enfermeria signos vitales",
        org_id="sigires",
        top_k=3,
    )

    assert len(sources) > 0
    first = sources[0]
    assert "Formularios Clínicos" in first.document_title or "Enfermería" in first.document_title
    assert first.snippet is not None
    assert len(first.snippet) > 20


@pytest.mark.asyncio
async def test_busqueda_client_unmatched_query_returns_neutral_guide_not_specific_case():
    client = BusquedaHttpClient(
        base_url="http://non-existent-host:9999",
        fallback_enabled=True,
    )
    sources = await client.search(
        query="Consulta general sobre un documento nuevo",
        org_id="otra_empresa",
        busqueda_api_url="http://otra-empresa-search:8002",
        top_k=2,
    )
    assert len(sources) > 0
    assert "Variable 14" not in sources[0].section
    assert "Base de Conocimiento General" in sources[0].document_title


@pytest.mark.asyncio
async def test_busqueda_client_pipeline_delimiter_query():
    client = BusquedaHttpClient(
        base_url="http://non-existent-host:9999",
        fallback_enabled=True,
    )
    sources = await client.search(
        query="El delimitador pipeline o pipe tiene error en fase 1",
        top_k=2,
    )

    assert len(sources) > 0
    assert any("delimitador" in s.snippet.lower() or "pipeline" in s.snippet.lower() for s in sources)


@pytest.mark.asyncio
async def test_busqueda_client_http_general_query_sends_empty_extras():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "results": [
            {
                "title": "Manual de Compras",
                "scope": "ORGANIZATION",
                "section": "Aprobaciones",
                "content": "Toda orden de compra requiere aprobación de gerencia.",
            }
        ]
    }
    mock_post = AsyncMock(return_value=mock_resp)

    with patch("httpx.AsyncClient.post", new=mock_post):
        client = BusquedaHttpClient(base_url="http://mock-busqueda:8001", fallback_enabled=False)
        sources = await client.search(
            query="¿Cómo se aprueba una orden de compra?",
            org_id="otra_empresa",
            site_id="site_1",
            top_k=4,
        )

    assert len(sources) == 1
    assert sources[0].document_title == "Manual de Compras"
    assert sources[0].scope == KnowledgeScope.ORGANIZATION
    sent_payload = mock_post.call_args.kwargs["json"]
    assert sent_payload["extras"] == {}
    assert sent_payload["org_id"] == "otra_empresa"
    assert sent_payload["site_id"] == "site_1"


@pytest.mark.asyncio
async def test_busqueda_client_http_sanitizes_and_forwards_custom_extras():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "results": [
            {
                "title": "Política Corporativa",
                "scope": "SITE",
                "section": "General",
                "content": "Regla vigente.",
            }
        ]
    }
    mock_post = AsyncMock(return_value=mock_resp)

    with patch("httpx.AsyncClient.post", new=mock_post):
        client = BusquedaHttpClient(base_url="http://mock-busqueda:8001", fallback_enabled=False)
        sources = await client.search(
            query="Consulta con filtros",
            org_id="otra_empresa",
            category="CAT_CUSTOM",
            extras={
                "modulo": "compras",
                "BadKey": "should_drop",
                "invalid.key": "should_drop",
                "nested": {"a": 1},
                "long_str": "x" * 600,
            },
        )

    assert len(sources) == 1
    assert sources[0].scope == KnowledgeScope.SITE
    sent_extras = mock_post.call_args.kwargs["json"]["extras"]
    assert sent_extras["modulo"] == "compras"
    assert sent_extras["category"] == "CAT_CUSTOM"
    assert len(sent_extras["long_str"]) == 500
    assert "BadKey" not in sent_extras
    assert "invalid.key" not in sent_extras
    assert "nested" not in sent_extras


@pytest.mark.asyncio
async def test_busqueda_client_http_unknown_scope_falls_back_to_global():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "results": [
            {
                "title": "Guía Externa",
                "scope": "CUSTOM_UNKNOWN_SCOPE",
                "section": "Sección 1",
                "content": "Contenido de prueba.",
            }
        ]
    }
    mock_post = AsyncMock(return_value=mock_resp)

    with patch("httpx.AsyncClient.post", new=mock_post):
        client = BusquedaHttpClient(base_url="http://mock-busqueda:8001", fallback_enabled=False)
        sources = await client.search(query="Consulta cualquiera", org_id="otra_empresa")

    assert len(sources) == 1
    assert sources[0].scope == KnowledgeScope.GLOBAL
