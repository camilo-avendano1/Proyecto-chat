"""
Repositorio persistente de consumo de tokens y llamadas a modelos.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from src.db.models import UsageRecordORM


def _parse_iso_datetime(value: str, end_of_day: bool = False) -> datetime:
    """Parse a YYYY-MM-DD date or ISO-8601 datetime string into a UTC-aware datetime."""
    raw = value.strip()
    if len(raw) == 10:
        dt = datetime.strptime(raw, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        if end_of_day:
            dt = dt.replace(hour=23, minute=59, second=59, microsecond=999999)
        return dt

    normalized = f"{raw[:-1]}+00:00" if raw.endswith("Z") else raw
    dt = datetime.fromisoformat(normalized)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _parse_date_bounds(
    days: Optional[int] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> Tuple[Optional[datetime], Optional[datetime]]:
    """Resolve optional days/date_from/date_to filters into UTC datetime bounds."""
    start_dt: Optional[datetime] = None
    end_dt: Optional[datetime] = None

    if date_from is not None and date_from.strip():
        start_dt = _parse_iso_datetime(date_from, end_of_day=False)
    elif days is not None:
        start_dt = datetime.now(timezone.utc) - timedelta(days=days)

    if date_to is not None and date_to.strip():
        end_dt = _parse_iso_datetime(date_to, end_of_day=True)

    return start_dt, end_dt


def _apply_common_filters(
    stmt: Any,
    org_id: Optional[str] = None,
    site_id: Optional[str] = None,
    usuario: Optional[str] = None,
    start_dt: Optional[datetime] = None,
    end_dt: Optional[datetime] = None,
) -> Any:
    """Apply common organization, site, user, and UTC date-range filters to a query."""
    if org_id:
        stmt = stmt.where(UsageRecordORM.org_id == org_id)
    if site_id:
        stmt = stmt.where(UsageRecordORM.site_id == site_id)
    if usuario:
        stmt = stmt.where(UsageRecordORM.usuario == usuario)
    if start_dt is not None:
        stmt = stmt.where(UsageRecordORM.created_at >= start_dt)
    if end_dt is not None:
        stmt = stmt.where(UsageRecordORM.created_at <= end_dt)
    return stmt


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
        org_id: Optional[str] = None,
        site_id: Optional[str] = None,
        usuario: Optional[str] = None,
        days: Optional[int] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> Dict[str, Any]:
        start_dt, end_dt = _parse_date_bounds(days=days, date_from=date_from, date_to=date_to)
        stmt = select(
            func.count(UsageRecordORM.id).label("total_records"),
            func.coalesce(func.sum(UsageRecordORM.tokens_input), 0).label("tokens_input"),
            func.coalesce(func.sum(UsageRecordORM.tokens_output), 0).label("tokens_output"),
            func.coalesce(func.sum(UsageRecordORM.tokens_total), 0).label("tokens_total"),
            func.coalesce(func.sum(UsageRecordORM.costo_usd), 0.0).label("costo_usd"),
            func.coalesce(func.sum(case((UsageRecordORM.is_llm_call.is_(False), 1), else_=0)), 0).label("saved_fast_path"),
        )
        stmt = _apply_common_filters(
            stmt,
            org_id=org_id,
            site_id=site_id,
            usuario=usuario,
            start_dt=start_dt,
            end_dt=end_dt,
        )

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
        org_id: Optional[str] = None,
        site_id: Optional[str] = None,
        days: Optional[int] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        start_dt, end_dt = _parse_date_bounds(days=days, date_from=date_from, date_to=date_to)
        stmt = select(
            UsageRecordORM.usuario,
            UsageRecordORM.site_id,
            UsageRecordORM.org_id,
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
            UsageRecordORM.site_id,
            UsageRecordORM.org_id,
            UsageRecordORM.rol,
        )
        stmt = _apply_common_filters(
            stmt,
            org_id=org_id,
            site_id=site_id,
            start_dt=start_dt,
            end_dt=end_dt,
        )

        rows = self.db.execute(stmt).all()
        return [
            {
                "usuario": r.usuario,
                "site_id": r.site_id,
                "org_id": r.org_id,
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

    def get_by_site(
        self,
        org_id: Optional[str] = None,
        site_id: Optional[str] = None,
        days: Optional[int] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        start_dt, end_dt = _parse_date_bounds(days=days, date_from=date_from, date_to=date_to)
        stmt = select(
            UsageRecordORM.site_id,
            UsageRecordORM.org_id,
            func.count(UsageRecordORM.id).label("total_requests"),
            func.sum(case((UsageRecordORM.is_llm_call.is_(True), 1), else_=0)).label("llm_requests"),
            func.sum(case((UsageRecordORM.is_llm_call.is_(False), 1), else_=0)).label("fast_path_requests"),
            func.coalesce(func.sum(UsageRecordORM.tokens_input), 0).label("tokens_input"),
            func.coalesce(func.sum(UsageRecordORM.tokens_output), 0).label("tokens_output"),
            func.coalesce(func.sum(UsageRecordORM.tokens_total), 0).label("tokens_total"),
            func.coalesce(func.sum(UsageRecordORM.costo_usd), 0.0).label("costo_usd"),
            func.avg(UsageRecordORM.latencia_ms).label("avg_latencia"),
        ).group_by(
            UsageRecordORM.site_id,
            UsageRecordORM.org_id,
        )
        stmt = _apply_common_filters(
            stmt,
            org_id=org_id,
            site_id=site_id,
            start_dt=start_dt,
            end_dt=end_dt,
        )

        rows = self.db.execute(stmt).all()
        return [
            {
                "site_id": r.site_id,
                "org_id": r.org_id,
                "total_requests": int(r.total_requests),
                "llm_requests": int(r.llm_requests),
                "fast_path_requests": int(r.fast_path_requests),
                "total_tokens_input": int(r.tokens_input),
                "total_tokens_output": int(r.tokens_output),
                "total_tokens": int(r.tokens_total),
                "total_cost_usd": round(float(r.costo_usd), 6),
                "avg_latencia_ms": int(round(float(r.avg_latencia or 0))),
            }
            for r in rows
        ]

    def get_by_role(
        self,
        org_id: Optional[str] = None,
        site_id: Optional[str] = None,
        days: Optional[int] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        start_dt, end_dt = _parse_date_bounds(days=days, date_from=date_from, date_to=date_to)
        stmt = select(
            UsageRecordORM.rol,
            UsageRecordORM.org_id,
            func.count(UsageRecordORM.id).label("total_requests"),
            func.coalesce(func.sum(UsageRecordORM.tokens_input), 0).label("tokens_input"),
            func.coalesce(func.sum(UsageRecordORM.tokens_output), 0).label("tokens_output"),
            func.coalesce(func.sum(UsageRecordORM.tokens_total), 0).label("tokens_total"),
            func.coalesce(func.sum(UsageRecordORM.costo_usd), 0.0).label("costo_usd"),
        ).group_by(
            UsageRecordORM.rol,
            UsageRecordORM.org_id,
        )
        stmt = _apply_common_filters(
            stmt,
            org_id=org_id,
            site_id=site_id,
            start_dt=start_dt,
            end_dt=end_dt,
        )

        rows = self.db.execute(stmt).all()
        return [
            {
                "rol": r.rol or "SIN_ROL",
                "org_id": r.org_id,
                "total_requests": int(r.total_requests),
                "total_tokens_input": int(r.tokens_input),
                "total_tokens_output": int(r.tokens_output),
                "total_tokens": int(r.tokens_total),
                "total_cost_usd": round(float(r.costo_usd), 6),
            }
            for r in rows
        ]

    def get_by_model(
        self,
        org_id: Optional[str] = None,
        site_id: Optional[str] = None,
        days: Optional[int] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        start_dt, end_dt = _parse_date_bounds(days=days, date_from=date_from, date_to=date_to)
        stmt = select(
            UsageRecordORM.model,
            UsageRecordORM.provider,
            func.count(UsageRecordORM.id).label("total_requests"),
            func.coalesce(func.sum(UsageRecordORM.tokens_input), 0).label("tokens_input"),
            func.coalesce(func.sum(UsageRecordORM.tokens_output), 0).label("tokens_output"),
            func.coalesce(func.sum(UsageRecordORM.tokens_total), 0).label("tokens_total"),
            func.coalesce(func.sum(UsageRecordORM.costo_usd), 0.0).label("costo_usd"),
            func.avg(UsageRecordORM.latencia_ms).label("avg_latencia"),
        ).group_by(
            UsageRecordORM.model,
            UsageRecordORM.provider,
        )
        stmt = _apply_common_filters(
            stmt,
            org_id=org_id,
            site_id=site_id,
            start_dt=start_dt,
            end_dt=end_dt,
        )

        rows = self.db.execute(stmt).all()
        return [
            {
                "model": r.model or "N/A",
                "provider": r.provider or "N/A",
                "total_requests": int(r.total_requests),
                "total_tokens_input": int(r.tokens_input),
                "total_tokens_output": int(r.tokens_output),
                "total_tokens": int(r.tokens_total),
                "total_cost_usd": round(float(r.costo_usd), 6),
                "avg_latencia_ms": int(round(float(r.avg_latencia or 0))),
            }
            for r in rows
        ]

    def get_timeseries(
        self,
        org_id: Optional[str] = None,
        site_id: Optional[str] = None,
        days: Optional[int] = 30,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        start_dt, end_dt = _parse_date_bounds(days=days, date_from=date_from, date_to=date_to)
        day_col = func.date(UsageRecordORM.created_at).label("day")
        stmt = select(
            day_col,
            func.count(UsageRecordORM.id).label("total_requests"),
            func.coalesce(func.sum(case((UsageRecordORM.is_llm_call.is_(True), 1), else_=0)), 0).label("llm_requests"),
            func.coalesce(func.sum(case((UsageRecordORM.is_llm_call.is_(False), 1), else_=0)), 0).label("fast_path_requests"),
            func.coalesce(func.sum(UsageRecordORM.tokens_input), 0).label("tokens_input"),
            func.coalesce(func.sum(UsageRecordORM.tokens_output), 0).label("tokens_output"),
            func.coalesce(func.sum(UsageRecordORM.tokens_total), 0).label("tokens_total"),
            func.coalesce(func.sum(UsageRecordORM.costo_usd), 0.0).label("costo_usd"),
        ).group_by(day_col).order_by(day_col.asc())

        stmt = _apply_common_filters(
            stmt,
            org_id=org_id,
            site_id=site_id,
            start_dt=start_dt,
            end_dt=end_dt,
        )

        rows = self.db.execute(stmt).all()
        return [
            {
                "date": str(r.day),
                "total_requests": int(r.total_requests),
                "llm_requests": int(r.llm_requests),
                "fast_path_requests": int(r.fast_path_requests),
                "tokens_input": int(r.tokens_input),
                "tokens_output": int(r.tokens_output),
                "tokens_total": int(r.tokens_total),
                "costo_usd": round(float(r.costo_usd), 6),
            }
            for r in rows
            if r.day is not None
        ]

    def get_recent_records(
        self,
        org_id: Optional[str] = None,
        site_id: Optional[str] = None,
        usuario: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
        days: Optional[int] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        start_dt, end_dt = _parse_date_bounds(days=days, date_from=date_from, date_to=date_to)
        stmt = select(UsageRecordORM)
        stmt = _apply_common_filters(
            stmt,
            org_id=org_id,
            site_id=site_id,
            usuario=usuario,
            start_dt=start_dt,
            end_dt=end_dt,
        )
        stmt = stmt.order_by(UsageRecordORM.id.desc()).limit(limit).offset(offset)

        rows = self.db.scalars(stmt).all()
        return [
            {
                "ledger_id": r.ledger_id,
                "request_id": r.request_id,
                "org_id": r.org_id,
                "site_id": r.site_id,
                "usuario": r.usuario,
                "rol": r.rol,
                "site_code": r.site_code,
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
