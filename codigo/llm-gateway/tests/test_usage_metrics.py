"""
Tests for usage metrics endpoints in llm-gateway.
"""

from fastapi.testclient import TestClient


def test_usage_summary(client: TestClient, superadmin_headers: dict):
    res = client.get("/api/v1/usage", headers=superadmin_headers)
    assert res.status_code == 200
    data = res.json()
    assert "total_records" in data
    assert "total_tokens" in data
    assert "total_cost_usd" in data
    assert "saved_fast_path_calls" in data
    assert data["total_records"] >= 3


def test_usage_by_user(client: TestClient, superadmin_headers: dict):
    res = client.get("/api/v1/usage/by-user", headers=superadmin_headers)
    assert res.status_code == 200
    users = res.json()
    assert len(users) >= 2
    user_names = [u["usuario"] for u in users]
    assert "dr_perez" in user_names
    assert "auditor_1" in user_names

    perez = next(u for u in users if u["usuario"] == "dr_perez")
    assert perez["rol"] == "PERFIL_IPS_MEDICO"
    assert perez["llm_requests"] >= 1
    assert perez["total_tokens"] > 0

    auditor = next(u for u in users if u["usuario"] == "auditor_1")
    assert auditor["rol"] == "PERFIL_EPS_AUDITOR"
    assert auditor["fast_path_requests"] >= 1


def test_usage_by_role(client: TestClient, superadmin_headers: dict):
    res = client.get("/api/v1/usage/by-role", headers=superadmin_headers)
    assert res.status_code == 200
    roles = res.json()
    assert len(roles) >= 2
    role_names = [r["rol"] for r in roles]
    assert "PERFIL_IPS_MEDICO" in role_names
    assert "PERFIL_EPS_AUDITOR" in role_names


def test_usage_by_model(client: TestClient, superadmin_headers: dict):
    res = client.get("/api/v1/usage/by-model", headers=superadmin_headers)
    assert res.status_code == 200
    models = res.json()
    assert len(models) >= 1
    assert "model" in models[0]
    assert "total_requests" in models[0]


def test_usage_records_paginated(client: TestClient, superadmin_headers: dict):
    res = client.get("/api/v1/usage/records?limit=10", headers=superadmin_headers)
    assert res.status_code == 200
    records = res.json()
    assert len(records) >= 3
    rec = records[0]
    assert "ledger_id" in rec
    assert "operacion" in rec
    assert "tokens_input" in rec


def test_client_admin_scoping(client: TestClient, client_admin_headers: dict):
    # client_admin_headers is bound to "sigires"
    res = client.get("/api/v1/usage", headers=client_admin_headers)
    assert res.status_code == 200
    # Should only return records where client_id == "sigires"
    users_res = client.get("/api/v1/usage/by-user", headers=client_admin_headers)
    assert users_res.status_code == 200
    for u in users_res.json():
        assert u["client_id"] == "sigires"
