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
