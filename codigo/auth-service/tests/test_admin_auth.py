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
    assert data["role"] == "GLOBAL_ADMIN"
    assert data["username"] == "testadmin"
    assert data["org_id"] is None
    assert data["org_name"] is None
    assert data["site_label"] == "Sede"
    assert data["site_label_plural"] == "Sedes"
    assert data["expires_in_seconds"] == 3600


def test_admin_login_invalid_password(client: TestClient):
    res = client.post("/api/v1/admin/auth/login", json={
        "username": "testadmin",
        "password": "WrongPassword999!",
    })
    assert res.status_code == 401
    assert "incorrectos" in res.json()["detail"]


def test_admin_me_profile(client: TestClient, global_admin_token: str):
    res = client.get(
        "/api/v1/admin/auth/me",
        headers={"Authorization": f"Bearer {global_admin_token}"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["username"] == "testadmin"
    assert data["role"] == "GLOBAL_ADMIN"
    assert data["org_id"] is None
    assert data["org_name"] is None
    assert data["site_label"] == "Sede"
    assert data["site_label_plural"] == "Sedes"
    assert data["is_active"] is True


def test_global_admin_can_create_org_admin_and_login(client: TestClient, global_admin_token: str):
    # 1. GLOBAL_ADMIN creates ORG_ADMIN for sigires
    res = client.post(
        "/api/v1/admin/users",
        headers={"Authorization": f"Bearer {global_admin_token}"},
        json={
            "username": "sigires_admin",
            "password": "SigiresSecret2026!",
            "role": "ORG_ADMIN",
            "org_id": "sigires",
            "full_name": "Administrador SIGIRES",
        }
    )
    assert res.status_code == 201
    new_user = res.json()
    assert new_user["username"] == "sigires_admin"
    assert new_user["role"] == "ORG_ADMIN"
    assert new_user["org_id"] == "sigires"
    assert new_user["org_name"] == "SIGIRES (Procex Software S.A.S)"
    assert new_user["site_label"] == "IPS"
    assert new_user["site_label_plural"] == "IPS"

    # 2. ORG_ADMIN logs in and receives org context + site labels
    login_res = client.post("/api/v1/admin/auth/login", json={
        "username": "sigires_admin",
        "password": "SigiresSecret2026!",
    })
    assert login_res.status_code == 200
    login_data = login_res.json()
    assert login_data["role"] == "ORG_ADMIN"
    assert login_data["org_id"] == "sigires"
    assert login_data["org_name"] == "SIGIRES (Procex Software S.A.S)"
    assert login_data["site_label"] == "IPS"
    assert login_data["site_label_plural"] == "IPS"
    org_admin_token = login_data["access_token"]

    # 3. ORG_ADMIN /auth/me includes org context + site labels
    me_res = client.get(
        "/api/v1/admin/auth/me",
        headers={"Authorization": f"Bearer {org_admin_token}"},
    )
    assert me_res.status_code == 200
    me_data = me_res.json()
    assert me_data["org_id"] == "sigires"
    assert me_data["site_label"] == "IPS"
    assert me_data["site_label_plural"] == "IPS"

    # 4. ORG_ADMIN tries to create another admin -> 403 Forbidden
    forbidden_res = client.post(
        "/api/v1/admin/users",
        headers={"Authorization": f"Bearer {org_admin_token}"},
        json={
            "username": "another_admin",
            "password": "AnotherSecret2026!",
            "role": "ORG_ADMIN",
            "org_id": "sigires",
        }
    )
    assert forbidden_res.status_code == 403


def test_global_admin_lists_and_updates_admin_users(client: TestClient, global_admin_token: str):
    create_res = client.post(
        "/api/v1/admin/users",
        headers={"Authorization": f"Bearer {global_admin_token}"},
        json={
            "username": "updatable_admin",
            "password": "InitialPass2026!",
            "role": "ORG_ADMIN",
            "org_id": "otra_empresa",
            "full_name": "Admin Inicial",
        },
    )
    assert create_res.status_code == 201
    admin_id = create_res.json()["admin_id"]

    list_res = client.get(
        "/api/v1/admin/users",
        headers={"Authorization": f"Bearer {global_admin_token}"},
    )
    assert list_res.status_code == 200
    listed = {u["username"]: u for u in list_res.json()}
    assert "updatable_admin" in listed
    assert listed["updatable_admin"]["site_label"] == "Sede"

    patch_res = client.patch(
        f"/api/v1/admin/users/{admin_id}",
        headers={"Authorization": f"Bearer {global_admin_token}"},
        json={"org_id": "sigires", "full_name": "Admin Movido"},
    )
    assert patch_res.status_code == 200
    updated = patch_res.json()
    assert updated["org_id"] == "sigires"
    assert updated["full_name"] == "Admin Movido"
    assert updated["site_label"] == "IPS"
    assert updated["site_label_plural"] == "IPS"


def test_change_password(client: TestClient, global_admin_token: str):
    # 1. Create dedicated user
    client.post(
        "/api/v1/admin/users",
        headers={"Authorization": f"Bearer {global_admin_token}"},
        json={
            "username": "pwd_user",
            "password": "InitialSecret2026!",
            "role": "ORG_ADMIN",
            "org_id": "sigires",
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


def test_account_lockout(client: TestClient, global_admin_token: str):
    # Create user to test lockout
    client.post(
        "/api/v1/admin/users",
        headers={"Authorization": f"Bearer {global_admin_token}"},
        json={
            "username": "lockout_user",
            "password": "LockoutPass2026!",
            "role": "ORG_ADMIN",
            "org_id": "sigires",
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
