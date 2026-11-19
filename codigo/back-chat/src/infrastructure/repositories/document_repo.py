"""
SQLAlchemy 2.0 Repository for Knowledge Documents and Chunk Indexing.
Supports strict multi-organization / multi-site isolation and hierarchical RAG fallback search.
"""

from __future__ import annotations

import os

os.environ["DISABLE_SQLALCHEMY_CEXT"] = "1"

from datetime import datetime, timezone
from pathlib import Path
import re
import threading
from typing import Any, Dict, List, Optional
import unicodedata
import uuid

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    and_,
    create_engine,
    event,
    func,
    or_,
    select,
    text,
)
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

from src.config import settings

_SPANISH_STOPWORDS = frozenset({
    "de", "la", "el", "en", "y", "que", "como", "se", "un", "una",
    "para", "por", "con", "los", "las", "del", "al", "es", "su", "sus",
    "lo", "le", "les", "unos", "unas", "sobre", "sin", "son", "cual",
    "cuales", "este", "esta", "estos", "estas", "ese", "esa", "me", "te",
    "nos", "si", "no", "mas", "pero", "donde", "cuando", "quien", "hay",
})

_SCOPE_BOOST: Dict[str, float] = {
    "SITE": 0.35,
    "ORGANIZATION": 0.15,
    "GLOBAL": 0.0,
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _format_dt(value: Optional[datetime]) -> Optional[str]:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def _normalize_text(raw_text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", raw_text or "")
    stripped = "".join(ch for ch in nfkd if not unicodedata.combining(ch))
    return stripped.lower()


def _tokenize_meaningful(raw_text: str) -> List[str]:
    normalized = _normalize_text(raw_text)
    raw_tokens = re.findall(r"[a-z0-9_]{2,}", normalized)
    filtered = [tok for tok in raw_tokens if tok not in _SPANISH_STOPWORDS]
    return filtered or raw_tokens


class Base(DeclarativeBase):
    """Declarative base for Knowledge Documents ORM models."""


class KnowledgeDocumentORM(Base):
    """Stores metadata and vector sync state for uploaded knowledge base documents."""

    __tablename__ = "knowledge_documents"

    doc_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    org_id: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    site_id: Mapped[Optional[str]] = mapped_column(String(100), index=True, nullable=True)
    scope: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_type: Mapped[str] = mapped_column(String(20), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    chunk_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="READY")
    vector_sync_status: Mapped[str] = mapped_column(String(30), nullable=False, default="LOCAL_INDEXED")
    vector_sync_detail: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tags: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=list)
    uploaded_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)

    chunks: Mapped[List["KnowledgeChunkORM"]] = relationship(
        "KnowledgeChunkORM",
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class KnowledgeChunkORM(Base):
    """Stores text chunks extracted from KnowledgeDocumentORM for RAG retrieval."""

    __tablename__ = "knowledge_chunks"

    chunk_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    doc_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("knowledge_documents.doc_id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    org_id: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    site_id: Mapped[Optional[str]] = mapped_column(String(100), index=True, nullable=True)
    scope: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    section: Mapped[str] = mapped_column(String(255), nullable=False, default="General")
    content: Mapped[str] = mapped_column(Text, nullable=False)
    char_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)

    document: Mapped["KnowledgeDocumentORM"] = relationship(
        "KnowledgeDocumentORM",
        back_populates="chunks",
    )


def _create_knowledge_engine(database_url: str) -> Engine:
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
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


def _migrate_legacy_knowledge_sqlite(engine: Engine) -> None:
    """
    Migrates legacy SQLite columns and scopes:
    - client_id -> org_id
    - tenant_id -> site_id
    - scope 'TENANT' -> 'SITE', 'ACCOUNT' -> 'ORGANIZATION'
    - ensures indexes on org_id and site_id
    """
    if engine.dialect.name != "sqlite":
        return

    column_renames = (
        ("client_id", "org_id"),
        ("tenant_id", "site_id"),
    )

    with engine.begin() as conn:
        for table_name in ("knowledge_documents", "knowledge_chunks"):
            exists = conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table' AND name=:t"),
                {"t": table_name},
            ).scalar()
            if not exists:
                continue

            cols = {
                row[1]
                for row in conn.execute(text(f'PRAGMA table_info("{table_name}")')).fetchall()
            }
            for old_col, new_col in column_renames:
                if old_col in cols and new_col not in cols:
                    conn.execute(
                        text(f'ALTER TABLE "{table_name}" RENAME COLUMN "{old_col}" TO "{new_col}"')
                    )
                    cols.remove(old_col)
                    cols.add(new_col)

            if "scope" in cols:
                conn.execute(text(f"UPDATE \"{table_name}\" SET scope='SITE' WHERE scope='TENANT'"))
                conn.execute(text(f"UPDATE \"{table_name}\" SET scope='ORGANIZATION' WHERE scope='ACCOUNT'"))

            if "org_id" in cols:
                conn.execute(
                    text(f'CREATE INDEX IF NOT EXISTS "ix_{table_name}_org_id" ON "{table_name}" ("org_id")')
                )
            if "site_id" in cols:
                conn.execute(
                    text(f'CREATE INDEX IF NOT EXISTS "ix_{table_name}_site_id" ON "{table_name}" ("site_id")')
                )


