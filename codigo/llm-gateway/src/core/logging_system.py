"""
Sistema de Logs Estructurados y Auditoría Persistente (módulo común a los microservicios).
Desarrollado por: Juan Camilo Avendaño, Fran Sneider Quincha, Adriana Moreno.

NOTA: Este archivo es idéntico en auth-service, llm-gateway y back-chat.
Si lo modifica, replique el cambio en los tres servicios.
"""

from __future__ import annotations

import os
os.environ["DISABLE_SQLALCHEMY_CEXT"] = "1"

import contextvars
from datetime import datetime, timezone
import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import queue
import sys
import threading
import time
from typing import Any, Callable, Dict, List, Optional
import uuid

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Float,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    create_engine,
    event,
    func,
    insert,
    select,
)
from sqlalchemy.engine import Engine

request_id_ctx: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("request_id", default=None)

_HANDLER_MARK = "_saas_structured_handler"


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if not getattr(record, "request_id", None):
            record.request_id = request_id_ctx.get()
        return True


class JsonFormatter(logging.Formatter):
    EXTRA_KEYS = ("request_id", "audit_data", "message_audit", "extra_data")

    def __init__(self, service: str):
        super().__init__()
        self.service = service

    def format(self, record: logging.LogRecord) -> str:
        payload: Dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "service": self.service,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key in self.EXTRA_KEYS:
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def setup_logging(
    service: str,
    level: str = "INFO",
    log_dir: Optional[str] = "logs",
    json_console: bool = False,
    max_bytes: int = 10 * 1024 * 1024,
    backup_count: int = 10,
) -> None:
    root = logging.getLogger()
    root.setLevel(level.upper())

    for handler in list(root.handlers):
        if getattr(handler, _HANDLER_MARK, False):
            root.removeHandler(handler)
            handler.close()

    request_filter = RequestIdFilter()
    json_formatter = JsonFormatter(service)

    console = logging.StreamHandler(sys.stdout)
    if json_console:
        console.setFormatter(json_formatter)
    else:
        console.setFormatter(
            logging.Formatter(f"%(asctime)s [%(levelname)s] {service} %(name)s: %(message)s")
        )
    console.addFilter(request_filter)
    setattr(console, _HANDLER_MARK, True)
    root.addHandler(console)

    if log_dir:
        path = Path(log_dir)
        path.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            path / f"{service}.jsonl",
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        file_handler.setFormatter(json_formatter)
        file_handler.addFilter(request_filter)
        setattr(file_handler, _HANDLER_MARK, True)
        root.addHandler(file_handler)


logs_metadata = MetaData()

security_events_table = Table(
    "security_events",
    logs_metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("event_id", String(36), unique=True, nullable=False),
    Column("service", String(50), index=True, nullable=False),
    Column("event_type", String(100), index=True, nullable=False),
    Column("severity", String(20), index=True, nullable=False),
    Column("client_id", String(100), index=True),
    Column("tenant_id", String(100), index=True),
    Column("usuario", String(255), index=True),
    Column("ips_code", String(50)),
    Column("ip_address", String(64)),
    Column("request_id", String(64), index=True),
    Column("details", JSON),
    Column("created_at", DateTime(timezone=True), index=True, nullable=False),
)

message_logs_table = Table(
    "message_logs",
    logs_metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("log_id", String(36), unique=True, nullable=False),
    Column("service", String(50), index=True, nullable=False),
    Column("direction", String(20), index=True, nullable=False),
    Column("client_id", String(100), index=True),
    Column("tenant_id", String(100), index=True),
    Column("usuario", String(255), index=True),
    Column("rol", String(100), index=True),
    Column("ips_code", String(50)),
    Column("request_id", String(64), index=True),
    Column("content", Text),
    Column("tokens", Integer, default=0),
    Column("costo_usd", Float, default=0.0),
    Column("latencia_ms", Integer, default=0),
    Column("model", String(150)),
    Column("status", String(50), index=True),
    Column("created_at", DateTime(timezone=True), index=True, nullable=False),
)

system_errors_table = Table(
    "system_errors",
    logs_metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("error_id", String(36), unique=True, nullable=False),
    Column("service", String(50), index=True, nullable=False),
    Column("error_type", String(100), index=True, nullable=False),
    Column("message", Text),
    Column("exception", Text),
    Column("client_id", String(100), index=True),
    Column("tenant_id", String(100), index=True),
    Column("usuario", String(255)),
    Column("request_id", String(64), index=True),
    Column("created_at", DateTime(timezone=True), index=True, nullable=False),
)

