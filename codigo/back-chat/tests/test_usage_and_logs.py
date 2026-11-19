"""
Unit and Integration tests for Token Usage tracking per User and per Site,
Inbound/Outbound message auditing, and Security Logs.
"""

from fastapi.testclient import TestClient


def test_token_tracking_per_user_and_site(
    client: TestClient,
    valid_session_token: str,
    sample_diagnostic_payload: dict,
):
    """Verifies that queries by different users under a site accumulate correctly."""
    headers = {
        "Authorization": f"Bearer {valid_session_token}",
        "Content-Type": "application/json",
    }

    payload_a = sample_diagnostic_payload.copy()
    payload_a["user_context"] = {
        "usuario": "medico_juan",
        "eps": "EPS_SURA",
        "site_code": "631300000001",
        "permisos": "PERFIL_IPS_MEDICO",
    }
    payload_a["query"] = "Error en variable 14 gestante fila 10"
    resp_a = client.post("/api/v1/diagnostic/query", headers=headers, json=payload_a)
    assert resp_a.status_code == 200

    payload_b = sample_diagnostic_payload.copy()
    payload_b["user_context"] = {
        "usuario": "auditora_maria",
        "eps": "EPS_SURA",
        "site_code": "631300000001",
        "permisos": "PERFIL_EPS_AUDITOR",
    }
    payload_b["query"] = "Hola buenos días"
    payload_b["system_logs"] = None
    resp_b = client.post("/api/v1/diagnostic/query", headers=headers, json=payload_b)
    assert resp_b.status_code == 200

    # Test /api/v1/usage/by-user
    resp_users = client.get("/api/v1/usage/by-user")
    assert resp_users.status_code == 200
    users_data = resp_users.json()
    assert len(users_data) >= 2

    user_map = {u["usuario"]: u for u in users_data}
    assert "medico_juan" in user_map
    assert "auditora_maria" in user_map

    assert user_map["medico_juan"]["llm_requests"] >= 1
    assert user_map["medico_juan"]["total_tokens"] > 0
    assert user_map["auditora_maria"]["fast_path_requests"] >= 1

    # Test /api/v1/usage/by-site
    resp_sites = client.get("/api/v1/usage/by-site")
    assert resp_sites.status_code == 200
    sites_data = resp_sites.json()
    assert len(sites_data) >= 1
    site = next((s for s in sites_data if s["site_id"] == "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d"), None)
    assert site is not None
    assert site["total_requests"] >= 2


def test_message_audit_logs(
    client: TestClient,
    valid_session_token: str,
    sample_diagnostic_payload: dict,
):
    """Verifies that inbound and outbound messages are audited with user and site attribution."""
    headers = {
        "Authorization": f"Bearer {valid_session_token}",
        "Content-Type": "application/json",
    }
    payload = sample_diagnostic_payload.copy()
    payload["user_context"]["usuario"] = "radicador_test_audit"
    payload["query"] = "Consulta de validacion de estructura para fila 12"

    client.post("/api/v1/diagnostic/query", headers=headers, json=payload)

    resp_logs = client.get("/api/v1/usage/message-logs?usuario=radicador_test_audit")
    assert resp_logs.status_code == 200
    logs_data = resp_logs.json()
    assert len(logs_data) >= 2

    directions = [m["direction"] for m in logs_data]
    assert "INCOMING" in directions
    assert "OUTGOING" in directions

    incoming = next(m for m in logs_data if m["direction"] == "INCOMING")
    assert "Consulta de validacion" in incoming["content"]
    assert incoming["usuario"] == "radicador_test_audit"


def test_security_audit_logs_unauthorized_access(client: TestClient):
    """Verifies that failed session creation logs security alerts."""
    response = client.post(
        "/api/v1/widget/session",
        headers={"X-Widget-Key": "invalid_key_12345"},
        json={
            "origin": "https://unauthorized-domain.com",
            "site_code": "631300000001",
        },
    )
    assert response.status_code == 401

    sec_resp = client.get("/api/v1/usage/security-logs")
    assert sec_resp.status_code == 200
    sec_data = sec_resp.json()
    auth_failures = [e for e in sec_data if e["event_type"] == "AUTH_FAILURE"]
    assert len(auth_failures) >= 1


def test_x_request_id_middleware(client: TestClient):
    """Verifies that every response includes a unique X-Request-ID header."""
    response = client.get("/health")
    assert response.status_code == 200
    assert "X-Request-ID" in response.headers
    assert len(response.headers["X-Request-ID"]) > 10
