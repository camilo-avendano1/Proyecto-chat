"""
Tests for internal chat endpoints in llm-gateway.
"""

from fastapi.testclient import TestClient


def test_internal_chat_missing_key_forbidden(client: TestClient):
    payload = {
        "system_prompt": "Eres un asistente.",
        "user_prompt": "Error variable 14",
        "caller": {
            "org_id": "sigires",
            "site_id": "site-1",
            "usuario": "medico_1",
            "rol": "PERFIL_IPS_MEDICO",
        },
    }
    res = client.post("/internal/v1/chat", json=payload)
    assert res.status_code == 401


def test_internal_chat_sync_success(client: TestClient, internal_headers: dict):
    payload = {
        "system_prompt": "Eres un asistente técnico de validación de formularios y reglamentos.",
        "user_prompt": "Tengo un rechazo en el formulario de enfermería en el campo 14",
        "stream": False,
        "caller": {
            "org_id": "sigires",
            "site_id": "site-sura",
            "site_code": "SC-SURA-01",
            "usuario": "dr_perez",
            "rol": "PERFIL_IPS_MEDICO",
            "operacion": "DIAGNOSTIC_QUERY",
            "request_id": "req-12345",
        },
    }
    res = client.post("/internal/v1/chat", headers=internal_headers, json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "response" in data
    assert len(data["response"]) > 20
    assert "campo 14" in data["response"].lower() or "formulario" in data["response"].lower()
    assert data["tokens_input"] > 0
    assert data["tokens_output"] > 0
    assert data["tokens_total"] > 0
    assert "model_used" in data


def test_internal_chat_stream_success(client: TestClient, internal_headers: dict):
    payload = {
        "system_prompt": "Eres un asistente clínico.",
        "user_prompt": "Error en delimitador pipeline fase 1",
        "stream": True,
        "caller": {
            "org_id": "sigires",
            "site_id": "site-sanitas",
            "site_code": "SC-SAN-01",
            "usuario": "radicador_1",
            "rol": "PERFIL_IPS_RADICADOR",
            "operacion": "DIAGNOSTIC_STREAM",
            "request_id": "req-stream-1",
        },
    }
    res = client.post("/internal/v1/chat", headers=internal_headers, json=payload)
    assert res.status_code == 200
    assert "text/event-stream" in res.headers["content-type"]
    text = res.text
    assert "event: chunk" in text
    assert "event: done" in text
    assert "delimitador" in text.lower() or "pipeline" in text.lower()


def test_internal_chat_stream_error_logs_audit(client: TestClient, internal_headers: dict, monkeypatch):
    from src.routers import internal_router

    async def _broken_stream(*args, **kwargs):
        raise RuntimeError("boom stream")
        yield  # pragma: no cover

    monkeypatch.setattr(internal_router._engine_client, "generate_stream", _broken_stream)
    payload = {
        "system_prompt": "Eres un asistente.",
        "user_prompt": "Prueba error stream",
        "stream": True,
        "caller": {
            "org_id": "sigires",
            "site_id": "site-sura",
            "site_code": "SC-SURA-01",
            "usuario": "stream_err_user",
            "rol": "PERFIL_IPS_MEDICO",
            "request_id": "req-stream-err",
        },
    }
    res = client.post("/internal/v1/chat", headers=internal_headers, json=payload)
    assert res.status_code == 200
    assert "event: error" in res.text
    assert "boom stream" in res.text


def test_internal_usage_events_record(client: TestClient, internal_headers: dict):
    payload = {
        "caller": {
            "org_id": "sigires",
            "site_id": "site-sura",
            "site_code": "SC-SURA-01",
            "usuario": "auditor_1",
            "rol": "PERFIL_EPS_AUDITOR",
            "operacion": "FAST_RESPONSE_GREETING",
            "request_id": "req-greeting-1",
        },
        "tokens_input": 0,
        "tokens_output": 0,
        "costo_usd": 0.0,
        "latencia_ms": 2,
        "status": "FAST_RESPONSE_GREETING",
        "is_llm_call": False,
        "query_preview": "Hola buenos dias",
    }
    res = client.post("/internal/v1/usage/events", headers=internal_headers, json=payload)
    assert res.status_code == 201
    assert res.json()["status"] == "recorded"


def test_internal_chat_minimal_generic_caller(client: TestClient, internal_headers: dict):
    payload = {
        "system_prompt": "Eres el Asistente Virtual de Otra Empresa.",
        "user_prompt": "¿Cómo se aprueba una orden de compra?",
        "stream": False,
        "caller": {
            "org_id": "otra_empresa",
            "site_id": "s1",
        },
    }
    res = client.post("/internal/v1/chat", headers=internal_headers, json=payload)
    assert res.status_code == 200
    data = res.json()
    text = data["response"]
    assert text and len(text.strip()) > 0
    lower = text.lower()
    assert "orden de compra" in lower or "documentación" in lower or "búsqueda" in lower
    assert "sigires" not in lower
    assert "ce_general_val_err" not in lower


def test_simulated_response_adaptive_cases():
    from src.services.engine_client import EngineClient
    from src.schemas import CallerContext
    from src.db.models import UsageRecordORM

    caller = CallerContext()
    assert caller.org_id == "default"
    assert caller.site_id == "unknown"
    assert caller.operacion == "CHAT_QUERY"
    assert caller.rol is None
    assert caller.site_code is None
    assert UsageRecordORM.org_id.default.arg == "default"
    assert UsageRecordORM.site_id.default.arg == "unknown"

    engine = EngineClient()
    assert engine._generate_simulated_clinical_response is not None

    # Case 1: Error code + RAG snippet (with and without format, including quoted query before RAG)
    prompt_case_1 = (
        "CONTEXTO TÉCNICO:\n"
        "- Código de Error: ERR-402\n"
        "- Fase / Categoría de Validación: Estructura CSV\n"
        "- Campo / Variable / Columna Afectada: fecha_emision\n"
        "- Formato de Formulario o Archivo: FACTURA_V2\n\n"
        "CONSULTA DEL USUARIO:\n"
        '"¿Por qué falla la fecha de emisión?"\n\n'
        "1. [Manual Técnico] **Guía de Integración** - Fechas:\n"
        '"La fecha de emisión debe seguir el formato YYYY-MM-DD."\n'
    )
    resp_1 = engine._generate_simulated_response(prompt_case_1)
    assert "ERR-402" in resp_1
    assert "Estructura CSV" in resp_1
    assert "fecha_emision" in resp_1
    assert "FACTURA_V2" in resp_1
    assert "La fecha de emisión debe seguir el formato YYYY-MM-DD." in resp_1
    assert "Guía de Integración - Fechas" in resp_1

    prompt_case_1_no_fmt = (
        "- Código de Error: ERR-500\n"
        "- Fase / Categoría de Validación: Reglas de Negocio\n"
        "- Campo / Variable / Columna Afectada: monto_total\n\n"
        "1. [Normativa] **Manual Contable** - Validaciones:\n"
        '"El monto total debe ser mayor a cero."\n'
    )
    resp_1_no_fmt = engine._generate_simulated_response(prompt_case_1_no_fmt)
    assert "ERR-500" in resp_1_no_fmt
    assert "monto_total" in resp_1_no_fmt
    assert "Manual Contable - Validaciones" in resp_1_no_fmt

    # Case 2: RAG snippet without error code
    prompt_case_2 = (
        "CONSULTA DEL USUARIO:\n"
        '"¿Cómo se aprueba una orden de compra?"\n\n'
        "DOCUMENTOS RECUPERADOS:\n"
        "1. [Políticas Internas] **Manual de Compras** - Flujo de Aprobación:\n"
        '"Las órdenes superiores a 5000 USD requieren firma de la dirección financiera."\n'
    )
    resp_2 = engine._generate_simulated_response(prompt_case_2)
    assert "orden de compra" in resp_2.lower()
    assert "Manual de Compras - Flujo de Aprobación" in resp_2
    assert "Las órdenes superiores a 5000 USD requieren firma de la dirección financiera." in resp_2
    assert "VALIDACION_TECNICA" not in resp_2
    assert "sigires" not in resp_2.lower()

    # Case 3: Short prompt / alias backwards compatibility
    resp_3 = engine._generate_simulated_clinical_response(
        'CONSULTA DEL USUARIO:\n"¿Cuál es el horario de soporte?"'
    )
    assert len(resp_3) > 20
    assert "¿Cuál es el horario de soporte?" in resp_3
    assert "sigires" not in resp_3.lower()


async def test_engine_client_fallback_model_used(monkeypatch):
    import httpx
    from src.services.engine_client import EngineClient

    async def _fail_post(*args, **kwargs):
        raise httpx.ConnectError("mocked offline llm")

    monkeypatch.setattr(httpx.AsyncClient, "post", _fail_post)
    engine = EngineClient(fallback_on_error=True)
    result = await engine.generate_response(
        system_prompt="Asistente",
        user_prompt="¿Cómo funciona el módulo?",
    )
    assert result.model_used == "simulated-fallback"
    assert result.provider_used == "contingency-engine"
    assert "¿Cómo funciona el módulo?" in result.text
