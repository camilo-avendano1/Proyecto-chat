"""
Tests for POST /api/v1/widget/session in auth-service.
"""

from fastapi.testclient import TestClient


def test_create_session_success(client: TestClient):
    headers = {
        "X-Widget-Key": "pk_live_sigires_8f9a2b1c3d4e5f6a",
        "Content-Type": "application/json",
    }
    payload = {
        "client_id": "sigires",
        "origin": "https://sigires.procex.co",
        "eps_id": "eps_sura_01",
        "ips_code": "631300040301",
    }

    response = client.post("/api/v1/widget/session", headers=headers, json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "session_token" in data
    assert data["client_id"] == "sigires"
    assert "SIGIRES" in data["client_name"]
    assert "tenant_id" in data
    assert "tenant_name" in data
    assert data["expires_in_seconds"] == 1800
    assert len(data["session_token"]) > 30


def test_create_session_otra_empresa(client: TestClient):
    headers = {
        "X-Widget-Key": "pk_live_otraempresa_1a2b3c4d5e6f7a8b",
        "Content-Type": "application/json",
    }
    payload = {
        "client_id": "otra_empresa",
        "origin": "https://corporacion-externa.com",
        "eps_id": "corp_div_01",
        "ips_code": "900100200",
    }

    response = client.post("/api/v1/widget/session", headers=headers, json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["client_id"] == "otra_empresa"
    assert "Entidad Corporativa Externa" in data["client_name"]


def test_create_session_invalid_key(client: TestClient):
    headers = {
        "X-Widget-Key": "pk_live_invalid_key_99999",
        "Content-Type": "application/json",
    }
    payload = {
        "origin": "https://sigires.procex.co",
        "eps_id": "eps_sura_01",
        "ips_code": "631300040301",
    }

    response = client.post("/api/v1/widget/session", headers=headers, json=payload)
    assert response.status_code == 401
    assert "no es válida" in response.json()["detail"]


def test_create_session_missing_key_header(client: TestClient):
    payload = {
        "origin": "https://sigires.procex.co",
        "eps_id": "eps_sura_01",
        "ips_code": "631300040301",
    }
    response = client.post("/api/v1/widget/session", json=payload)
    assert response.status_code == 422


def test_create_session_unauthorized_origin(client: TestClient):
    headers = {
        "X-Widget-Key": "pk_live_sigires_8f9a2b1c3d4e5f6a",
        "Content-Type": "application/json",
    }
    payload = {
        "origin": "https://unauthorized-domain.hack.io",
        "eps_id": "eps_sura_01",
        "ips_code": "631300040301",
    }

    response = client.post("/api/v1/widget/session", headers=headers, json=payload)
    assert response.status_code == 403
    assert "no está autorizado" in response.json()["detail"]
