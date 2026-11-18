"""
Integration tests for POST /api/v1/widget/session endpoint.
Tests multi-client identification and division/tenant mapping.
"""

from fastapi.testclient import TestClient


def test_create_session_success(client: TestClient, valid_widget_key: str):
    headers = {
        "X-Widget-Key": valid_widget_key,
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


def test_create_session_unauthorized_origin(client: TestClient, valid_widget_key: str):
    headers = {
        "X-Widget-Key": valid_widget_key,
        "Content-Type": "application/json",
    }
    payload = {
        "origin": "https://unauthorized-domain.hack.io",
        "eps_id": "eps_sura_01",
        "ips_code": "631300040301",
    }

    response = client.post("/api/v1/widget/session", headers=headers, json=payload)
    assert response.status_code == 403
    assert "no está autorizado en la lista blanca" in response.json()["detail"]


def test_create_session_minimal_body_with_origin_header(client: TestClient, valid_widget_key: str):
    headers = {
        "X-Widget-Key": valid_widget_key,
        "Origin": "https://sigires.procex.co",
        "Content-Type": "application/json",
    }
    response = client.post("/api/v1/widget/session", headers=headers, json={})
    assert response.status_code == 200
    data = response.json()
    assert data["client_id"] == "sigires"
    assert len(data["session_token"]) > 30


def test_create_session_wildcard_without_origin(client: TestClient):
    headers = {
        "X-Widget-Key": "pk_live_otraempresa_1a2b3c4d5e6f7a8b",
        "Content-Type": "application/json",
    }
    response = client.post("/api/v1/widget/session", headers=headers, json={})
    assert response.status_code == 200
    data = response.json()
    assert data["client_id"] == "otra_empresa"
    assert "Entidad Corporativa Externa" in data["client_name"]


def test_create_session_with_generic_metadata(client: TestClient):
    from src.infrastructure.security.jwt_handler import default_jwt_handler

    headers = {
        "X-Widget-Key": "pk_live_otraempresa_1a2b3c4d5e6f7a8b",
        "Content-Type": "application/json",
    }
    payload = {
        "metadata": {
            "canal": "portal_erp",
            "pais": "CO",
            "invalid$key": "should_be_dropped",
            "nested": {"no": "scalars_only"},
        }
    }
    response = client.post("/api/v1/widget/session", headers=headers, json=payload)
    assert response.status_code == 200
    data = response.json()
    decoded = default_jwt_handler.decode_token(data["session_token"])
    assert decoded["metadata"] == {"canal": "portal_erp", "pais": "CO"}


def test_create_session_restricted_tenant_without_origin_returns_403(
    client: TestClient,
    valid_widget_key: str,
):
    headers = {
        "X-Widget-Key": valid_widget_key,
        "Content-Type": "application/json",
    }
    response = client.post("/api/v1/widget/session", headers=headers, json={})
    assert response.status_code == 403
    assert "no está autorizado en la lista blanca" in response.json()["detail"]
