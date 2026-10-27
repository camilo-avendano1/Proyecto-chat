"""
Capa de persistencia del Auth Service (SQLAlchemy 2.0, síncrono).
SQLite por defecto en desarrollo; PostgreSQL en producción vía DATABASE_URL
(ej. postgresql+psycopg://user:pass@host:5432/auth).
"""

import os
os.environ["DISABLE_SQLALCHEMY_CEXT"] = "1"

from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, List, Optional
import uuid

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def as_utc(value: Optional[datetime]) -> Optional[datetime]:
    """SQLite devuelve datetimes sin zona: se normalizan a UTC."""
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


class Base(DeclarativeBase):
    pass


class ClientORM(Base):
    """Empresa cliente de la plataforma (ej. SIGIRES / Procex Software S.A.S)."""

    __tablename__ = "clients"

    client_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    nombre: Mapped[str] = mapped_column(String(255))
    busqueda_api_url: Mapped[str] = mapped_column(String(500))
    dominios_permitidos: Mapped[List[str]] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class TenantORM(Base):
    """División o entidad dentro de un cliente (en SIGIRES: una EPS)."""

    __tablename__ = "tenants"

    tenant_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    client_id: Mapped[str] = mapped_column(ForeignKey("clients.client_id"), index=True)
    nombre: Mapped[str] = mapped_column(String(255))
    codigo_eps: Mapped[str] = mapped_column(String(100), index=True)
    dominios_permitidos: Mapped[List[str]] = mapped_column(JSON, default=list)
    api_key_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    api_key_prefix: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    def is_origin_allowed(self, origin: str) -> bool:
        if not origin:
            return False
        clean_origin = origin.rstrip("/")
        for allowed in self.dominios_permitidos or []:
            clean_allowed = allowed.rstrip("/")
            if clean_allowed == "*" or clean_origin == clean_allowed:
                return True
        return False


class AdminUserORM(Base):
    """Administrador de la plataforma (SUPERADMIN o CLIENT_ADMIN)."""

    __tablename__ = "admin_users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    username: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    full_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(30), index=True)
    client_id: Mapped[Optional[str]] = mapped_column(ForeignKey("clients.client_id"), nullable=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    failed_attempts: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)


class Database:
    """Encapsula engine y fábrica de sesiones."""

    def __init__(self, database_url: str):
        connect_args = {}
        if database_url.startswith("sqlite"):
            connect_args["check_same_thread"] = False
            db_path = database_url.split("///", 1)[-1]
            if db_path and db_path != ":memory:":
                Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine(database_url, pool_pre_ping=True, connect_args=connect_args)
        if database_url.startswith("sqlite"):
            @event.listens_for(self.engine, "connect")
            def _pragmas(dbapi_conn, _record):  # pragma: no cover
                cursor = dbapi_conn.cursor()
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.close()
        self.SessionLocal = sessionmaker(bind=self.engine, expire_on_commit=False)

    def create_all(self) -> None:
        Base.metadata.create_all(self.engine)

    def session(self) -> Iterator[Session]:
        db = self.SessionLocal()
        try:
            yield db
        finally:
            db.close()

    def dispose(self) -> None:
        self.engine.dispose()
