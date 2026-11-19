"""
Tests for usage metrics endpoints in llm-gateway.
"""

from datetime import datetime, timedelta, timezone
import sqlite3
from fastapi.testclient import TestClient
from sqlalchemy import delete, inspect as sa_inspect

from src.config import settings
from src.db.ledger_repo import LedgerRepository
from src.db.models import Database, UsageRecordORM
from src.dependencies import get_db_instance


def test_usage_summary(client: TestClient, global_admin_headers: dict):
    res = client.get("/api/v1/usage", headers=global_admin_headers)
    assert res.status_code == 200
    data = res.json()
    assert "total_records" in data
    assert "total_tokens" in data
    assert "total_cost_usd" in data
    assert "saved_fast_path_calls" in data
    assert data["total_records"] >= 3


def test_usage_summary_internal_key_access(client: TestClient, internal_headers: dict):
    res = client.get("/api/v1/usage", headers=internal_headers)
    assert res.status_code == 200
    assert res.json()["total_records"] >= 3


def test_usage_summary_alias_endpoint(client: TestClient, global_admin_headers: dict):
    res = client.get("/api/v1/usage/summary", headers=global_admin_headers)
    assert res.status_code == 200
    data = res.json()
    assert "total_records" in data
    assert "total_tokens_input" in data
    assert "total_tokens_output" in data
    assert "total_tokens" in data
    assert "total_cost_usd" in data
    assert "saved_fast_path_calls" in data
    assert data["total_records"] >= 3


def test_usage_by_user(client: TestClient, global_admin_headers: dict):
    res = client.get("/api/v1/usage/by-user", headers=global_admin_headers)
    assert res.status_code == 200
    users = res.json()
    assert len(users) >= 2
    user_names = [u["usuario"] for u in users]
    assert "dr_perez" in user_names
    assert "auditor_1" in user_names

    perez = next(u for u in users if u["usuario"] == "dr_perez")
    assert perez["rol"] == "PERFIL_IPS_MEDICO"
    assert perez["org_id"] == "sigires"
    assert perez["site_id"] == "site-sura"
    assert perez["llm_requests"] >= 1
    assert perez["total_tokens"] > 0

    auditor = next(u for u in users if u["usuario"] == "auditor_1")
    assert auditor["rol"] == "PERFIL_EPS_AUDITOR"
    assert auditor["fast_path_requests"] >= 1


def test_usage_by_role(client: TestClient, global_admin_headers: dict):
    res = client.get("/api/v1/usage/by-role", headers=global_admin_headers)
    assert res.status_code == 200
    roles = res.json()
    assert len(roles) >= 2
    role_names = [r["rol"] for r in roles]
    assert "PERFIL_IPS_MEDICO" in role_names
    assert "PERFIL_EPS_AUDITOR" in role_names
    assert all("org_id" in r for r in roles)


def test_usage_by_model(client: TestClient, global_admin_headers: dict):
    res = client.get("/api/v1/usage/by-model", headers=global_admin_headers)
    assert res.status_code == 200
    models = res.json()
    assert len(models) >= 1
    assert "model" in models[0]
    assert "total_requests" in models[0]


def test_usage_records_paginated(client: TestClient, global_admin_headers: dict):
    res = client.get("/api/v1/usage/records?limit=10", headers=global_admin_headers)
    assert res.status_code == 200
    records = res.json()
    assert len(records) >= 3
    rec = records[0]
    assert "ledger_id" in rec
    assert "org_id" in rec
    assert "site_id" in rec
    assert "site_code" in rec
    assert "operacion" in rec
    assert "tokens_input" in rec
    assert "client_id" not in rec
    assert "tenant_id" not in rec
    assert "ips_code" not in rec


def test_org_admin_scoping(client: TestClient, org_admin_headers: dict):
    # org_admin_headers is bound to "sigires"
    res = client.get("/api/v1/usage?org_id=otra_empresa", headers=org_admin_headers)
    assert res.status_code == 200
    # Should only return records where org_id == "sigires"
    users_res = client.get("/api/v1/usage/by-user?org_id=otra_empresa", headers=org_admin_headers)
    assert users_res.status_code == 200
    assert len(users_res.json()) >= 1
    for u in users_res.json():
        assert u["org_id"] == "sigires"

    sites_res = client.get("/api/v1/usage/by-site?org_id=otra_empresa", headers=org_admin_headers)
    assert sites_res.status_code == 200
    for s in sites_res.json():
        assert s["org_id"] == "sigires"


