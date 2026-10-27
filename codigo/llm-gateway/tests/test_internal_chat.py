"""
Tests for internal chat endpoints in llm-gateway.
"""

from fastapi.testclient import TestClient


def test_internal_chat_missing_key_forbidden(client: TestClient):
    payload = {
        "system_prompt": "Eres un asistente.",
        "user_prompt": "Error variable 14",
        "caller": {
            "client_id": "sigires",
            "tenant_id": "tenant-1",
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
            "client_id": "sigires",
            "tenant_id": "tenant-sura",
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
            "client_id": "sigires",
            "tenant_id": "tenant-sanitas",
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


def test_internal_usage_events_record(client: TestClient, internal_headers: dict):
    payload = {
        "caller": {
            "client_id": "sigires",
            "tenant_id": "tenant-sura",
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
