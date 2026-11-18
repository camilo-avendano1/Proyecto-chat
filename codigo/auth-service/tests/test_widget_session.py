"""
Tests for POST /api/v1/widget/session in auth-service.
"""

from fastapi.testclient import TestClient
import jwt

from src.config import settings
from src.services.widget_session_service import _sanitize_metadata


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


def test_create_session_minimal_with_origin_header_only(client: TestClient):
    headers = {
        "X-Widget-Key": "pk_live_sigires_8f9a2b1c3d4e5f6a",
        "Origin": "http://localhost:5173",
    }
    response = client.post("/api/v1/widget/session", headers=headers, json={})
    assert response.status_code == 200
    data = response.json()
    assert data["client_id"] == "sigires"


def test_create_session_minimal_no_body_wildcard_client(client: TestClient):
    headers = {
        "X-Widget-Key": "pk_live_otraempresa_1a2b3c4d5e6f7a8b",
    }
    response = client.post("/api/v1/widget/session", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["client_id"] == "otra_empresa"


def test_create_session_restricted_client_without_origin_forbidden(client: TestClient):
    headers = {
        "X-Widget-Key": "pk_live_sigires_8f9a2b1c3d4e5f6a",
    }
    response = client.post("/api/v1/widget/session", headers=headers, json={})
    assert response.status_code == 403


def test_create_session_generic_metadata_included_in_jwt(client: TestClient):
    headers = {
        "X-Widget-Key": "pk_live_otraempresa_1a2b3c4d5e6f7a8b",
    }
    payload = {
        "origin": "https://app.ejemplo.com",
        "metadata": {"branch": "bogota", "department": "compras"},
    }
    response = client.post("/api/v1/widget/session", headers=headers, json=payload)
    assert response.status_code == 200
    token = response.json()["session_token"]
    decoded = jwt.decode(
        token,
        settings.WIDGET_JWT_SECRET,
        algorithms=[settings.JWT_ALGORITHM],
        audience=settings.WIDGET_TOKEN_AUDIENCE,
    )
    assert decoded["metadata"] == {"branch": "bogota", "department": "compras"}
    assert decoded["eps_id"] is None


def test_create_session_sanitizes_metadata_and_merges_legacy_fields(client: TestClient):
    headers = {
        "X-Widget-Key": "pk_live_sigires_8f9a2b1c3d4e5f6a",
        "Origin": "http://localhost:5173",
    }
    payload = {
        "eps_id": "eps_sura_01",
        "ips_code": "631300040301",
        "metadata": {
            "branch": "medellin",
            "active": True,
            "count": 3,
            "long_val": "x" * 250,
            "null_val": None,
            "nested": {"a": 1},
            "bad key!": "ignored",
        },
    }
    response = client.post("/api/v1/widget/session", headers=headers, json=payload)
    assert response.status_code == 200
    decoded = jwt.decode(
        response.json()["session_token"],
        settings.WIDGET_JWT_SECRET,
        algorithms=[settings.JWT_ALGORITHM],
        audience=settings.WIDGET_TOKEN_AUDIENCE,
    )
    assert decoded["eps_id"] == "eps_sura_01"
    assert decoded["ips_code"] == "631300040301"
    assert decoded["metadata"] == {
        "branch": "medellin",
        "active": True,
        "count": 3,
        "long_val": "x" * 200,
        "eps_id": "eps_sura_01",
        "ips_code": "631300040301",
    }


def test_sanitize_metadata_caps_at_20_keys():
    raw = {f"key_{i}": i for i in range(25)}
    raw["invalid\nkey"] = "drop"
    sanitized = _sanitize_metadata(raw)
    assert len(sanitized) == 20
    assert "invalid\nkey" not in sanitized