def test_cors_origins_includes_admin_console():
    assert "http://localhost:5174" in settings.CORS_ORIGINS
    assert "http://127.0.0.1:5174" in settings.CORS_ORIGINS


def test_usage_by_role_enriched_and_site_filter(client: TestClient, global_admin_headers: dict):
    res = client.get("/api/v1/usage/by-role", headers=global_admin_headers)
    assert res.status_code == 200
    roles = res.json()
    assert len(roles) >= 2
    for role in roles:
        assert "total_tokens_input" in role
        assert "total_tokens_output" in role
        assert role["total_tokens_input"] + role["total_tokens_output"] == role["total_tokens"]

    medico = next(r for r in roles if r["rol"] == "PERFIL_IPS_MEDICO")
    assert medico["total_tokens_input"] >= 120
    assert medico["total_tokens_output"] >= 80

    filtered = client.get("/api/v1/usage/by-role?site_id=corp-site-1", headers=global_admin_headers)
    assert filtered.status_code == 200
    filtered_roles = filtered.json()
    assert len(filtered_roles) == 1
    assert filtered_roles[0]["rol"] == "PERFIL_EMPRESA"
    assert filtered_roles[0]["org_id"] == "otra_empresa"
    assert filtered_roles[0]["total_tokens_input"] == 50
    assert filtered_roles[0]["total_tokens_output"] == 50


def test_usage_by_model_enriched_and_site_filter(client: TestClient, global_admin_headers: dict):
    res = client.get("/api/v1/usage/by-model", headers=global_admin_headers)
    assert res.status_code == 200
    models = res.json()
    assert len(models) >= 1
    for model in models:
        assert "total_tokens_input" in model
        assert "total_tokens_output" in model
        assert "avg_latencia_ms" in model
        assert isinstance(model["avg_latencia_ms"], int)
        assert model["avg_latencia_ms"] >= 0

    filtered = client.get("/api/v1/usage/by-model?site_id=corp-site-1", headers=global_admin_headers)
    assert filtered.status_code == 200
    filtered_models = filtered.json()
    assert len(filtered_models) == 1
    assert filtered_models[0]["model"] == "local-model"
    assert filtered_models[0]["total_tokens_input"] == 50
    assert filtered_models[0]["total_tokens_output"] == 50
    assert filtered_models[0]["avg_latencia_ms"] == 100


def test_usage_by_site_avg_latency_and_filter(client: TestClient, global_admin_headers: dict):
    legacy_res = client.get("/api/v1/usage/by-tenant", headers=global_admin_headers)
    assert legacy_res.status_code == 404

    res = client.get("/api/v1/usage/by-site", headers=global_admin_headers)
    assert res.status_code == 200
    sites = res.json()
    assert len(sites) >= 2
    for site in sites:
        assert "site_id" in site
        assert "org_id" in site
        assert "avg_latencia_ms" in site
        assert isinstance(site["avg_latencia_ms"], int)
        assert site["avg_latencia_ms"] >= 0

    filtered = client.get("/api/v1/usage/by-site?site_id=corp-site-1", headers=global_admin_headers)
    assert filtered.status_code == 200
    filtered_sites = filtered.json()
    assert len(filtered_sites) == 1
    assert filtered_sites[0]["site_id"] == "corp-site-1"
    assert filtered_sites[0]["org_id"] == "otra_empresa"
    assert filtered_sites[0]["avg_latencia_ms"] == 100


