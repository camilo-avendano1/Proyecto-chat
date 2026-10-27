"""
Tests for Back - Busqueda client adapter, multi-client routing, and fallback knowledge base.
"""

import pytest
from src.infrastructure.external.busqueda_client import BusquedaHttpClient


@pytest.mark.asyncio
async def test_busqueda_client_local_fallback():
    client = BusquedaHttpClient(
        base_url="http://non-existent-host:9999",
        fallback_enabled=True
    )
    sources = await client.search(
        query="Error en el formulario de enfermeria signos vitales",
        client_id="sigires",
        top_k=3
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
        fallback_enabled=True
    )
    sources = await client.search(
        query="Consulta general sobre un documento nuevo",
        client_id="otra_empresa",
        busqueda_api_url="http://otra-empresa-search:8002",
        top_k=2
    )
    assert len(sources) > 0
    # Must NOT force Variable 14 / Gestante when no keywords match
    assert "Variable 14" not in sources[0].section
    assert "Guía General de Validación de Formularios" in sources[0].document_title


@pytest.mark.asyncio
async def test_busqueda_client_pipeline_delimiter_query():
    client = BusquedaHttpClient(
        base_url="http://non-existent-host:9999",
        fallback_enabled=True
    )
    sources = await client.search(
        query="El delimitador pipeline o pipe tiene error en fase 1",
        top_k=2
    )

    assert len(sources) > 0
    assert any("delimitador" in s.snippet.lower() or "pipeline" in s.snippet.lower() for s in sources)
