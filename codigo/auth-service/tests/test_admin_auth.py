"""
Tests for Administrator Authentication and Management in auth-service.
"""

from fastapi.testclient import TestClient


def test_admin_login_success(client: TestClient):
    res = client.post("/api/v1/admin/auth/login", json={
        "username": "testadmin",
        "password": "TestAdminPass2026!",
    })
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert data["role"] == "SUPERADMIN"
    assert data["username"] == "testadmin"
    assert data["expires_in_seconds"] == 3600


def test_admin_login_invalid_password(client: TestClient):
    res = client.post("/api/v1/admin/auth/login", json={
        "username": "testadmin",
        "password": "WrongPassword999!",
    })
    assert res.status_code == 401
    assert "incorrectos" in res.json()["detail"]


def test_admin_me_profile(client: TestClient, superadmin_token: str):
    res = client.get(
        "/api/v1/admin/auth/me",
        headers={"Authorization": f"Bearer {superadmin_token}"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["username"] == "testadmin"
    assert data["role"] == "SUPERADMIN"
    assert data["is_active"] is True


def test_superadmin_can_create_client_admin_and_login(client: TestClient, superadmin_token: str):
    # 1. SUPERADMIN creates CLIENT_ADMIN for sigires
    res = client.post(
        "/api/v1/admin/users",
        headers={"Authorization": f"Bearer {superadmin_token}"},
        json={
            "username": "sigires_admin",
            "password": "SigiresSecret2026!",
            "role": "CLIENT_ADMIN",
            "client_id": "sigires",
            "full_name": "Administrador SIGIRES",
        }
    )
    assert res.status_code == 201
    new_user = res.json()
    assert new_user["username"] == "sigires_admin"
    assert new_user["role"] == "CLIENT_ADMIN"
    assert new_user["client_id"] == "sigires"

    # 2. CLIENT_ADMIN logs in
    login_res = client.post("/api/v1/admin/auth/login", json={
        "username": "sigires_admin",
        "password": "SigiresSecret2026!",
    })
    assert login_res.status_code == 200
    client_admin_token = login_res.json()["access_token"]

    # 3. CLIENT_ADMIN tries to create another admin -> 403 Forbidden
    forbidden_res = client.post(
        "/api/v1/admin/users",
        headers={"Authorization": f"Bearer {client_admin_token}"},
        json={
            "username": "another_admin",
            "password": "AnotherSecret2026!",
            "role": "CLIENT_ADMIN",
            "client_id": "sigires",
        }
    )
    assert forbidden_res.status_code == 403


def test_change_password(client: TestClient, superadmin_token: str):
    # 1. Create dedicated user
    client.post(
        "/api/v1/admin/users",
        headers={"Authorization": f"Bearer {superadmin_token}"},
        json={
            "username": "pwd_user",
            "password": "InitialSecret2026!",
            "role": "CLIENT_ADMIN",
            "client_id": "sigires",
        }
    )

    # 2. Login as pwd_user
    login_res = client.post("/api/v1/admin/auth/login", json={
        "username": "pwd_user",
        "password": "InitialSecret2026!",
    })
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]

    # 3. Change password
    change_res = client.post(
        "/api/v1/admin/auth/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "current_password": "InitialSecret2026!",
            "new_password": "NewSecretPass2026!",
        }
    )
    assert change_res.status_code == 200

    # 4. Login with old password fails
    old_res = client.post("/api/v1/admin/auth/login", json={
        "username": "pwd_user",
        "password": "InitialSecret2026!",
    })
    assert old_res.status_code == 401

    # 5. Login with new password succeeds
    new_res = client.post("/api/v1/admin/auth/login", json={
        "username": "pwd_user",
        "password": "NewSecretPass2026!",
    })
    assert new_res.status_code == 200


def test_account_lockout(client: TestClient, superadmin_token: str):
    # Create user to test lockout
    client.post(
        "/api/v1/admin/users",
        headers={"Authorization": f"Bearer {superadmin_token}"},
        json={
            "username": "lockout_user",
            "password": "LockoutPass2026!",
            "role": "CLIENT_ADMIN",
            "client_id": "sigires",
        }
    )

    # 5 failed attempts
    for _ in range(5):
        res = client.post("/api/v1/admin/auth/login", json={
            "username": "lockout_user",
            "password": "WrongPassword99!",
        })
        assert res.status_code in (401, 423)

    # 6th attempt should return 423 Locked
    res = client.post("/api/v1/admin/auth/login", json={
        "username": "lockout_user",
        "password": "LockoutPass2026!",
    })
    assert res.status_code == 423
    assert "bloqueada" in res.json()["detail"].lower()