def test_usage_timeseries_and_org_admin_scoping(
    client: TestClient,
    global_admin_headers: dict,
    org_admin_headers: dict,
):
    now = datetime.now(timezone.utc)
    day_5d = (now - timedelta(days=5)).strftime("%Y-%m-%d")
    day_2d = (now - timedelta(days=2)).strftime("%Y-%m-%d")
    day_45d = (now - timedelta(days=45)).strftime("%Y-%m-%d")
    temp_ids = ["req-ts-sigires-5d", "req-ts-otra-2d", "req-ts-sigires-45d"]

    db = get_db_instance()
    with next(db.session()) as session:
        repo = LedgerRepository(session)
        repo.record_usage(
            request_id="req-ts-sigires-5d",
            org_id="sigires",
            site_id="site-sura",
            usuario="dr_perez",
            rol="PERFIL_IPS_MEDICO",
            tokens_input=30,
            tokens_output=15,
            tokens_total=45,
            costo_usd=0.012,
            latencia_ms=150,
            model="local-model",
            provider="lmstudio",
            is_llm_call=True,
            created_at=now - timedelta(days=5),
        )
        repo.record_usage(
            request_id="req-ts-otra-2d",
            org_id="otra_empresa",
            site_id="corp-site-1",
            usuario="corp_user",
            rol="PERFIL_EMPRESA",
            tokens_input=0,
            tokens_output=0,
            tokens_total=0,
            costo_usd=0.0,
            latencia_ms=3,
            model="none",
            provider="internal",
            is_llm_call=False,
            created_at=now - timedelta(days=2),
        )
        repo.record_usage(
            request_id="req-ts-sigires-45d",
            org_id="sigires",
            site_id="site-sura",
            usuario="dr_perez",
            rol="PERFIL_IPS_MEDICO",
            tokens_input=10,
            tokens_output=10,
            tokens_total=20,
            costo_usd=0.005,
            latencia_ms=120,
            model="local-model",
            provider="lmstudio",
            is_llm_call=True,
            created_at=now - timedelta(days=45),
        )

    try:
        res = client.get("/api/v1/usage/timeseries", headers=global_admin_headers)
        assert res.status_code == 200
        series = res.json()
        assert len(series) >= 3
        dates = [pt["date"] for pt in series]
        assert dates == sorted(dates)
        assert day_5d in dates
        assert day_2d in dates
        assert day_45d not in dates  # Default days=30 excludes 45 days ago

        for pt in series:
            for key in (
                "date",
                "total_requests",
                "llm_requests",
                "fast_path_requests",
                "tokens_input",
                "tokens_output",
                "tokens_total",
                "costo_usd",
            ):
                assert key in pt

        point_5d = next(pt for pt in series if pt["date"] == day_5d)
        assert point_5d["total_requests"] == 1
        assert point_5d["llm_requests"] == 1
        assert point_5d["fast_path_requests"] == 0
        assert point_5d["tokens_total"] == 45
        assert point_5d["costo_usd"] == 0.012

        # date_from overrides default days=30
        all_from = (now - timedelta(days=60)).strftime("%Y-%m-%d")
        res_60d = client.get(f"/api/v1/usage/timeseries?date_from={all_from}", headers=global_admin_headers)
        assert res_60d.status_code == 200
        dates_60d = [pt["date"] for pt in res_60d.json()]
        assert day_45d in dates_60d

        # ORG_ADMIN is forced to org_id="sigires" even if org_id=otra_empresa is requested
        scoped = client.get(
            "/api/v1/usage/timeseries?org_id=otra_empresa",
            headers=org_admin_headers,
        )
        assert scoped.status_code == 200
        scoped_dates = [pt["date"] for pt in scoped.json()]
        assert scoped_dates == sorted(scoped_dates)
        assert day_5d in scoped_dates
        assert day_2d not in scoped_dates
    finally:
        with next(db.session()) as session:
            session.execute(delete(UsageRecordORM).where(UsageRecordORM.request_id.in_(temp_ids)))
            session.commit()


def test_usage_date_filters_and_validation(client: TestClient, global_admin_headers: dict):
    res_30 = client.get("/api/v1/usage?days=30", headers=global_admin_headers)
    assert res_30.status_code == 200
    assert res_30.json()["total_records"] >= 3

    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    res_today = client.get(
        f"/api/v1/usage/summary?date_from={today_str}&date_to={today_str}",
        headers=global_admin_headers,
    )
    assert res_today.status_code == 200
    assert res_today.json()["total_records"] >= 3

    future_str = (datetime.now(timezone.utc) + timedelta(days=7)).strftime("%Y-%m-%d")
    for path in (
        "/api/v1/usage",
        "/api/v1/usage/summary",
    ):
        r = client.get(f"{path}?date_from={future_str}", headers=global_admin_headers)
        assert r.status_code == 200
        assert r.json()["total_records"] == 0
        assert r.json()["total_tokens"] == 0

    for path in (
        "/api/v1/usage/by-user",
        "/api/v1/usage/by-site",
        "/api/v1/usage/by-role",
        "/api/v1/usage/by-model",
        "/api/v1/usage/records",
        "/api/v1/usage/timeseries",
    ):
        r = client.get(f"{path}?date_from={future_str}", headers=global_admin_headers)
        assert r.status_code == 200
        assert r.json() == []

    bad_date = client.get("/api/v1/usage?date_from=invalid-date", headers=global_admin_headers)
    assert bad_date.status_code == 422


