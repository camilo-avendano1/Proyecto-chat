"""
Tests for Healthcheck, Status, and Token Usage endpoints.
"""

from fastapi.testclient import TestClient


def test_health_check(client: TestClient):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_system_status(client: TestClient):
    response = client.get("/api/v1/status")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data
    assert "back_busqueda_status" in data
    assert "llm_service_status" in data

    # Verify authors
    assert "authors" in data
    assert "Juan Camilo Avendaño" in data["authors"]
    assert "Fran Sneider Quincha" in data["authors"]
    assert "Adriana Moreno" in data["authors"]

    # Verify LLM local configuration
    assert data["llm_provider"] == "lmstudio"
    assert data["llm_base_url"] == "http://localhost:1234/v1"
    assert data["llm_model"] == "local-model"


def test_usage_ledger_records(
    client: TestClient,
    valid_session_token: str,
    sample_diagnostic_payload: dict
):
    # Execute a diagnostic query first so usage is logged
    headers = {
        "Authorization": f"Bearer {valid_session_token}",
        "Content-Type": "application/json",
    }
    client.post("/api/v1/diagnostic/query", headers=headers, json=sample_diagnostic_payload)

    # Check /api/v1/usage
    response = client.get("/api/v1/usage")
    assert response.status_code == 200
    data = response.json()
    assert data["total_records"] >= 1
    assert data["total_tokens_input"] > 0
    assert data["total_tokens_output"] > 0