TABLES: Dict[str, Table] = {
    "security_events": security_events_table,
    "message_logs": message_logs_table,
    "system_errors": system_errors_table,
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def create_logs_engine(database_url: str) -> Engine:
    connect_args: Dict[str, Any] = {}
    if database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
        db_path = database_url.split("///", 1)[-1]
        if db_path and db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    engine = create_engine(database_url, pool_pre_ping=True, connect_args=connect_args)

    if database_url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def _sqlite_pragmas(dbapi_conn, _record):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.close()

    return engine


class AuditLogStore:
    def __init__(self, database_url: str, batch_size: int = 200, max_queue: int = 10000):
        self.database_url = database_url
        self.engine = create_logs_engine(database_url)
        logs_metadata.create_all(self.engine)
        self._batch_size = batch_size
        self._queue: "queue.Queue[Optional[tuple]]" = queue.Queue(maxsize=max_queue)
        self._closed = False
        self._thread = threading.Thread(target=self._worker, name="audit-log-writer", daemon=True)
        self._thread.start()
        self._logger = logging.getLogger("audit.store")

    def enqueue(self, table: str, row: Dict[str, Any]) -> None:
        if self._closed:
            return
        try:
            self._queue.put_nowait((table, row))
        except queue.Full:
            self._logger.error("Cola de auditoría llena: se descarta registro de %s", table)

    def _worker(self) -> None:
        while True:
            item = self._queue.get()
            if item is None:
                self._queue.task_done()
                return
            batch = [item]
            while len(batch) < self._batch_size:
                try:
                    nxt = self._queue.get_nowait()
                except queue.Empty:
                    break
                if nxt is None:
                    self._queue.put_nowait(None)
                    self._queue.task_done()
                    break
                batch.append(nxt)
            try:
                grouped: Dict[str, List[Dict[str, Any]]] = {}
                for table_name, row in batch:
                    grouped.setdefault(table_name, []).append(row)
                with self.engine.begin() as conn:
                    for table_name, rows in grouped.items():
                        conn.execute(insert(TABLES[table_name]), rows)
            except Exception:
                logging.getLogger("audit.store").exception("No se pudo persistir lote de auditoría")
            finally:
                for _ in batch:
                    self._queue.task_done()

    def flush(self, timeout: float = 5.0) -> None:
        deadline = time.monotonic() + timeout
        while self._queue.unfinished_tasks and time.monotonic() < deadline:
            time.sleep(0.01)

    def close(self) -> None:
        if self._closed:
            return
        self.flush()
        self._closed = True
        self._queue.put(None)
        self._thread.join(timeout=5)
        self.engine.dispose()

    def query(
        self,
        table: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        self.flush()
        tbl = TABLES[table]
        stmt = select(tbl)
        for key, value in (filters or {}).items():
            if value is not None and key in tbl.c:
                stmt = stmt.where(tbl.c[key] == value)
        stmt = stmt.order_by(tbl.c.id.desc()).limit(limit).offset(offset)
        with self.engine.connect() as conn:
            rows = conn.execute(stmt).mappings().all()
        result = []
        for row in rows:
            item = dict(row)
            item.pop("id", None)
            created = item.get("created_at")
            if isinstance(created, datetime):
                if created.tzinfo is None:
                    created = created.replace(tzinfo=timezone.utc)
                item["created_at"] = created.isoformat()
            result.append(item)
        return result

    def count(self, table: str, filters: Optional[Dict[str, Any]] = None) -> int:
        self.flush()
        tbl = TABLES[table]
        stmt = select(func.count()).select_from(tbl)
        for key, value in (filters or {}).items():
            if value is not None and key in tbl.c:
                stmt = stmt.where(tbl.c[key] == value)
        with self.engine.connect() as conn:
            return int(conn.execute(stmt).scalar() or 0)


security_logger = logging.getLogger("security.audit")
message_logger = logging.getLogger("chat.messages")
error_logger = logging.getLogger("system.errors")


class AuditLogger:
    def __init__(
        self,
        service: str,
        store_factory: Callable[[], Optional[AuditLogStore]],
        max_content_chars: int = 4000,
    ):
        self.service = service
        self._store_factory = store_factory
        self._store: Optional[AuditLogStore] = None
        self._store_lock = threading.Lock()
        self.max_content_chars = max_content_chars

    @property
    def store(self) -> Optional[AuditLogStore]:
        if self._store is None:
            with self._store_lock:
                if self._store is None:
                    self._store = self._store_factory()
        return self._store

    def reset_store(self, store: Optional[AuditLogStore]) -> None:
        with self._store_lock:
            if self._store is not None and self._store is not store:
                self._store.close()
            self._store = store

    def close(self) -> None:
        if self._store is not None:
            self._store.close()

    def _persist(self, table: str, row: Dict[str, Any]) -> None:
        store = self.store
        if store is not None:
            store.enqueue(table, row)

    def log_security_event(
        self,
        event_type: str,
        severity: str,
        client_id: Optional[str] = "unknown",
        tenant_id: Optional[str] = "unknown",
        usuario: Optional[str] = "unknown",
        details: Optional[Dict[str, Any]] = None,
        ips_code: Optional[str] = None,
        ip_address: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        row = {
            "event_id": str(uuid.uuid4()),
            "service": self.service,
            "event_type": event_type,
            "severity": severity.upper(),
            "client_id": client_id or "unknown",
            "tenant_id": tenant_id or "unknown",
            "usuario": usuario or "unknown",
            "ips_code": ips_code,
            "ip_address": ip_address,
            "request_id": request_id or request_id_ctx.get() or str(uuid.uuid4()),
            "details": details or {},
            "created_at": _utcnow(),
        }
        msg = (
            f"[SECURITY-{row['severity']}] {event_type} | User: {row['usuario']} | "
            f"Tenant: {row['tenant_id']} | Details: {json.dumps(row['details'], ensure_ascii=False, default=str)}"
        )
        extra = {"audit_data": {**row, "created_at": row["created_at"].isoformat()}, "request_id": row["request_id"]}
        if row["severity"] in ("CRITICAL", "HIGH"):
            security_logger.error(msg, extra=extra)
        elif row["severity"] == "MEDIUM":
            security_logger.warning(msg, extra=extra)
        else:
            security_logger.info(msg, extra=extra)
        self._persist("security_events", row)
        return row

    def log_auth_failure(
        self,
        reason: str,
        origin: Optional[str] = None,
        api_key_preview: Optional[str] = None,
        ip_address: Optional[str] = None,
        client_id: str = "unknown",
        tenant_id: str = "unknown",
        usuario: str = "unauthenticated",
        event_type: str = "AUTH_FAILURE",
        severity: str = "HIGH",
    ) -> Dict[str, Any]:
        return self.log_security_event(
            event_type=event_type,
            severity=severity,
            client_id=client_id,
            tenant_id=tenant_id,
            usuario=usuario,
            details={"reason": reason, "origin": origin, "api_key_preview": api_key_preview},
            ip_address=ip_address,
        )

    def log_message(
        self,
        direction: str,
        client_id: str,
        tenant_id: str,
        usuario: str,
        content: str,
        rol: Optional[str] = None,
        tokens: int = 0,
        costo_usd: float = 0.0,
        latencia_ms: int = 0,
        status: str = "PROCESSED",
        model: Optional[str] = None,
        ips_code: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        row = {
            "log_id": str(uuid.uuid4()),
            "service": self.service,
            "direction": direction,
            "client_id": client_id,
            "tenant_id": tenant_id,
            "usuario": usuario,
            "rol": rol,
            "ips_code": ips_code,
            "request_id": request_id or request_id_ctx.get() or str(uuid.uuid4()),
            "content": (content or "")[: self.max_content_chars],
            "tokens": int(tokens or 0),
            "costo_usd": float(costo_usd or 0.0),
            "latencia_ms": int(latencia_ms or 0),
            "model": model,
            "status": status,
            "created_at": _utcnow(),
        }
        tag = "MSG-IN" if direction == "INCOMING" else "MSG-OUT"
        message_logger.info(
            f"[{tag}] Req: {row['request_id']} | Client: {client_id} | Tenant: {tenant_id} | User: {usuario} | "
            f"Status: {status} | Tokens: {row['tokens']} | Latency: {row['latencia_ms']}ms | Len: {len(content or '')}",
            extra={
                "message_audit": {k: v for k, v in row.items() if k not in ("content", "created_at")},
                "request_id": row["request_id"],
            },
        )
        self._persist("message_logs", row)
        return row

    def log_message_in(self, client_id: str, tenant_id: str, usuario: str, content: str, **kwargs: Any) -> Dict[str, Any]:
        kwargs.setdefault("status", "RECEIVED")
        return self.log_message("INCOMING", client_id, tenant_id, usuario, content, **kwargs)

    def log_message_out(self, client_id: str, tenant_id: str, usuario: str, content: str, **kwargs: Any) -> Dict[str, Any]:
        kwargs.setdefault("status", "COMPLETED")
        return self.log_message("OUTGOING", client_id, tenant_id, usuario, content, **kwargs)

    def log_system_error(
        self,
        error_type: str,
        message: str,
        client_id: str = "unknown",
        tenant_id: str = "unknown",
        usuario: str = "system",
        request_id: Optional[str] = None,
        exception_str: Optional[str] = None,
    ) -> Dict[str, Any]:
        row = {
            "error_id": str(uuid.uuid4()),
            "service": self.service,
            "error_type": error_type,
            "message": (message or "")[: self.max_content_chars],
            "exception": exception_str,
            "client_id": client_id,
            "tenant_id": tenant_id,
            "usuario": usuario,
            "request_id": request_id or request_id_ctx.get(),
            "created_at": _utcnow(),
        }
        error_logger.error(
            f"[SYS-ERROR] Type: {error_type} | User: {usuario} | Tenant: {tenant_id} | Msg: {message} | Exc: {exception_str}",
            extra={"request_id": row["request_id"]},
        )
        self._persist("system_errors", row)
        return row

    def query(self, table: str, filters: Optional[Dict[str, Any]] = None, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        store = self.store
        if store is None:
            return []
        return store.query(table, filters=filters, limit=limit, offset=offset)

    def flush(self) -> None:
        if self._store is not None:
            self._store.flush()
