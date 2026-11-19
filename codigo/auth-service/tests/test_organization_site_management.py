"""
Tests for Organization and Site Management Endpoints
(RBAC, CRUD, Custom Site Labels, Key Rotation, Suspend/Reactivate, SQLite Legacy Migration)
in auth-service.
"""

from datetime import datetime, timezone
import sqlite3

from fastapi.testclient import TestClient
from sqlalchemy import text

from src.config import settings
from src.core.security import hash_api_key, hash_password
from src.db.database import Database

SEEDED_SIGIRES_SITE_ID = "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d"
SEEDED_OTRA_EMPRESA_SITE_ID = "e55f6a7b-8c9d-0e1f-2a3b-4c5d6e7f8a9b"


def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _ensure_org_admin_token(
    client: TestClient,
    global_admin_token: str,
    username: str,
    password: str,
    org_id: str,
) -> str:
    create_res = client.post(
        "/api/v1/admin/users",
        headers=_auth_headers(global_admin_token),
        json={
            "username": username,
            "password": password,
            "role": "ORG_ADMIN",
            "org_id": org_id,
            "full_name": f"Admin {org_id}",
        },
    )
    assert create_res.status_code in (201, 409)
    login_res = client.post(
        "/api/v1/admin/auth/login",
        json={"username": username, "password": password},
    )
    assert login_res.status_code == 200
    return login_res.json()["access_token"]


def test_cors_origins_include_admin_console(client: TestClient):
    assert "http://localhost:5174" in settings.CORS_ORIGINS
    assert "http://127.0.0.1:5174" in settings.CORS_ORIGINS

    preflight = client.options(
        "/api/v1/admin/organizations",
        headers={
            "Origin": "http://localhost:5174",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "Authorization",
        },
    )
    assert preflight.status_code == 200
    assert preflight.headers.get("access-control-allow-origin") == "http://localhost:5174"


def test_unauthenticated_access_rejected(client: TestClient):
    assert client.get("/api/v1/admin/organizations").status_code == 401
    assert client.get("/api/v1/admin/sites").status_code == 401
    assert client.patch("/api/v1/admin/organizations/sigires", json={"site_label": "X"}).status_code == 401


def test_global_admin_custom_site_labels_and_org_admin_login_me(
    client: TestClient, global_admin_token: str
):
    headers = _auth_headers(global_admin_token)

    create_org_res = client.post(
        "/api/v1/admin/organizations",
        headers=headers,
        json={
            "org_id": "talleres_unidos",
            "nombre": "Talleres Unidos S.A.S.",
            "busqueda_api_url": "http://localhost:8001",
            "dominios_permitidos": ["https://talleres.co"],
            "site_label": "Taller",
            "site_label_plural": "Talleres",
        },
    )
    assert create_org_res.status_code == 201
    created_org = create_org_res.json()
    assert created_org["org_id"] == "talleres_unidos"
    assert created_org["site_label"] == "Taller"
    assert created_org["site_label_plural"] == "Talleres"

    create_admin_res = client.post(
        "/api/v1/admin/users",
        headers=headers,
        json={
            "username": "talleres_admin",
            "password": "TalleresPass2026!",
            "role": "ORG_ADMIN",
            "org_id": "talleres_unidos",
            "full_name": "Administrador Talleres",
        },
    )
    assert create_admin_res.status_code == 201
    assert create_admin_res.json()["site_label"] == "Taller"
    assert create_admin_res.json()["site_label_plural"] == "Talleres"

    login_res = client.post(
        "/api/v1/admin/auth/login",
        json={"username": "talleres_admin", "password": "TalleresPass2026!"},
    )
    assert login_res.status_code == 200
    login_data = login_res.json()
    assert login_data["role"] == "ORG_ADMIN"
    assert login_data["org_id"] == "talleres_unidos"
    assert login_data["org_name"] == "Talleres Unidos S.A.S."
    assert login_data["site_label"] == "Taller"
    assert login_data["site_label_plural"] == "Talleres"

    me_res = client.get(
        "/api/v1/admin/auth/me",
        headers=_auth_headers(login_data["access_token"]),
    )
    assert me_res.status_code == 200
    me_data = me_res.json()
    assert me_data["org_id"] == "talleres_unidos"
    assert me_data["org_name"] == "Talleres Unidos S.A.S."
    assert me_data["site_label"] == "Taller"
    assert me_data["site_label_plural"] == "Talleres"


