"""
Protocols and interfaces for the Operations layer.
Implements dependency inversion via structural typing (Protocol).
Supports Multi-Organization and Multi-Site routing.
"""

from typing import Any, AsyncGenerator, Dict, List, Optional, Protocol
from src.domain.entities import KnowledgeSource, Organization, Site, UsageLedgerRecord


class SearchServiceProtocol(Protocol):
    """Protocol for communicating with Organization Search APIs (Retrieval Service)."""

    async def search(
        self,
        query: str,
        org_id: Optional[str] = None,
        busqueda_api_url: Optional[str] = None,
        site_id: Optional[str] = None,
        category: Optional[str] = None,
        variable_num: Optional[int] = None,
        error_code: Optional[str] = None,
        extras: Optional[Dict[str, Any]] = None,
        top_k: int = 5,
    ) -> List[KnowledgeSource]:
        """Queries the retrieval engine for relevant normative and manual chunks."""
        ...


class LLMServiceProtocol(Protocol):
    """Protocol for communicating with LLM inference engines (LM Studio, Ollama, OpenAI)."""

    async def generate_response(
        self,
        system_prompt: str,
        user_prompt: str,
        history: Optional[List[Dict[str, str]]] = None,
        **kwargs: Any,
    ) -> str:
        """Generates a complete response synchronously."""
        ...

    async def generate_stream(
        self,
        system_prompt: str,
        user_prompt: str,
        history: Optional[List[Dict[str, str]]] = None,
        **kwargs: Any,
    ) -> AsyncGenerator[str, None]:
        """Streams response tokens as an asynchronous generator."""
        ...


class SessionRepositoryProtocol(Protocol):
    """Protocol for organization, site, and session management."""

    def get_organization_by_id(self, org_id: str) -> Optional[Organization]:
        """Resolves organization by ID."""
        ...

    def get_site_by_key(self, api_key: str) -> Optional[Site]:
        """Resolves site from API Key."""
        ...

    def get_site_by_id(self, site_id: str) -> Optional[Site]:
        """Resolves site by UUID."""
        ...

    def get_site_by_code(self, site_code: str) -> Optional[Site]:
        """Resolves site by site code."""
        ...


