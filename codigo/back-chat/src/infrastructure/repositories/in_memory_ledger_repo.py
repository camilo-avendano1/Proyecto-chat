"""
In-memory implementation of LedgerRepositoryProtocol.
Logs usage records and aggregates tokens, latencies, and estimated costs per user, site, and organization.
"""

from typing import Any, Dict, List, Optional
from src.domain.entities import UsageLedgerRecord
from src.operations.interfaces import LedgerRepositoryProtocol


class InMemoryLedgerRepository(LedgerRepositoryProtocol):
    """Repository storing AI token usage, security diagnostics, and request tracking."""

    def __init__(self):
        self._records: List[UsageLedgerRecord] = []

    async def record_usage(self, record: UsageLedgerRecord) -> None:
        self._records.append(record)

    async def get_usage_summary(
        self,
        site_id: Optional[str] = None,
        org_id: Optional[str] = None,
        usuario: Optional[str] = None,
    ) -> Dict[str, Any]:
        filtered = [
            r for r in self._records
            if (site_id is None or r.site_id == site_id)
            and (org_id is None or r.org_id == org_id)
            and (usuario is None or r.usuario == usuario)
        ]
        return {
            "total_records": len(filtered),
            "total_tokens_input": sum(r.tokens_input for r in filtered),
            "total_tokens_output": sum(r.tokens_output for r in filtered),
            "total_tokens": sum(r.tokens_input + r.tokens_output for r in filtered),
            "total_cost_usd": round(sum(r.costo_usd for r in filtered), 6),
            "saved_fast_path_calls": sum(1 for r in filtered if not r.is_llm_call),
        }

    async def get_usage_by_user(
        self,
        site_id: Optional[str] = None,
        org_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Aggregates token consumption and costs grouped by user."""
        users: Dict[str, Dict[str, Any]] = {}
        for r in self._records:
            if site_id and r.site_id != site_id:
                continue
            if org_id and r.org_id != org_id:
                continue
            u = r.usuario or "anonimo"
            if u not in users:
                users[u] = {
                    "usuario": u,
                    "site_id": r.site_id,
                    "org_id": r.org_id,
                    "total_requests": 0,
                    "llm_requests": 0,
                    "fast_path_requests": 0,
                    "total_tokens_input": 0,
                    "total_tokens_output": 0,
                    "total_tokens": 0,
                    "total_cost_usd": 0.0,
                }
            users[u]["total_requests"] += 1
            if r.is_llm_call:
                users[u]["llm_requests"] += 1
            else:
                users[u]["fast_path_requests"] += 1
            users[u]["total_tokens_input"] += r.tokens_input
            users[u]["total_tokens_output"] += r.tokens_output
            users[u]["total_tokens"] += (r.tokens_input + r.tokens_output)
            users[u]["total_cost_usd"] = round(users[u]["total_cost_usd"] + r.costo_usd, 6)

        return list(users.values())

    async def get_usage_by_site(
        self,
        org_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Aggregates token consumption and costs grouped by site."""
        sites: Dict[str, Dict[str, Any]] = {}
        for r in self._records:
            if org_id and r.org_id != org_id:
                continue
            s = r.site_id
            if s not in sites:
                sites[s] = {
                    "site_id": s,
                    "org_id": r.org_id,
                    "total_requests": 0,
                    "llm_requests": 0,
                    "fast_path_requests": 0,
                    "total_tokens_input": 0,
                    "total_tokens_output": 0,
                    "total_tokens": 0,
                    "total_cost_usd": 0.0,
                }
            sites[s]["total_requests"] += 1
            if r.is_llm_call:
                sites[s]["llm_requests"] += 1
            else:
                sites[s]["fast_path_requests"] += 1
            sites[s]["total_tokens_input"] += r.tokens_input
            sites[s]["total_tokens_output"] += r.tokens_output
            sites[s]["total_tokens"] += (r.tokens_input + r.tokens_output)
            sites[s]["total_cost_usd"] = round(sites[s]["total_cost_usd"] + r.costo_usd, 6)

        return list(sites.values())

    async def get_recent_records(
        self,
        limit: int = 50,
        site_id: Optional[str] = None,
        usuario: Optional[str] = None,
    ) -> List[UsageLedgerRecord]:
        filtered = [
            r for r in reversed(self._records)
            if (site_id is None or r.site_id == site_id)
            and (usuario is None or r.usuario == usuario)
        ]
        return filtered[:limit]

    def get_all_records(self) -> List[UsageLedgerRecord]:
        return list(self._records)
