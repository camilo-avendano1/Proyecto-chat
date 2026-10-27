"""
Pytest fixtures for llm-gateway.
"""

import os
import tempfile
from pathlib import Path
from datetime import datetime, timezone, timedelta
import jwt
import pytest
from fastapi.testclient import TestClient

# Create a temporary sqlite db file that persists across sessions in this run
_temp_dir = tempfile.mkdtemp()
_db_path = Path(_temp_dir) / "test_ledger.db"

os.environ["DISABLE_SQLALCHEMY_CEXT"] = "1"
os.environ["ENVIRONMENT"] = "testing"
os.environ["DATABASE_URL"] = f"sqlite:///{_db_path.as_posix()}"
os.environ["LOGS_DATABASE_URL"] = "sqlite:///:memory:"
os.environ["INTERNAL_SERVICE_KEY"] = "test_internal_key_123456"
os.environ["ADMIN_JWT_SECRET"] = "test_admin_jwt_secret_9876543210_fedcba"
os.environ["FALLBACK_SIMULATION_ON_LLM_ERROR"] = "true"

from src.main import app
from src.dependencies import get_db_instance
from src.db.ledger_repo import LedgerRepository


@pytest.fixture(scope="session", autouse=True)
def init_test_db():
    db = get_db_instance()
    db.create_all()

    # Seed base test records into ledger
    with next(db.session()) as session:
        repo = LedgerRepository(session)
        # Record 1: Doctor query
        repo.record_usage(
            request_id="req-seed-1",
            client_id="sigires",
            tenant_id="tenant-sura",
            usuario="dr_perez",
            rol="PERFIL_IPS_MEDICO",
            operacion="DIAGNOSTIC_QUERY",
            tokens_input=120,
            tokens_output=80,
            tokens_total=200,
            costo_usd=0.0,
            latencia_ms=250,
            model="local-model",
            provider="lmstudio",
            status="COMPLETED",
            is_llm_call=True,
            token_source="estimated",
            query_preview="Error en variable 14",
        )
        # Record 2: Auditor fast-path greeting
        repo.record_usage(
            request_id="req-seed-2",
            client_id="sigires",
            tenant_id="tenant-sura",
            usuario="auditor_1",
            rol="PERFIL_EPS_AUDITOR",
            operacion="FAST_RESPONSE_GREETING",
            tokens_input=0,
            tokens_output=0,
            tokens_total=0,
            costo_usd=0.0,
            latencia_ms=2,
            model="none",
            provider="internal",
            status="FAST_RESPONSE_GREETING",
            is_llm_call=False,
            token_source="direct_event",
            query_preview="Hola buenos dias",
        )
        # Record 3: Another user from otra_empresa
        repo.record_usage(
            request_id="req-seed-3",
            client_id="otra_empresa",
            tenant_id="corp-div-1",
            usuario="corp_user",
            rol="PERFIL_EMPRESA",
            operacion="DIAGNOSTIC_QUERY",
            tokens_input=50,
            tokens_output=50,
            tokens_total=100,
            costo_usd=0.0,
            latencia_ms=100,
            model="local-model",
            provider="lmstudio",
            status="COMPLETED",
            is_llm_call=True,
            token_source="estimated",
            query_preview="Consulta externa",
        )


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def internal_headers() -> dict:
    return {
        "X-Internal-Key": "test_internal_key_123456",
        "Content-Type": "application/json",
    }


@pytest.fixture
def superadmin_headers() -> dict:
    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {
            "sub": "admin-1",
            "username": "superadmin",
            "role": "SUPERADMIN",
            "client_id": None,
            "aud": "saas-admin",
            "iss": "saas-auth-service",
            "exp": now + timedelta(hours=1),
            "iat": now,
        },
        "test_admin_jwt_secret_9876543210_fedcba",
        algorithm="HS256",
    )
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


@pytest.fixture
def client_admin_headers() -> dict:
    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {
            "sub": "admin-sigires-1",
            "username": "sigires_admin",
            "role": "CLIENT_ADMIN",
            "client_id": "sigires",
            "aud": "saas-admin",
            "iss": "saas-auth-service",
            "exp": now + timedelta(hours=1),
            "iat": now,
        },
        "test_admin_jwt_secret_9876543210_fedcba",
        algorithm="HS256",
    )
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
