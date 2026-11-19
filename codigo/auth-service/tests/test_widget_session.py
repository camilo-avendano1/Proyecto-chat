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
        "org_id": "sigires",
        "origin": "https://sigires.procex.co",
        "site_code": "631300040301",
    }

    response = client.post("/api/v1/widget/session", headers=headers, json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "session_token" in data
    assert data["org_id"] == "sigires"
    assert "SIGIRES" in data["org_name"]
    assert data["site_id"] == "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d"
    assert "EPS Sura" in data["site_name"]
    assert data["site_code"] == "eps_sura_01"
    assert data["site_label"] == "IPS"
    assert data["expires_in_seconds"] == 1800
    assert len(data["session_token"]) > 30


def test_create_session_otra_empresa(client: TestClient):
    headers = {
        "X-Widget-Key": "pk_live_otraempresa_1a2b3c4d5e6f7a8b",
        "Content-Type": "application/json",
    }
    payload = {
        "org_id": "otra_empresa",
        "origin": "https://corporacion-externa.com",
        "site_code": "900100200",
    }

    response = client.post("/api/v1/widget/session", headers=headers, json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["org_id"] == "otra_empresa"
    assert "Organización Demo Central" in data["org_name"]
    assert data["site_code"] == "sede_central_01"
    assert data["site_label"] == "Sede"


def test_create_session_invalid_key(client: TestClient):
    headers = {
        "X-Widget-Key": "pk_live_invalid_key_99999",
        "Content-Type": "application/json",
    }
    payload = {
        "origin": "https://sigires.procex.co",
        "site_code": "631300040301",
    }

    response = client.post("/api/v1/widget/session", headers=headers, json=payload)
    assert response.status_code == 401
    assert "no es válida" in response.json()["detail"]


def test_create_session_missing_key_header(client: TestClient):
    payload = {
        "origin": "https://sigires.procex.co",
        "site_code": "631300040301",
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
        "site_code": "631300040301",
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
    assert data["org_id"] == "sigires"


def test_create_session_minimal_no_body_wildcard_org(client: TestClient):
    headers = {
        "X-Widget-Key": "pk_live_otraempresa_1a2b3c4d5e6f7a8b",
    }
    response = client.post("/api/v1/widget/session", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["org_id"] == "otra_empresa"


def test_create_session_restricted_org_without_origin_forbidden(client: TestClient):
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
    assert decoded["sub"] == "e55f6a7b-8c9d-0e1f-2a3b-4c5d6e7f8a9b"
    assert decoded["org_id"] == "otra_empresa"
    assert decoded["org_name"] == "Organización Demo Central"
    assert decoded["site_id"] == "e55f6a7b-8c9d-0e1f-2a3b-4c5d6e7f8a9b"
    assert decoded["site_name"] == "Sede Operativa Central"
    assert decoded["site_code"] == "sede_central_01"
    assert decoded["site_label"] == "Sede"
    assert decoded["metadata"] == {"branch": "bogota", "department": "compras"}
    assert "eps_id" not in decoded


def test_create_session_sanitizes_metadata_and_merges_site_code(client: TestClient):
    headers = {
        "X-Widget-Key": "pk_live_sigires_8f9a2b1c3d4e5f6a",
        "Origin": "http://localhost:5173",
    }
    payload = {
        "site_code": "631300040301",
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
    assert decoded["site_code"] == "eps_sura_01"
    assert decoded["site_label"] == "IPS"
    assert decoded["metadata"] == {
        "branch": "medellin",
        "active": True,
        "count": 3,
        "long_val": "x" * 200,
        "site_code": "631300040301",
    }


def test_sanitize_metadata_caps_at_20_keys():
    raw = {f"key_{i}": i for i in range(25)}
    raw["invalid\nkey"] = "drop"
    sanitized = _sanitize_metadata(raw)
    assert len(sanitized) == 20
    assert "invalid\nkey" not in sanitized