def test_global_admin_creates_org_and_site_and_widget_handshake_works(
    client: TestClient, global_admin_token: str
):
    headers = _auth_headers(global_admin_token)

    # 1. List existing seeded organizations & sites
    orgs_res = client.get("/api/v1/admin/organizations", headers=headers)
    assert orgs_res.status_code == 200
    orgs_by_id = {o["org_id"]: o for o in orgs_res.json()}
    assert {"sigires", "otra_empresa"}.issubset(orgs_by_id.keys())
    assert orgs_by_id["sigires"]["site_label"] == "IPS"
    assert orgs_by_id["sigires"]["site_label_plural"] == "IPS"
    assert orgs_by_id["otra_empresa"]["site_label"] == "Sede"
    assert orgs_by_id["otra_empresa"]["site_label_plural"] == "Sedes"

    sites_res = client.get("/api/v1/admin/sites", headers=headers)
    assert sites_res.status_code == 200
    assert len(sites_res.json()) >= 4

    # 2. Create new organization retail_demo
    create_org_res = client.post(
        "/api/v1/admin/organizations",
        headers=headers,
        json={
            "org_id": "retail_demo",
            "nombre": "Retail Demo S.A.S.",
            "busqueda_api_url": "http://localhost:8001",
            "dominios_permitidos": ["https://tienda.retaildemo.co"],
            "site_label": "Sucursal",
            "site_label_plural": "Sucursales",
        },
    )
    assert create_org_res.status_code == 201
    created_org = create_org_res.json()
    assert created_org["org_id"] == "retail_demo"
    assert created_org["nombre"] == "Retail Demo S.A.S."
    assert created_org["site_label"] == "Sucursal"
    assert created_org["site_label_plural"] == "Sucursales"
    assert created_org["site_count"] == 0
    assert created_org["active_site_count"] == 0

    # Duplicate organization -> 409 Conflict
    dup_res = client.post(
        "/api/v1/admin/organizations",
        headers=headers,
        json={
            "org_id": "retail_demo",
            "nombre": "Duplicado",
        },
    )
    assert dup_res.status_code == 409

    # 3. Validation & NotFound checks for POST /sites as GLOBAL_ADMIN
    missing_org_res = client.post(
        "/api/v1/admin/sites",
        headers=headers,
        json={"nombre": "Sin Organización"},
    )
    assert missing_org_res.status_code == 422

    unknown_org_res = client.post(
        "/api/v1/admin/sites",
        headers=headers,
        json={"org_id": "org_inexistente", "nombre": "Sede Fantasma"},
    )
    assert unknown_org_res.status_code == 404

    # 4. Create site Tienda Norte under retail_demo (auto-generated site_code)
    create_site_res = client.post(
        "/api/v1/admin/sites",
        headers=headers,
        json={
            "org_id": "retail_demo",
            "nombre": "Tienda Norte",
            "dominios_permitidos": ["*"],
        },
    )
    assert create_site_res.status_code == 201
    created_site = create_site_res.json()
    assert created_site["org_id"] == "retail_demo"
    assert created_site["org_name"] == "Retail Demo S.A.S."
    assert created_site["nombre"] == "Tienda Norte"
    assert created_site["site_code"].startswith("tienda_norte_")
    assert created_site["status"] == "ACTIVE"
    api_key = created_site["api_key"]
    assert api_key.startswith("pk_live_retail_demo_")
    assert created_site["api_key_prefix"] == api_key[:16]

    # 5. Filter sites by org_id
    filtered_res = client.get("/api/v1/admin/sites?org_id=retail_demo", headers=headers)
    assert filtered_res.status_code == 200
    filtered = filtered_res.json()
    assert len(filtered) == 1
    assert filtered[0]["site_id"] == created_site["site_id"]

    # 6. Verify organization summary counts updated
    orgs_after = client.get("/api/v1/admin/organizations", headers=headers).json()
    retail_summary = next(o for o in orgs_after if o["org_id"] == "retail_demo")
    assert retail_summary["site_count"] == 1
    assert retail_summary["active_site_count"] == 1

    # 7. Returned API key works immediately on POST /api/v1/widget/session
    widget_res = client.post(
        "/api/v1/widget/session",
        headers={"X-Widget-Key": api_key},
        json={"origin": "https://retaildemo.co/widget"},
    )
    assert widget_res.status_code == 200
    session_data = widget_res.json()
    assert session_data["org_id"] == "retail_demo"
    assert session_data["site_id"] == created_site["site_id"]
    assert session_data["site_name"] == "Tienda Norte"
    assert session_data["site_code"] == created_site["site_code"]
    assert session_data["site_label"] == "Sucursal"


