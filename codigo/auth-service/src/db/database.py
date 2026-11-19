"""
Capa de persistencia del Auth Service (SQLAlchemy 2.0, síncrono).
SQLite por defecto en desarrollo; PostgreSQL en producción vía DATABASE_URL
(ej. postgresql+psycopg://user:pass@host:5432/auth).
"""

import os
os.environ["DISABLE_SQLALCHEMY_CEXT"] = "1"

from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, List, Optional, Set
import uuid

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, create_engine, event, text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker
from sqlalchemy.pool import StaticPool


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def as_utc(value: Optional[datetime]) -> Optional[datetime]:
    """SQLite devuelve datetimes sin zona: se normalizan a UTC."""
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


class Base(DeclarativeBase):
    pass


class OrganizationORM(Base):
    """Organización cliente de la plataforma (ej. SIGIRES / Procex Software S.A.S)."""

    __tablename__ = "organizations"

    org_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    nombre: Mapped[str] = mapped_column(String(255))
    busqueda_api_url: Mapped[str] = mapped_column(String(500))
    dominios_permitidos: Mapped[List[str]] = mapped_column(JSON, default=list)
    site_label: Mapped[str] = mapped_column(String(50), default="Sede")
    site_label_plural: Mapped[str] = mapped_column(String(50), default="Sedes")
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class SiteORM(Base):
    """Sede o división operativa dentro de una organización (ej. en SIGIRES: una IPS/EPS)."""

    __tablename__ = "sites"

    site_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.org_id"), index=True)
    nombre: Mapped[str] = mapped_column(String(255))
    site_code: Mapped[str] = mapped_column(String(100), index=True)
    dominios_permitidos: Mapped[List[str]] = mapped_column(JSON, default=list)
    api_key_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    api_key_prefix: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    def is_origin_allowed(self, origin: Optional[str]) -> bool:
        allowed_list = [(d or "").rstrip("/") for d in (self.dominios_permitidos or [])]
        if "*" in allowed_list:
            return True
        if not origin:
            return False
        clean_origin = origin.rstrip("/")
        return any(clean_origin == allowed for allowed in allowed_list if allowed)


class AdminUserORM(Base):
    """Administrador de la plataforma (GLOBAL_ADMIN u ORG_ADMIN)."""

    __tablename__ = "admin_users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    username: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    full_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(30), index=True)
    org_id: Mapped[Optional[str]] = mapped_column(ForeignKey("organizations.org_id"), nullable=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    failed_attempts: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)


def _sqlite_table_exists(conn: Connection, table_name: str) -> bool:
    return bool(
        conn.execute(
            text("SELECT 1 FROM sqlite_master WHERE type='table' AND name=:t"),
            {"t": table_name},
        ).scalar()
    )


def _sqlite_columns(conn: Connection, table_name: str) -> Set[str]:
    return {
        row[1]
        for row in conn.execute(text(f'PRAGMA table_info("{table_name}")')).fetchall()
    }


def _rebuild_legacy_admin_users_sqlite(conn: Connection) -> None:
    """Reconstruye `admin_users` migrando `client_id` -> `org_id` y roles heredados."""
    conn.execute(text("ALTER TABLE admin_users RENAME TO admin_users_legacy"))
    legacy_indexes = [
        row[1]
        for row in conn.execute(text("PRAGMA index_list('admin_users_legacy')")).fetchall()
        if row[3] == "c"
    ]
    for idx_name in legacy_indexes:
        conn.execute(text(f'DROP INDEX IF EXISTS "{idx_name}"'))
    for idx_name in ("ix_admin_users_username", "ix_admin_users_role", "ix_admin_users_client_id"):
        conn.execute(text(f'DROP INDEX IF EXISTS "{idx_name}"'))

    Base.metadata.tables["admin_users"].create(bind=conn, checkfirst=True)
    conn.execute(
        text(
            """
            INSERT INTO admin_users (
                id, username, full_name, password_hash, role, org_id,
                is_active, failed_attempts, locked_until, last_login_at, created_at, updated_at
            )
            SELECT
                id, username, full_name, password_hash,
                CASE
                    WHEN role = 'SUPERADMIN' THEN 'GLOBAL_ADMIN'
                    WHEN role = 'CLIENT_ADMIN' THEN 'ORG_ADMIN'
                    ELSE role
                END,
                client_id,
                is_active, failed_attempts, locked_until, last_login_at, created_at, updated_at
            FROM admin_users_legacy
            """
        )
    )
    conn.execute(text("DROP TABLE admin_users_legacy"))


