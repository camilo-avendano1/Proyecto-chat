"""
Integration tests for Diagnostic endpoints:
- POST /api/v1/diagnostic/query
- POST /api/v1/diagnostic/stream (SSE)
"""

from fastapi.testclient import TestClient


def test_diagnostic_query_unauthorized(client: TestClient, sample_diagnostic_payload: dict):
    # No Authorization header
    response = client.post("/api/v1/diagnostic/query", json=sample_diagnostic_payload)
    assert response.status_code == 401


def test_diagnostic_query_success(
    client: TestClient,
    valid_session_token: str,
    sample_diagnostic_payload: dict
):
    headers = {
        "Authorization": f"Bearer {valid_session_token}",
        "Content-Type": "application/json",
    }
    response = client.post(
        "/api/v1/diagnostic/query",
        headers=headers,
        json=sample_diagnostic_payload
    )
    assert response.status_code == 200
    data = response.json()

    assert "response" in data
    assert len(data["response"]) > 50

    # Error diagnostic structure
    assert "error_diagnostic" in data
    diag = data["error_diagnostic"]
    assert diag["affected_row"] == 45
    assert diag["affected_variable_number"] == 14
    assert diag["detected_code"] == "CE_VAR_014_INVAL"
    assert diag["error_phase"] == "FASE_2_CE"

    # Sources structure
    assert "sources" in data
    assert len(data["sources"]) > 0
    assert "document_title" in data["sources"][0]
    assert "scope" in data["sources"][0]


def test_diagnostic_stream_success(
    client: TestClient,
    valid_session_token: str,
    sample_diagnostic_payload: dict
):
    headers = {
        "Authorization": f"Bearer {valid_session_token}",
        "Accept": "text/event-stream",
        "Content-Type": "application/json",
    }
    response = client.post(
        "/api/v1/diagnostic/stream",
        headers=headers,
        json=sample_diagnostic_payload
    )
    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]

    content = response.text
    # Verify expected SSE events
    assert "event: chunk" in content
    assert "event: error_diagnostic" in content
    assert "event: sources" in content
    assert "event: done" in content
    assert '"status": "COMPLETED"' in content
    assert "CE_VAR_014_INVAL" in content


def test_chat_query_minimal_general_question(
    client: TestClient,
    generic_session_token: str,
):
    headers = {
        "Authorization": f"Bearer {generic_session_token}",
        "Content-Type": "application/json",
    }
    response = client.post(
        "/api/v1/chat/query",
        headers=headers,
        json={"query": "¿Cómo se aprueba una orden de compra?"},
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["response"]) > 50
    assert data["error_diagnostic"] is None
    assert "SIGIRES" not in data["response"]
    assert "CE_GENERAL_VAL_ERR" not in data["response"]
    assert len(data["sources"]) > 0


def test_chat_stream_minimal_general_question(
    client: TestClient,
    generic_session_token: str,
):
    headers = {
        "Authorization": f"Bearer {generic_session_token}",
        "Accept": "text/event-stream",
        "Content-Type": "application/json",
    }
    response = client.post(
        "/api/v1/chat/stream",
        headers=headers,
        json={"query": "¿Cómo se aprueba una orden de compra?"},
    )
    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]

    content = response.text
    assert "event: chunk" in content
    assert "event: error_diagnostic\ndata: null" in content
    assert "event: sources" in content
    assert "event: done" in content
    assert '"status": "COMPLETED"' in content
    assert "SIGIRES" not in content
    assert "CE_GENERAL_VAL_ERR" not in content


def test_chat_query_generic_enriched_payload(
    client: TestClient,
    generic_session_token: str,
):
    headers = {
        "Authorization": f"Bearer {generic_session_token}",
        "Content-Type": "application/json",
    }
    payload = {
        "query": "¿Cuál es el proceso para aprobar una orden de compra mayor?",
        "user": {
            "id": "ana.compras.test",
            "role": "COMPRADOR_SENIOR",
            "organization": "SEDE_NORTE",
            "attributes": {"departamento": "Abastecimiento"},
        },
        "context": {
            "pagina": "aprobaciones_oc",
            "modulo": "COMPRAS",
            "monto": 15000,
        },
        "extras": {
            "modulo_erp": "compras",
            "pais": "CO",
        },
    }
    response = client.post("/api/v1/chat/query", headers=headers, json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["error_diagnostic"] is None
    assert len(data["response"]) > 50

    logs_resp = client.get("/api/v1/usage/message-logs?usuario=ana.compras.test")
    assert logs_resp.status_code == 200
    logs = logs_resp.json()
    assert len(logs) >= 2
    assert any(item["ips_code"] == "SEDE_NORTE" for item in logs)


def test_chat_query_missing_or_empty_query_returns_422(
    client: TestClient,
    generic_session_token: str,
):
    headers = {
        "Authorization": f"Bearer {generic_session_token}",
        "Content-Type": "application/json",
    }
    resp_missing = client.post("/api/v1/chat/query", headers=headers, json={})
    assert resp_missing.status_code == 422

    resp_empty = client.post("/api/v1/chat/query", headers=headers, json={"query": ""})
    assert resp_empty.status_code == 422


def test_diagnostic_query_accepts_minimal_payload(
    client: TestClient,
    valid_session_token: str,
):
    headers = {
        "Authorization": f"Bearer {valid_session_token}",
        "Content-Type": "application/json",
    }
    response = client.post(
        "/api/v1/diagnostic/query",
        headers=headers,
        json={"query": "¿Cómo consultar el estado de una solicitud en la plataforma?"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["error_diagnostic"] is None
    assert len(data["response"]) > 50