def test_org_admin_rbac_patch_labels_and_site_management(
    client: TestClient, global_admin_token: str
):
    global_headers = _auth_headers(global_admin_token)

    # Dedicated org so site_label edits don't mutate seeded otra_empresa
    client.post(
        "/api/v1/admin/organizations",
        headers=global_headers,
        json={
            "org_id": "comercio_rbac",
            "nombre": "Comercio RBAC S.A.S.",
            "busqueda_api_url": "http://localhost:8001",
            "dominios_permitidos": ["*"],
        },
    )
    comercio_token = _ensure_org_admin_token(
        client, global_admin_token, "comercio_admin", "ComercioPass2026!", "comercio_rbac"
    )
    comercio_headers = _auth_headers(comercio_token)

    otra_token = _ensure_org_admin_token(
        client, global_admin_token, "otra_empresa_admin", "OtraEmpresaPass2026!", "otra_empresa"
    )
    otra_headers = _auth_headers(otra_token)

    # 1. ORG_ADMIN sees ONLY otra_empresa in GET /organizations
    orgs_res = client.get("/api/v1/admin/organizations", headers=otra_headers)
    assert orgs_res.status_code == 200
    orgs_data = orgs_res.json()
    assert len(orgs_data) == 1
    assert orgs_data[0]["org_id"] == "otra_empresa"

    # 2. ORG_ADMIN sees ONLY otra_empresa sites even if requesting ?org_id=sigires
    sites_res = client.get("/api/v1/admin/sites?org_id=sigires", headers=otra_headers)
    assert sites_res.status_code == 200
    sites_data = sites_res.json()
    assert len(sites_data) >= 1
    assert all(s["org_id"] == "otra_empresa" for s in sites_data)
    assert any(s["site_id"] == SEEDED_OTRA_EMPRESA_SITE_ID for s in sites_data)

    # 3. ORG_ADMIN cannot create organizations -> 403
    forbidden_org_res = client.post(
        "/api/v1/admin/organizations",
        headers=otra_headers,
        json={"org_id": "org_no_autorizada", "nombre": "No Autorizada"},
    )
    assert forbidden_org_res.status_code == 403

    # 4. ORG_ADMIN can patch own site_label and site_label_plural -> 200
    patch_own_labels = client.patch(
        "/api/v1/admin/organizations/comercio_rbac",
        headers=comercio_headers,
        json={"site_label": "Tienda", "site_label_plural": "Tiendas"},
    )
    assert patch_own_labels.status_code == 200
    patched_org = patch_own_labels.json()
    assert patched_org["site_label"] == "Tienda"
    assert patched_org["site_label_plural"] == "Tiendas"

    # 5. ORG_ADMIN cannot patch another organization -> 403
    forbidden_other_org = client.patch(
        "/api/v1/admin/organizations/sigires",
        headers=comercio_headers,
        json={"site_label": "Tienda", "site_label_plural": "Tiendas"},
    )
    assert forbidden_other_org.status_code == 403

    # 6. ORG_ADMIN cannot patch busqueda_api_url or status on own organization -> 403
    forbidden_url_patch = client.patch(
        "/api/v1/admin/organizations/comercio_rbac",
        headers=comercio_headers,
        json={"busqueda_api_url": "https://evil.example.com"},
    )
    assert forbidden_url_patch.status_code == 403

    forbidden_status_patch = client.patch(
        "/api/v1/admin/organizations/comercio_rbac",
        headers=comercio_headers,
        json={"status": "SUSPENDED"},
    )
    assert forbidden_status_patch.status_code == 403

    # 7. ORG_ADMIN cannot create site for another organization -> 403
    forbidden_site_create = client.post(
        "/api/v1/admin/sites",
        headers=otra_headers,
        json={"org_id": "sigires", "nombre": "Sede Ajena"},
    )
    assert forbidden_site_create.status_code == 403

    # 8. ORG_ADMIN cannot update a sigires site -> 403
    forbidden_site_patch = client.patch(
        f"/api/v1/admin/sites/{SEEDED_SIGIRES_SITE_ID}",
        headers=otra_headers,
        json={"nombre": "Intento Malicioso"},
    )
    assert forbidden_site_patch.status_code == 403

    # 9. ORG_ADMIN creates own site (org_id omitted -> forced to otra_empresa)
    create_own = client.post(
        "/api/v1/admin/sites",
        headers=otra_headers,
        json={
            "nombre": "Sucursal Caribe",
            "site_code": "corp_caribe_01",
            "dominios_permitidos": ["https://caribe.otraempresa.co"],
        },
    )
    assert create_own.status_code == 201
    own_site = create_own.json()
    assert own_site["org_id"] == "otra_empresa"
    assert own_site["site_code"] == "corp_caribe_01"
    old_key = own_site["api_key"]
    site_id = own_site["site_id"]

    # Old key works on allowed origin
    assert client.post(
        "/api/v1/widget/session",
        headers={"X-Widget-Key": old_key},
        json={"origin": "https://caribe.otraempresa.co"},
    ).status_code == 200

    # 10. ORG_ADMIN updates own site and rotates API key
    rotate_res = client.patch(
        f"/api/v1/admin/sites/{site_id}",
        headers=otra_headers,
        json={
            "nombre": "Sucursal Caribe Renovada",
            "site_code": "corp_caribe_02",
            "dominios_permitidos": ["https://caribe-v2.otraempresa.co"],
            "rotate_api_key": True,
        },
    )
    assert rotate_res.status_code == 200
    rotated = rotate_res.json()
    assert rotated["nombre"] == "Sucursal Caribe Renovada"
    assert rotated["site_code"] == "corp_caribe_02"
    assert rotated["dominios_permitidos"] == ["https://caribe-v2.otraempresa.co"]
    new_key = rotated["new_api_key"]
    assert new_key is not None
    assert new_key != old_key
    assert rotated["api_key_prefix"] == new_key[:16]

    # Old key stops working with 401
    assert client.post(
        "/api/v1/widget/session",
        headers={"X-Widget-Key": old_key},
        json={"origin": "https://caribe-v2.otraempresa.co"},
    ).status_code == 401

    # New key works with 200 on updated allowed origin
    assert client.post(
        "/api/v1/widget/session",
        headers={"X-Widget-Key": new_key},
        json={"origin": "https://caribe-v2.otraempresa.co"},
    ).status_code == 200

    # 11. ORG_ADMIN suspends and reactivates own site affecting /widget/session
    suspend_res = client.patch(
        f"/api/v1/admin/sites/{site_id}",
        headers=otra_headers,
        json={"status": "SUSPENDED"},
    )
    assert suspend_res.status_code == 200
    assert suspend_res.json()["status"] == "SUSPENDED"
    assert client.post(
        "/api/v1/widget/session",
        headers={"X-Widget-Key": new_key},
        json={"origin": "https://caribe-v2.otraempresa.co"},
    ).status_code == 401

    reactivate_res = client.patch(
        f"/api/v1/admin/sites/{site_id}",
        headers=otra_headers,
        json={"status": "ACTIVE"},
    )
    assert reactivate_res.status_code == 200
    assert reactivate_res.json()["status"] == "ACTIVE"
    assert client.post(
        "/api/v1/widget/session",
        headers={"X-Widget-Key": new_key},
        json={"origin": "https://caribe-v2.otraempresa.co"},
    ).status_code == 200