def test_legacy_sqlite_ledger_migration_preserves_records(tmp_path):
    legacy_db_path = tmp_path / "legacy.db"
    conn = sqlite3.connect(legacy_db_path)
    try:
        conn.execute(
            """
            CREATE TABLE ai_usage_ledger (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ledger_id VARCHAR(36) UNIQUE,
                request_id VARCHAR(64),
                client_id VARCHAR(100),
                tenant_id VARCHAR(100),
                usuario VARCHAR(255),
                rol VARCHAR(100),
                ips_code VARCHAR(50),
                operacion VARCHAR(100),
                tokens_input INTEGER,
                tokens_output INTEGER,
                tokens_total INTEGER,
                costo_usd FLOAT,
                latencia_ms INTEGER,
                model VARCHAR(150),
                provider VARCHAR(100),
                status VARCHAR(50),
                is_llm_call BOOLEAN,
                token_source VARCHAR(50),
                query_preview VARCHAR(255),
                created_at DATETIME
            )
            """
        )
        conn.execute(
            """
            INSERT INTO ai_usage_ledger (
                ledger_id, request_id, client_id, tenant_id, usuario, rol, ips_code,
                operacion, tokens_input, tokens_output, tokens_total, costo_usd,
                latencia_ms, model, provider, status, is_llm_call, token_source,
                query_preview, created_at
            ) VALUES (
                'legacy-uuid-1', 'req-legacy-1', 'org-legacy', 'site-legacy', 'legacy_user',
                'MEDICO', 'SC-001', 'DIAGNOSTIC_QUERY', 100, 50, 150, 0.0025,
                180, 'gpt-4o-mini', 'openai', 'COMPLETED', 1, 'provider',
                'Consulta heredada', '2026-01-15 10:30:00'
            )
            """
        )
        conn.commit()
    finally:
        conn.close()

    db = Database(f"sqlite:///{legacy_db_path.as_posix()}")
    try:
        db.create_all()

        inspector = sa_inspect(db.engine)
        columns = {col["name"] for col in inspector.get_columns("ai_usage_ledger")}
        assert "org_id" in columns
        assert "site_id" in columns
        assert "site_code" in columns
        assert "client_id" not in columns
        assert "tenant_id" not in columns
        assert "ips_code" not in columns

        indexes = {idx["name"] for idx in inspector.get_indexes("ai_usage_ledger")}
        assert "ix_ai_usage_ledger_org_id" in indexes
        assert "ix_ai_usage_ledger_site_id" in indexes

        with next(db.session()) as session:
            repo = LedgerRepository(session)
            summary = repo.get_summary(org_id="org-legacy", site_id="site-legacy")
            assert summary["total_records"] == 1
            assert summary["total_tokens_input"] == 100
            assert summary["total_tokens_output"] == 50
            assert summary["total_tokens"] == 150
            assert summary["total_cost_usd"] == 0.0025

            sites = repo.get_by_site(org_id="org-legacy")
            assert len(sites) == 1
            assert sites[0]["site_id"] == "site-legacy"
            assert sites[0]["org_id"] == "org-legacy"

            records = repo.get_recent_records(org_id="org-legacy")
            assert len(records) == 1
            assert records[0]["ledger_id"] == "legacy-uuid-1"
            assert records[0]["org_id"] == "org-legacy"
            assert records[0]["site_id"] == "site-legacy"
            assert records[0]["site_code"] == "SC-001"
            assert records[0]["usuario"] == "legacy_user"

        # Verify calling create_all() a second time is idempotent
        db.create_all()
    finally:
        db.dispose()
