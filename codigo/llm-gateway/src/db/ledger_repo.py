"""
Repositorio persistente de consumo de tokens y llamadas a modelos.
"""

from typing import Any, Dict, List, Optional
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from src.db.models import UsageRecordORM


class LedgerRepository:
    def __init__(self, db: Session):
        self.db = db

    def record_usage(self, **kwargs: Any) -> UsageRecordORM:
        if "tokens_total" not in kwargs:
            tokens_in = kwargs.get("tokens_input", 0)
            tokens_out = kwargs.get("tokens_output", 0)
            kwargs["tokens_total"] = tokens_in + tokens_out

        record = UsageRecordORM(**kwargs)
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def get_summary(
        self,
        client_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        usuario: Optional[str] = None,
    ) -> Dict[str, Any]:
        stmt = select(
            func.count(UsageRecordORM.id).label("total_records"),
            func.coalesce(func.sum(UsageRecordORM.tokens_input), 0).label("tokens_input"),
            func.coalesce(func.sum(UsageRecordORM.tokens_output), 0).label("tokens_output"),
            func.coalesce(func.sum(UsageRecordORM.tokens_total), 0).label("tokens_total"),
            func.coalesce(func.sum(UsageRecordORM.costo_usd), 0.0).label("costo_usd"),
            func.coalesce(func.sum(case((UsageRecordORM.is_llm_call.is_(False), 1), else_=0)), 0).label("saved_fast_path"),
        )
        if client_id:
            stmt = stmt.where(UsageRecordORM.client_id == client_id)
        if tenant_id:
            stmt = stmt.where(UsageRecordORM.tenant_id == tenant_id)
        if usuario:
            stmt = stmt.where(UsageRecordORM.usuario == usuario)

        row = self.db.execute(stmt).one()
        return {
            "total_records": int(row.total_records),
            "total_tokens_input": int(row.tokens_input),
            "total_tokens_output": int(row.tokens_output),
            "total_tokens": int(row.tokens_total),
            "total_cost_usd": round(float(row.costo_usd), 6),
            "saved_fast_path_calls": int(row.saved_fast_path),
        }

    def get_by_user(
        self,
        client_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        stmt = select(
            UsageRecordORM.usuario,
            UsageRecordORM.tenant_id,
            UsageRecordORM.client_id,
            UsageRecordORM.rol,
            func.count(UsageRecordORM.id).label("total_requests"),
            func.sum(case((UsageRecordORM.is_llm_call.is_(True), 1), else_=0)).label("llm_requests"),
            func.sum(case((UsageRecordORM.is_llm_call.is_(False), 1), else_=0)).label("fast_path_requests"),
            func.coalesce(func.sum(UsageRecordORM.tokens_input), 0).label("tokens_input"),
            func.coalesce(func.sum(UsageRecordORM.tokens_output), 0).label("tokens_output"),
            func.coalesce(func.sum(UsageRecordORM.tokens_total), 0).label("tokens_total"),
            func.coalesce(func.sum(UsageRecordORM.costo_usd), 0.0).label("costo_usd"),
        ).group_by(
            UsageRecordORM.usuario,
            UsageRecordORM.tenant_id,
            UsageRecordORM.client_id,
            UsageRecordORM.rol,
        )

        if client_id:
            stmt = stmt.where(UsageRecordORM.client_id == client_id)
        if tenant_id:
            stmt = stmt.where(UsageRecordORM.tenant_id == tenant_id)

        rows = self.db.execute(stmt).all()
        return [
            {
                "usuario": r.usuario,
                "tenant_id": r.tenant_id,
                "client_id": r.client_id,
                "rol": r.rol or "SIN_ROL",
                "total_requests": int(r.total_requests),
                "llm_requests": int(r.llm_requests),
                "fast_path_requests": int(r.fast_path_requests),
                "total_tokens_input": int(r.tokens_input),
                "total_tokens_output": int(r.tokens_output),
                "total_tokens": int(r.tokens_total),
                "total_cost_usd": round(float(r.costo_usd), 6),
            }
            for r in rows
        ]

    def get_by_tenant(
        self,
        client_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        stmt = select(
            UsageRecordORM.tenant_id,
            UsageRecordORM.client_id,
            func.count(UsageRecordORM.id).label("total_requests"),
            func.sum(case((UsageRecordORM.is_llm_call.is_(True), 1), else_=0)).label("llm_requests"),
            func.sum(case((UsageRecordORM.is_llm_call.is_(False), 1), else_=0)).label("fast_path_requests"),
            func.coalesce(func.sum(UsageRecordORM.tokens_input), 0).label("tokens_input"),
            func.coalesce(func.sum(UsageRecordORM.tokens_output), 0).label("tokens_output"),
            func.coalesce(func.sum(UsageRecordORM.tokens_total), 0).label("tokens_total"),
            func.coalesce(func.sum(UsageRecordORM.costo_usd), 0.0).label("costo_usd"),
        ).group_by(
            UsageRecordORM.tenant_id,
            UsageRecordORM.client_id,
        )

        if client_id:
            stmt = stmt.where(UsageRecordORM.client_id == client_id)

        rows = self.db.execute(stmt).all()
        return [
            {
                "tenant_id": r.tenant_id,
                "client_id": r.client_id,
                "total_requests": int(r.total_requests),
                "llm_requests": int(r.llm_requests),
                "fast_path_requests": int(r.fast_path_requests),
                "total_tokens_input": int(r.tokens_input),
                "total_tokens_output": int(r.tokens_output),
                "total_tokens": int(r.tokens_total),
                "total_cost_usd": round(float(r.costo_usd), 6),
            }
            for r in rows
        ]

    def get_by_role(
        self,
        client_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        stmt = select(
            UsageRecordORM.rol,
            UsageRecordORM.client_id,
            func.count(UsageRecordORM.id).label("total_requests"),
            func.coalesce(func.sum(UsageRecordORM.tokens_total), 0).label("tokens_total"),
            func.coalesce(func.sum(UsageRecordORM.costo_usd), 0.0).label("costo_usd"),
        ).group_by(
            UsageRecordORM.rol,
            UsageRecordORM.client_id,
        )

        if client_id:
            stmt = stmt.where(UsageRecordORM.client_id == client_id)

        rows = self.db.execute(stmt).all()
        return [
            {
                "rol": r.rol or "SIN_ROL",
                "client_id": r.client_id,
                "total_requests": int(r.total_requests),
                "total_tokens": int(r.tokens_total),
                "total_cost_usd": round(float(r.costo_usd), 6),
            }
            for r in rows
        ]

    def get_by_model(
        self,
        client_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        stmt = select(
            UsageRecordORM.model,
            UsageRecordORM.provider,
            func.count(UsageRecordORM.id).label("total_requests"),
            func.coalesce(func.sum(UsageRecordORM.tokens_total), 0).label("tokens_total"),
            func.coalesce(func.sum(UsageRecordORM.costo_usd), 0.0).label("costo_usd"),
        ).group_by(
            UsageRecordORM.model,
            UsageRecordORM.provider,
        )

        if client_id:
            stmt = stmt.where(UsageRecordORM.client_id == client_id)

        rows = self.db.execute(stmt).all()
        return [
            {
                "model": r.model or "N/A",
                "provider": r.provider or "N/A",
                "total_requests": int(r.total_requests),
                "total_tokens": int(r.tokens_total),
                "total_cost_usd": round(float(r.costo_usd), 6),
            }
            for r in rows
        ]

    def get_recent_records(
        self,
        client_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        usuario: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        stmt = select(UsageRecordORM).order_by(UsageRecordORM.id.desc()).limit(limit).offset(offset)
        if client_id:
            stmt = stmt.where(UsageRecordORM.client_id == client_id)
        if tenant_id:
            stmt = stmt.where(UsageRecordORM.tenant_id == tenant_id)
        if usuario:
            stmt = stmt.where(UsageRecordORM.usuario == usuario)

        rows = self.db.scalars(stmt).all()
        return [
            {
                "ledger_id": r.ledger_id,
                "request_id": r.request_id,
                "client_id": r.client_id,
                "tenant_id": r.tenant_id,
                "usuario": r.usuario,
                "rol": r.rol,
                "ips_code": r.ips_code,
                "operacion": r.operacion,
                "tokens_input": r.tokens_input,
                "tokens_output": r.tokens_output,
                "tokens_total": r.tokens_total,
                "costo_usd": r.costo_usd,
                "latencia_ms": r.latencia_ms,
                "model": r.model,
                "provider": r.provider,
                "status": r.status,
                "is_llm_call": r.is_llm_call,
                "token_source": r.token_source,
                "query_preview": r.query_preview,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]
