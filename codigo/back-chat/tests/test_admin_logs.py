"""
Tests for Admin Observability & Central Audit Logs endpoints in back-chat.
Validates JWT role enforcement and audit trail queries.
"""

import os
os.environ["DISABLE_SQLALCHEMY_CEXT"] = "1"

import jwt
from fastapi.testclient import TestClient

from src.config import settings
from src.core.audit import audit_logger


def _generate_admin_token(role: str = "GLOBAL_ADMIN", org_id: str | None = "sigires", username: str = "admin_test") -> str:
    payload = {
        "sub": "user_admin_001",
        "username": username,
        "email": f"{username}@saas.com",
        "role": role,
        "org_id": org_id,
        "aud": settings.ADMIN_TOKEN_AUDIENCE,
        "typ": "admin",
    }
    return jwt.encode(payload, settings.ADMIN_JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def test_admin_logs_unauthorized_without_token(client: TestClient):
    resp = client.get("/api/v1/admin/logs/security")
    assert resp.status_code == 401


def test_admin_logs_security_query_global_admin(client: TestClient):
    audit_logger.log_security_event(
        event_type="TEST_ADMIN_QUERY_EVENT",
        severity="HIGH",
        org_id="sigires",
        site_id="site_alpha",
        usuario="test_actor",
        details={"test": "ok"},
    )
    audit_logger.flush()

    token = _generate_admin_token(role="GLOBAL_ADMIN")
    resp = client.get(
        "/api/v1/admin/logs/security?event_type=TEST_ADMIN_QUERY_EVENT",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "records" in data
    assert any(r["event_type"] == "TEST_ADMIN_QUERY_EVENT" for r in data["records"])


def test_admin_logs_messages_query(client: TestClient):
    audit_logger.log_message(
        direction="INCOMING",
        org_id="sigires",
        site_id="site_alpha",
        usuario="dr_test",
        content="Consulta de prueba para auditoria central",
        rol="medico",
    )
    audit_logger.flush()

    token = _generate_admin_token(role="GLOBAL_ADMIN")
    resp = client.get(
        "/api/v1/admin/logs/messages",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "records" in data
    assert len(data["records"]) >= 1


def test_admin_logs_org_admin_scoped(client: TestClient):
    token = _generate_admin_token(role="ORG_ADMIN", org_id="otra_empresa", username="org_admin_test")
    resp = client.get(
        "/api/v1/admin/logs/security?org_id=sigires",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["org_id_scoped"] == "otra_empresa"