def test_suspend_and_reactivate_site_validation_and_not_found(
    client: TestClient, global_admin_token: str
):
    headers = _auth_headers(global_admin_token)

    create_res = client.post(
        "/api/v1/admin/sites",
        headers=headers,
        json={
            "org_id": "otra_empresa",
            "nombre": "Sede Temporal Control",
            "dominios_permitidos": ["*"],
        },
    )
    assert create_res.status_code == 201
    site_id = create_res.json()["site_id"]
    api_key = create_res.json()["api_key"]

    assert client.post("/api/v1/widget/session", headers={"X-Widget-Key": api_key}).status_code == 200

    # Invalid status -> 422
    invalid_res = client.patch(
        f"/api/v1/admin/sites/{site_id}",
        headers=headers,
        json={"status": "ARCHIVED"},
    )
    assert invalid_res.status_code == 422

    # Not found site -> 404
    not_found_res = client.patch(
        "/api/v1/admin/sites/00000000-0000-0000-0000-000000000000",
        headers=headers,
        json={"status": "SUSPENDED"},
    )
    assert not_found_res.status_code == 404


def test_sqlite_legacy_migration(tmp_path):
    db_path = tmp_path / "legacy_auth.db"
    now_iso = datetime.now(timezone.utc).isoformat()
    sigires_key = "pk_live_sigires_8f9a2b1c3d4e5f6a"
    acme_key = "pk_live_acme_1122334455667788"
    superadmin_hash = hash_password("LegacySuper2026!")
    client_admin_hash = hash_password("LegacyClient2026!")

    raw = sqlite3.connect(str(db_path))
    try:
        raw.executescript(
            """
            CREATE TABLE clients (
                client_id VARCHAR(100) NOT NULL PRIMARY KEY,
                nombre VARCHAR(255) NOT NULL,
                busqueda_api_url VARCHAR(500) NOT NULL,
                dominios_permitidos JSON NOT NULL,
                status VARCHAR(20) NOT NULL,
                created_at DATETIME NOT NULL
            );
            CREATE TABLE tenants (
                tenant_id VARCHAR(64) NOT NULL PRIMARY KEY,
                client_id VARCHAR(100) NOT NULL REFERENCES clients(client_id),
                nombre VARCHAR(255) NOT NULL,
                codigo_eps VARCHAR(100) NOT NULL,
                dominios_permitidos JSON NOT NULL,
                api_key_hash VARCHAR(64) NOT NULL,
                api_key_prefix VARCHAR(32) NOT NULL,
                status VARCHAR(20) NOT NULL,
                created_at DATETIME NOT NULL
            );
            CREATE INDEX ix_tenants_codigo_eps ON tenants (codigo_eps);
            CREATE INDEX ix_tenants_client_id ON tenants (client_id);
            CREATE UNIQUE INDEX ix_tenants_api_key_hash ON tenants (api_key_hash);
            CREATE TABLE admin_users (
                id VARCHAR(36) NOT NULL PRIMARY KEY,
                username VARCHAR(100) NOT NULL,
                full_name VARCHAR(255),
                password_hash VARCHAR(255) NOT NULL,
                role VARCHAR(30) NOT NULL,
                client_id VARCHAR(100) REFERENCES clients(client_id),
                is_active BOOLEAN NOT NULL,
                failed_attempts INTEGER NOT NULL,
                locked_until DATETIME,
                last_login_at DATETIME,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL
            );
            CREATE INDEX ix_admin_users_role ON admin_users (role);
            CREATE INDEX ix_admin_users_client_id ON admin_users (client_id);
            CREATE UNIQUE INDEX ix_admin_users_username ON admin_users (username);
            """
        )
        raw.execute(
            "INSERT INTO clients VALUES (?, ?, ?, ?, ?, ?)",
            ("sigires", "SIGIRES (Procex Software S.A.S)", "http://localhost:8001", '["https://sigires.procex.co"]', "ACTIVE", now_iso),
        )
        raw.execute(
            "INSERT INTO clients VALUES (?, ?, ?, ?, ?, ?)",
            ("acme", "Acme Corp", "http://localhost:8009", '["*"]', "ACTIVE", now_iso),
        )
        raw.execute(
            "INSERT INTO tenants VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "tenant-sigires-1", "sigires", "EPS Sura", "eps_sura_01",
                '["https://sigires.procex.co"]', hash_api_key(sigires_key), sigires_key[:16], "ACTIVE", now_iso,
            ),
        )
        raw.execute(
            "INSERT INTO tenants VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "tenant-acme-1", "acme", "Acme HQ", "acme_hq_01",
                '["*"]', hash_api_key(acme_key), acme_key[:16], "SUSPENDED", now_iso,
            ),
        )
        raw.execute(
            "INSERT INTO admin_users VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "adm-1", "rootadmin", "Root Legacy", superadmin_hash, "SUPERADMIN", None,
                1, 0, None, None, now_iso, now_iso,
            ),
        )
        raw.execute(
            "INSERT INTO admin_users VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "adm-2", "acme_mgr", "Acme Manager", client_admin_hash, "CLIENT_ADMIN", "acme",
                1, 0, None, None, now_iso, now_iso,
            ),
        )
        raw.commit()
    finally:
        raw.close()

    db = Database(f"sqlite:///{db_path.as_posix()}")
    try:
        db.create_all()
        # Idempotent on second call
        db.create_all()

        with db.engine.connect() as conn:
            tables = {
                row[0]
                for row in conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).fetchall()
            }
            assert "clients" not in tables
            assert "tenants" not in tables
            assert "admin_users_legacy" not in tables
            assert {"organizations", "sites", "admin_users"}.issubset(tables)

            fk_violations = conn.execute(text("PRAGMA foreign_key_check")).fetchall()
            assert fk_violations == []

            orgs = {
                row.org_id: row
                for row in conn.execute(
                    text("SELECT org_id, nombre, busqueda_api_url, site_label, site_label_plural, status FROM organizations")
                ).fetchall()
            }
            assert orgs["sigires"].site_label == "IPS"
            assert orgs["sigires"].site_label_plural == "IPS"
            assert orgs["acme"].site_label == "Sede"
            assert orgs["acme"].site_label_plural == "Sedes"
            assert orgs["acme"].busqueda_api_url == "http://localhost:8009"

            sites = {
                row.site_id: row
                for row in conn.execute(
                    text("SELECT site_id, org_id, nombre, site_code, api_key_hash, api_key_prefix, status FROM sites")
                ).fetchall()
            }
            assert sites["tenant-sigires-1"].org_id == "sigires"
            assert sites["tenant-sigires-1"].site_code == "eps_sura_01"
            assert sites["tenant-sigires-1"].api_key_hash == hash_api_key(sigires_key)
            assert sites["tenant-acme-1"].org_id == "acme"
            assert sites["tenant-acme-1"].site_code == "acme_hq_01"
            assert sites["tenant-acme-1"].status == "SUSPENDED"
            assert sites["tenant-acme-1"].api_key_hash == hash_api_key(acme_key)

            admins = {
                row.username: row
                for row in conn.execute(
                    text("SELECT username, role, org_id, password_hash FROM admin_users")
                ).fetchall()
            }
            assert admins["rootadmin"].role == "GLOBAL_ADMIN"
            assert admins["rootadmin"].org_id is None
            assert admins["rootadmin"].password_hash == superadmin_hash
            assert admins["acme_mgr"].role == "ORG_ADMIN"
            assert admins["acme_mgr"].org_id == "acme"
            assert admins["acme_mgr"].password_hash == client_admin_hash
    finally:
        db.dispose()