class KnowledgeDocumentRepository:
    """Repository managing persistent knowledge documents and chunks in SQLite/SQL."""

    def __init__(self, database_url: Optional[str] = None):
        self.database_url = database_url or os.environ.get("KNOWLEDGE_DATABASE_URL") or settings.KNOWLEDGE_DATABASE_URL
        self.engine = _create_knowledge_engine(self.database_url)
        _migrate_legacy_knowledge_sqlite(self.engine)
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine, expire_on_commit=False)

    def close(self) -> None:
        self.engine.dispose()

    @staticmethod
    def _doc_to_dict(doc: KnowledgeDocumentORM) -> Dict[str, Any]:
        return {
            "doc_id": doc.doc_id,
            "org_id": doc.org_id,
            "site_id": doc.site_id,
            "scope": doc.scope,
            "title": doc.title,
            "filename": doc.filename,
            "file_type": doc.file_type,
            "file_size_bytes": doc.file_size_bytes,
            "content_hash": doc.content_hash,
            "chunk_count": doc.chunk_count,
            "status": doc.status,
            "vector_sync_status": doc.vector_sync_status,
            "vector_sync_detail": doc.vector_sync_detail,
            "tags": list(doc.tags or []),
            "uploaded_by": doc.uploaded_by,
            "created_at": _format_dt(doc.created_at),
        }

    @staticmethod
    def _chunk_to_dict(chunk: KnowledgeChunkORM) -> Dict[str, Any]:
        return {
            "chunk_id": chunk.chunk_id,
            "doc_id": chunk.doc_id,
            "org_id": chunk.org_id,
            "site_id": chunk.site_id,
            "scope": chunk.scope,
            "chunk_index": chunk.chunk_index,
            "section": chunk.section,
            "content": chunk.content,
            "char_count": chunk.char_count,
            "created_at": _format_dt(chunk.created_at),
        }

    def find_by_hash(
        self,
        org_id: str,
        site_id: Optional[str],
        scope: str,
        content_hash: str,
    ) -> Optional[Dict[str, Any]]:
        norm_site = site_id or None
        with self.SessionLocal() as session:
            site_cond = (
                KnowledgeDocumentORM.site_id.is_(None)
                if norm_site is None
                else KnowledgeDocumentORM.site_id == norm_site
            )
            stmt = select(KnowledgeDocumentORM).where(
                KnowledgeDocumentORM.org_id == org_id,
                site_cond,
                KnowledgeDocumentORM.scope == scope,
                KnowledgeDocumentORM.content_hash == content_hash,
            )
            doc = session.scalars(stmt).first()
            return self._doc_to_dict(doc) if doc is not None else None

    def create_document_with_chunks(
        self,
        doc_data: Dict[str, Any],
        chunks_data: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        doc_id = doc_data.get("doc_id") or str(uuid.uuid4())
        now = doc_data.get("created_at") or _utcnow()
        org_id = doc_data["org_id"]
        site_id = doc_data.get("site_id") or None
        scope = doc_data["scope"]

        with self.SessionLocal() as session:
            doc_orm = KnowledgeDocumentORM(
                doc_id=doc_id,
                org_id=org_id,
                site_id=site_id,
                scope=scope,
                title=doc_data["title"],
                filename=doc_data["filename"],
                file_type=doc_data["file_type"],
                file_size_bytes=int(doc_data["file_size_bytes"]),
                content_hash=doc_data["content_hash"],
                chunk_count=int(doc_data.get("chunk_count", len(chunks_data))),
                status=doc_data.get("status", "READY"),
                vector_sync_status=doc_data.get("vector_sync_status", "LOCAL_INDEXED"),
                vector_sync_detail=doc_data.get("vector_sync_detail"),
                tags=list(doc_data.get("tags") or []),
                uploaded_by=doc_data.get("uploaded_by"),
                created_at=now,
            )
            session.add(doc_orm)
            session.flush()

            chunk_orms = []
            for idx, chunk in enumerate(chunks_data):
                content = chunk["content"]
                chunk_orms.append(
                    KnowledgeChunkORM(
                        chunk_id=chunk.get("chunk_id") or str(uuid.uuid4()),
                        doc_id=doc_id,
                        org_id=org_id,
                        site_id=site_id,
                        scope=scope,
                        chunk_index=int(chunk.get("chunk_index", idx)),
                        section=(chunk.get("section") or "General")[:255],
                        content=content,
                        char_count=int(chunk.get("char_count", len(content))),
                        created_at=chunk.get("created_at") or now,
                    )
                )
            if chunk_orms:
                session.add_all(chunk_orms)

            session.commit()
            session.refresh(doc_orm)
            return self._doc_to_dict(doc_orm)

    def update_sync_status(
        self,
        doc_id: str,
        vector_sync_status: str,
        vector_sync_detail: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        with self.SessionLocal() as session:
            doc_orm = session.get(KnowledgeDocumentORM, doc_id)
            if doc_orm is None:
                return None
            doc_orm.vector_sync_status = vector_sync_status
            doc_orm.vector_sync_detail = vector_sync_detail
            session.commit()
            session.refresh(doc_orm)
            return self._doc_to_dict(doc_orm)

    def list_documents(
        self,
        org_id: Optional[str] = None,
        site_id: Optional[str] = None,
        scope: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Dict[str, Any]:
        conditions = []
        if org_id:
            conditions.append(KnowledgeDocumentORM.org_id == org_id)
        if site_id:
            conditions.append(KnowledgeDocumentORM.site_id == site_id)
        if scope:
            conditions.append(KnowledgeDocumentORM.scope == scope.strip().upper())
        if search and search.strip():
            pattern = f"%{search.strip()}%"
            conditions.append(
                or_(
                    KnowledgeDocumentORM.title.ilike(pattern),
                    KnowledgeDocumentORM.filename.ilike(pattern),
                )
            )

        with self.SessionLocal() as session:
            total_stmt = select(func.count()).select_from(KnowledgeDocumentORM)
            if conditions:
                total_stmt = total_stmt.where(*conditions)
            total = int(session.execute(total_stmt).scalar() or 0)

            rows_stmt = select(KnowledgeDocumentORM)
            if conditions:
                rows_stmt = rows_stmt.where(*conditions)
            rows_stmt = (
                rows_stmt.order_by(KnowledgeDocumentORM.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
            docs = session.scalars(rows_stmt).all()

            counts_stmt = (
                select(KnowledgeDocumentORM.site_id, func.count())
                .where(KnowledgeDocumentORM.site_id.is_not(None))
            )
            if conditions:
                counts_stmt = counts_stmt.where(*conditions)
            counts_stmt = counts_stmt.group_by(KnowledgeDocumentORM.site_id)
            counts_by_site = {
                str(s_id): int(cnt)
                for s_id, cnt in session.execute(counts_stmt).all()
                if s_id is not None
            }

            return {
                "total": total,
                "records": [self._doc_to_dict(d) for d in docs],
                "counts_by_site": counts_by_site,
            }

    def get_document(self, doc_id: str) -> Optional[Dict[str, Any]]:
        with self.SessionLocal() as session:
            doc_orm = session.get(KnowledgeDocumentORM, doc_id)
            return self._doc_to_dict(doc_orm) if doc_orm is not None else None

    def get_chunks(self, doc_id: str) -> List[Dict[str, Any]]:
        with self.SessionLocal() as session:
            stmt = (
                select(KnowledgeChunkORM)
                .where(KnowledgeChunkORM.doc_id == doc_id)
                .order_by(KnowledgeChunkORM.chunk_index.asc())
            )
            chunks = session.scalars(stmt).all()
            return [self._chunk_to_dict(c) for c in chunks]

    def delete_document(self, doc_id: str) -> bool:
        with self.SessionLocal() as session:
            doc_orm = session.get(KnowledgeDocumentORM, doc_id)
            if doc_orm is None:
                return False
            session.delete(doc_orm)
            session.commit()
            return True

    def search_chunks(
        self,
        query: str,
        org_id: Optional[str],
        site_id: Optional[str] = None,
        top_k: int = 4,
    ) -> List[Dict[str, Any]]:
        norm_query = _normalize_text(query).strip()
        if not norm_query:
            return []

        query_tokens = _tokenize_meaningful(query)
        query_token_set = set(query_tokens)
        if not query_token_set:
            return []

        eff_org = (org_id or "").strip() or None
        eff_site = (site_id or "").strip() or None

        scope_filters = []
        if eff_org:
            if eff_site:
                scope_filters.append(
                    and_(
                        KnowledgeChunkORM.scope == "SITE",
                        KnowledgeChunkORM.org_id == eff_org,
                        KnowledgeChunkORM.site_id == eff_site,
                    )
                )
            scope_filters.append(
                and_(
                    KnowledgeChunkORM.scope == "ORGANIZATION",
                    KnowledgeChunkORM.org_id == eff_org,
                )
            )
            scope_filters.append(
                and_(
                    KnowledgeChunkORM.scope == "GLOBAL",
                    KnowledgeChunkORM.org_id.in_([eff_org, "global"]),
                )
            )
        else:
            scope_filters.append(
                and_(
                    KnowledgeChunkORM.scope == "GLOBAL",
                    KnowledgeChunkORM.org_id == "global",
                )
            )

        with self.SessionLocal() as session:
            stmt = (
                select(KnowledgeChunkORM, KnowledgeDocumentORM.title)
                .join(
                    KnowledgeDocumentORM,
                    KnowledgeChunkORM.doc_id == KnowledgeDocumentORM.doc_id,
                )
                .where(
                    KnowledgeDocumentORM.status == "READY",
                    or_(*scope_filters),
                )
            )
            candidates = session.execute(stmt).all()

        scored: List[tuple[float, int, Dict[str, Any]]] = []
        for chunk, doc_title in candidates:
            norm_title = _normalize_text(doc_title)
            norm_section = _normalize_text(chunk.section)
            norm_content = _normalize_text(chunk.content)
            combined_norm = f"{norm_title} {norm_section} {norm_content}"

            chunk_tokens = set(_tokenize_meaningful(combined_norm))
            matched_tokens = query_token_set & chunk_tokens
            exact_match = len(norm_query) >= 4 and norm_query in combined_norm

            if not matched_tokens and not exact_match:
                continue

            overlap_ratio = len(matched_tokens) / max(1, len(query_token_set))
            title_section_tokens = set(_tokenize_meaningful(f"{norm_title} {norm_section}"))
            title_ratio = len(query_token_set & title_section_tokens) / max(1, len(query_token_set))
            boost = _SCOPE_BOOST.get(chunk.scope, 0.0)

            raw_score = (0.60 * overlap_ratio) + (0.20 * title_ratio) + (0.25 if exact_match else 0.0) + boost
            scored.append(
                (
                    raw_score,
                    len(matched_tokens),
                    {
                        "title": doc_title,
                        "scope": chunk.scope,
                        "section": chunk.section,
                        "content": chunk.content,
                        "score": round(min(1.0, raw_score), 4),
                    },
                )
            )

        scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
        return [item[2] for item in scored[:top_k]]


_repo_lock = threading.Lock()
_repo_instance: Optional[KnowledgeDocumentRepository] = None


def get_document_repository() -> KnowledgeDocumentRepository:
    """Returns the thread-safe singleton KnowledgeDocumentRepository instance."""
    global _repo_instance
    if _repo_instance is None:
        with _repo_lock:
            if _repo_instance is None:
                _repo_instance = KnowledgeDocumentRepository()
    return _repo_instance


def reset_document_repository(database_url: Optional[str] = None) -> KnowledgeDocumentRepository:
    """Resets and replaces the singleton repository (primarily for isolated testing)."""
    global _repo_instance
    with _repo_lock:
        if _repo_instance is not None:
            _repo_instance.close()
        _repo_instance = KnowledgeDocumentRepository(database_url=database_url)
        return _repo_instance
