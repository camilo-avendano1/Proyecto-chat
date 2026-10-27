"""
Pytest configuration and fixtures for auth-service.
"""

import os
import pytest
from fastapi.testclient import TestClient

# Configure test environment with in-memory databases and test secrets
os.environ["DISABLE_SQLALCHEMY_CEXT"] = "1"
os.environ["ENVIRONMENT"] = "testing"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["LOGS_DATABASE_URL"] = "sqlite:///:memory:"
os.environ["WIDGET_JWT_SECRET"] = "test_widget_jwt_secret_0123456789_abcdef"
os.environ["ADMIN_JWT_SECRET"] = "test_admin_jwt_secret_9876543210_fedcba"
os.environ["BOOTSTRAP_ADMIN_USERNAME"] = "testadmin"
os.environ["BOOTSTRAP_ADMIN_PASSWORD"] = "TestAdminPass2026!"
os.environ["SEED_DEMO_DATA"] = "true"

from src.main import app
from src.dependencies import get_db_instance
from src.db.seed import seed_demo_data, bootstrap_superadmin
from src.config import settings


@pytest.fixture(scope="session", autouse=True)
def init_test_db():
    db = get_db_instance()
    db.create_all()
    with next(db.session()) as session:
        seed_demo_data(session, settings)
        bootstrap_superadmin(session, settings)


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def superadmin_token(client: TestClient) -> str:
    res = client.post("/api/v1/admin/auth/login", json={
        "username": "testadmin",
        "password": "TestAdminPass2026!",
    })
    assert res.status_code == 200
    return res.json()["access_token"]