class LedgerRepositoryProtocol(Protocol):
    """Protocol for persisting AI token usage and observability metrics."""

    async def record_usage(self, record: UsageLedgerRecord) -> None:
        """Stores a token and latency usage record."""
        ...

    async def get_usage_summary(
        self,
        site_id: Optional[str] = None,
        org_id: Optional[str] = None,
        usuario: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Calculates total usage statistics."""
        ...

    async def get_usage_by_user(
        self,
        site_id: Optional[str] = None,
        org_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Aggregates token consumption and costs grouped by user."""
        ...

    async def get_usage_by_site(
        self,
        org_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Aggregates token consumption and costs grouped by site."""
        ...

    async def get_recent_records(
        self,
        limit: int = 50,
        site_id: Optional[str] = None,
        usuario: Optional[str] = None,
    ) -> List[UsageLedgerRecord]:
        """Returns recent ledger usage records."""
        ...


# ---------------------------------------------------------------------------
# Stubs for Unit Testing and Standalone Mode (Python Clean Architecture)
# ---------------------------------------------------------------------------

class SearchServiceStub:
    """In-memory stub for SearchServiceProtocol."""

    def __init__(self, predefined_sources: Optional[List[KnowledgeSource]] = None):
        self.predefined_sources = predefined_sources or []
        self.call_history: List[Dict[str, Any]] = []

    async def search(
        self,
        query: str,
        org_id: Optional[str] = None,
        busqueda_api_url: Optional[str] = None,
        site_id: Optional[str] = None,
        category: Optional[str] = None,
        variable_num: Optional[int] = None,
        error_code: Optional[str] = None,
        extras: Optional[Dict[str, Any]] = None,
        top_k: int = 5,
    ) -> List[KnowledgeSource]:
        self.call_history.append({
            "query": query,
            "org_id": org_id,
            "busqueda_api_url": busqueda_api_url,
            "site_id": site_id,
            "category": category,
            "variable_num": variable_num,
            "error_code": error_code,
            "extras": extras,
            "top_k": top_k,
        })
        if self.predefined_sources:
            return self.predefined_sources[:top_k]
        return []


class LLMServiceStub:
    """In-memory stub for LLMServiceProtocol."""

    def __init__(self, simulated_response: str = "Respuesta simulada del asistente técnico."):
        self.simulated_response = simulated_response
        self.call_history: List[Dict[str, Any]] = []

    async def generate_response(
        self,
        system_prompt: str,
        user_prompt: str,
        history: Optional[List[Dict[str, str]]] = None,
        **kwargs: Any,
    ) -> str:
        self.call_history.append({
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
            "history": history,
            "kwargs": kwargs,
        })
        return self.simulated_response

    async def generate_stream(
        self,
        system_prompt: str,
        user_prompt: str,
        history: Optional[List[Dict[str, str]]] = None,
        **kwargs: Any,
    ) -> AsyncGenerator[str, None]:
        self.call_history.append({
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
            "history": history,
            "kwargs": kwargs,
        })
        words = self.simulated_response.split(" ")
        for i, word in enumerate(words):
            yield word + (" " if i < len(words) - 1 else "")


class SessionRepositoryStub:
    """In-memory stub for SessionRepositoryProtocol."""

    def __init__(
        self,
        organizations: Optional[Dict[str, Organization]] = None,
        sites: Optional[Dict[str, Site]] = None,
    ):
        self.organizations = organizations or {}
        self.sites = sites or {}

    def get_organization_by_id(self, org_id: str) -> Optional[Organization]:
        return self.organizations.get(org_id)

    def get_site_by_key(self, api_key: str) -> Optional[Site]:
        for site in self.sites.values():
            if site.api_key_hash == api_key:
                return site
        return None

    def get_site_by_id(self, site_id: str) -> Optional[Site]:
        return self.sites.get(site_id)

    def get_site_by_code(self, site_code: str) -> Optional[Site]:
        for site in self.sites.values():
            if site.site_code.lower() == site_code.lower():
                return site
        return None


class LedgerRepositoryStub:
    """In-memory stub for LedgerRepositoryProtocol."""

    def __init__(self):
        self.records: List[UsageLedgerRecord] = []

    async def record_usage(self, record: UsageLedgerRecord) -> None:
        self.records.append(record)

    async def get_usage_summary(
        self,
        site_id: Optional[str] = None,
        org_id: Optional[str] = None,
        usuario: Optional[str] = None,
    ) -> Dict[str, Any]:
        filtered = [
            r for r in self.records
            if (site_id is None or r.site_id == site_id)
            and (org_id is None or r.org_id == org_id)
            and (usuario is None or r.usuario == usuario)
        ]
        return {
            "total_records": len(filtered),
            "total_tokens_input": sum(r.tokens_input for r in filtered),
            "total_tokens_output": sum(r.tokens_output for r in filtered),
            "total_cost_usd": round(sum(r.costo_usd for r in filtered), 6),
        }

    async def get_usage_by_user(
        self,
        site_id: Optional[str] = None,
        org_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        users: Dict[str, Dict[str, Any]] = {}
        for r in self.records:
            if site_id and r.site_id != site_id:
                continue
            if org_id and r.org_id != org_id:
                continue
            u = r.usuario or "anonimo"
            if u not in users:
                users[u] = {
                    "usuario": u,
                    "site_id": r.site_id,
                    "total_requests": 0,
                    "total_tokens_input": 0,
                    "total_tokens_output": 0,
                    "total_tokens": 0,
                    "total_cost_usd": 0.0,
                }
            users[u]["total_requests"] += 1
            users[u]["total_tokens_input"] += r.tokens_input
            users[u]["total_tokens_output"] += r.tokens_output
            users[u]["total_tokens"] += (r.tokens_input + r.tokens_output)
            users[u]["total_cost_usd"] = round(users[u]["total_cost_usd"] + r.costo_usd, 6)
        return list(users.values())

    async def get_usage_by_site(
        self,
        org_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        sites: Dict[str, Dict[str, Any]] = {}
        for r in self.records:
            if org_id and r.org_id != org_id:
                continue
            s = r.site_id
            if s not in sites:
                sites[s] = {
                    "site_id": s,
                    "org_id": r.org_id,
                    "total_requests": 0,
                    "total_tokens_input": 0,
                    "total_tokens_output": 0,
                    "total_tokens": 0,
                    "total_cost_usd": 0.0,
                }
            sites[s]["total_requests"] += 1
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
            r for r in reversed(self.records)
            if (site_id is None or r.site_id == site_id)
            and (usuario is None or r.usuario == usuario)
        ]
        return filtered[:limit]