def test_sqlite_organizations_adds_missing_site_labels(tmp_path):
    db_path = tmp_path / "partial_orgs.db"
    now_iso = datetime.now(timezone.utc).isoformat()
    raw = sqlite3.connect(str(db_path))
    try:
        raw.executescript(
            """
            CREATE TABLE organizations (
                org_id VARCHAR(100) NOT NULL PRIMARY KEY,
                nombre VARCHAR(255) NOT NULL,
                busqueda_api_url VARCHAR(500) NOT NULL,
                dominios_permitidos JSON NOT NULL,
                status VARCHAR(20) NOT NULL,
                created_at DATETIME NOT NULL
            );
            """
        )
        raw.execute(
            "INSERT INTO organizations VALUES (?, ?, ?, ?, ?, ?)",
            ("demo", "Demo Org", "http://localhost:8001", '["*"]', "ACTIVE", now_iso),
        )
        raw.commit()
    finally:
        raw.close()

    db = Database(f"sqlite:///{db_path.as_posix()}")
    try:
        db.create_all()
        with db.engine.connect() as conn:
            row = conn.execute(
                text("SELECT site_label, site_label_plural FROM organizations WHERE org_id='demo'")
            ).one()
            assert row.site_label == "Sede"
            assert row.site_label_plural == "Sedes"
    finally:
        db.dispose()
