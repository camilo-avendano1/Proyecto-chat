"""
Modelos ORM para el libro de consumo de IA (Usage Ledger).
"""

import os
os.environ["DISABLE_SQLALCHEMY_CEXT"] = "1"

from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Optional
import uuid

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Engine,
    Float,
    Integer,
    String,
    create_engine,
    event,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class UsageRecordORM(Base):
    __tablename__ = "ai_usage_ledger"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ledger_id: Mapped[str] = mapped_column(String(36), unique=True, index=True, default=lambda: str(uuid.uuid4()))
    request_id: Mapped[Optional[str]] = mapped_column(String(64), index=True, nullable=True)
    org_id: Mapped[str] = mapped_column(String(100), index=True, default="default")
    site_id: Mapped[str] = mapped_column(String(100), index=True, default="unknown")
    usuario: Mapped[str] = mapped_column(String(255), index=True, default="anonimo")
    rol: Mapped[Optional[str]] = mapped_column(String(100), index=True, nullable=True)
    site_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    operacion: Mapped[str] = mapped_column(String(100), index=True, default="INFERENCE")
    tokens_input: Mapped[int] = mapped_column(Integer, default=0)
    tokens_output: Mapped[int] = mapped_column(Integer, default=0)
    tokens_total: Mapped[int] = mapped_column(Integer, default=0)
    costo_usd: Mapped[float] = mapped_column(Float, default=0.0)
    latencia_ms: Mapped[int] = mapped_column(Integer, default=0)
    model: Mapped[Optional[str]] = mapped_column(String(150), index=True, nullable=True)
    provider: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(50), index=True, default="COMPLETED")
    is_llm_call: Mapped[bool] = mapped_column(Boolean, default=True)
    token_source: Mapped[str] = mapped_column(String(50), default="estimated")
    query_preview: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)


def _migrate_legacy_ledger_sqlite(engine: Engine) -> None:
    """Migra columnas heredadas client_id/tenant_id/ips_code -> org_id/site_id/site_code en SQLite."""
    if engine.dialect.name != "sqlite":
        return

    column_renames = (
        ("client_id", "org_id"),
        ("tenant_id", "site_id"),
        ("ips_code", "site_code"),
    )

    with engine.begin() as conn:
        exists = conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name='ai_usage_ledger'")
        ).scalar()
        if not exists:
            return

        cols = {
            row[1]
            for row in conn.execute(text('PRAGMA table_info("ai_usage_ledger")')).fetchall()
        }
        for old_col, new_col in column_renames:
            if old_col in cols and new_col not in cols:
                conn.execute(
                    text(f'ALTER TABLE "ai_usage_ledger" RENAME COLUMN "{old_col}" TO "{new_col}"')
                )
                cols.remove(old_col)
                cols.add(new_col)

        if "org_id" in cols:
            conn.execute(
                text('CREATE INDEX IF NOT EXISTS "ix_ai_usage_ledger_org_id" ON "ai_usage_ledger" ("org_id")')
            )
        if "site_id" in cols:
            conn.execute(
                text('CREATE INDEX IF NOT EXISTS "ix_ai_usage_ledger_site_id" ON "ai_usage_ledger" ("site_id")')
            )


class Database:
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
            def _pragmas(dbapi_conn, _record):
                cursor = dbapi_conn.cursor()
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA busy_timeout=5000")
                cursor.close()
        self.SessionLocal = sessionmaker(bind=self.engine, expire_on_commit=False)

    def create_all(self) -> None:
        _migrate_legacy_ledger_sqlite(self.engine)
        Base.metadata.create_all(self.engine)

    def session(self) -> Iterator[Session]:
        db = self.SessionLocal()
        try:
            yield db
        finally:
            db.close()

    def dispose(self) -> None:
        self.engine.dispose()