def _migrate_legacy_auth_sqlite(engine: Engine) -> None:
    """Migra tablas heredadas clients/tenants/admin_users -> organizations/sites/admin_users en SQLite."""
    if engine.dialect.name != "sqlite":
        return

    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        has_clients = _sqlite_table_exists(conn, "clients")
        has_organizations = _sqlite_table_exists(conn, "organizations")

        if has_clients and not has_organizations:
            conn.execute(text("PRAGMA foreign_keys=OFF"))
            conn.execute(text("BEGIN"))
            try:
                Base.metadata.tables["organizations"].create(bind=conn, checkfirst=True)
                Base.metadata.tables["sites"].create(bind=conn, checkfirst=True)

                conn.execute(
                    text(
                        """
                        INSERT INTO organizations (
                            org_id, nombre, busqueda_api_url, dominios_permitidos,
                            site_label, site_label_plural, status, created_at
                        )
                        SELECT
                            client_id,
                            nombre,
                            busqueda_api_url,
                            dominios_permitidos,
                            CASE WHEN client_id = 'sigires' THEN 'IPS' ELSE 'Sede' END,
                            CASE WHEN client_id = 'sigires' THEN 'IPS' ELSE 'Sedes' END,
                            status,
                            created_at
                        FROM clients
                        """
                    )
                )

                if _sqlite_table_exists(conn, "tenants"):
                    conn.execute(
                        text(
                            """
                            INSERT INTO sites (
                                site_id, org_id, nombre, site_code, dominios_permitidos,
                                api_key_hash, api_key_prefix, status, created_at
                            )
                            SELECT
                                tenant_id, client_id, nombre, codigo_eps, dominios_permitidos,
                                api_key_hash, api_key_prefix, status, created_at
                            FROM tenants
                            """
                        )
                    )

                if _sqlite_table_exists(conn, "admin_users") and "client_id" in _sqlite_columns(conn, "admin_users"):
                    _rebuild_legacy_admin_users_sqlite(conn)

                if _sqlite_table_exists(conn, "tenants"):
                    conn.execute(text("DROP TABLE tenants"))
                conn.execute(text("DROP TABLE clients"))

                conn.execute(text("COMMIT"))
            except Exception:
                conn.execute(text("ROLLBACK"))
                raise
            finally:
                conn.execute(text("PRAGMA foreign_keys=ON"))

        elif has_organizations:
            cols = _sqlite_columns(conn, "organizations")
            if "site_label" not in cols:
                conn.execute(
                    text("ALTER TABLE organizations ADD COLUMN site_label VARCHAR(50) NOT NULL DEFAULT 'Sede'")
                )
            if "site_label_plural" not in cols:
                conn.execute(
                    text("ALTER TABLE organizations ADD COLUMN site_label_plural VARCHAR(50) NOT NULL DEFAULT 'Sedes'")
                )


class Database:
    """Encapsula engine y fábrica de sesiones."""

    def __init__(self, database_url: str):
        connect_args = {}
        engine_kwargs = {"pool_pre_ping": True}
        if database_url.startswith("sqlite"):
            connect_args["check_same_thread"] = False
            db_path = database_url.split("///", 1)[-1]
            if db_path == ":memory:" or ":memory:" in database_url:
                engine_kwargs["poolclass"] = StaticPool
            elif db_path:
                Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine(database_url, connect_args=connect_args, **engine_kwargs)
        if database_url.startswith("sqlite"):
            @event.listens_for(self.engine, "connect")
            def _pragmas(dbapi_conn, _record):  # pragma: no cover
                cursor = dbapi_conn.cursor()
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.close()
        self.SessionLocal = sessionmaker(bind=self.engine, expire_on_commit=False)

    def create_all(self) -> None:
        if self.engine.dialect.name == "sqlite":
            _migrate_legacy_auth_sqlite(self.engine)
        Base.metadata.create_all(self.engine)

    def session(self) -> Iterator[Session]:
        db = self.SessionLocal()
        try:
            yield db
        finally:
            db.close()

    def dispose(self) -> None:
        self.engine.dispose()
