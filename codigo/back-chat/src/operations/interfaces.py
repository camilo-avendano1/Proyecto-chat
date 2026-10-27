"""
Protocols and interfaces for the Operations layer.
Implements dependency inversion via structural typing (Protocol).
Supports Multi-Client and Multi-Tenant routing.
"""

from typing import Any, AsyncGenerator, Dict, List, Optional, Protocol
from src.domain.entities import ClientCompany, KnowledgeSource, Tenant, UsageLedgerRecord


class SearchServiceProtocol(Protocol):
    """Protocol for communicating with Client Search APIs (Retrieval Service)."""

    async def search(
        self,
        query: str,
        client_id: Optional[str] = "sigires",
        busqueda_api_url: Optional[str] = None,
        tenant_id: Optional[str] = None,
        category: Optional[str] = None,
        variable_num: Optional[int] = None,
        error_code: Optional[str] = None,
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
    """Protocol for client, tenant, and session management."""

    def get_client_by_id(self, client_id: str) -> Optional[ClientCompany]:
        """Resolves client company by ID."""
        ...

    def get_tenant_by_key(self, api_key: str) -> Optional[Tenant]:
        """Resolves tenant from API Key."""
        ...

    def get_tenant_by_id(self, tenant_id: str) -> Optional[Tenant]:
        """Resolves tenant by UUID."""
        ...

    def get_tenant_by_eps_code(self, eps_code: str) -> Optional[Tenant]:
        """Resolves tenant by EPS/Division code."""
        ...


class LedgerRepositoryProtocol(Protocol):
    """Protocol for persisting AI token usage and observability metrics."""

    async def record_usage(self, record: UsageLedgerRecord) -> None:
        """Stores a token and latency usage record."""
        ...

    async def get_usage_summary(
        self,
        tenant_id: Optional[str] = None,
        client_id: Optional[str] = None,
        usuario: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Calculates total usage statistics."""
        ...

    async def get_usage_by_user(
        self,
        tenant_id: Optional[str] = None,
        client_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Aggregates token consumption and costs grouped by user."""
        ...

    async def get_usage_by_tenant(
        self,
        client_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Aggregates token consumption and costs grouped by tenant."""
        ...

    async def get_recent_records(
        self,
        limit: int = 50,
        tenant_id: Optional[str] = None,
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
        client_id: Optional[str] = "sigires",
        busqueda_api_url: Optional[str] = None,
        tenant_id: Optional[str] = None,
        category: Optional[str] = None,
        variable_num: Optional[int] = None,
        error_code: Optional[str] = None,
        top_k: int = 5,
    ) -> List[KnowledgeSource]:
        self.call_history.append({
            "query": query,
            "client_id": client_id,
            "busqueda_api_url": busqueda_api_url,
            "tenant_id": tenant_id,
            "category": category,
            "variable_num": variable_num,
            "error_code": error_code,
            "top_k": top_k,
        })
        if self.predefined_sources:
            return self.predefined_sources[:top_k]
        return []


class LLMServiceStub:
    """In-memory stub for LLMServiceProtocol."""

    def __init__(self, simulated_response: str = "Respuesta simulada del asistente clínico."):
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
        clients: Optional[Dict[str, ClientCompany]] = None,
        tenants: Optional[Dict[str, Tenant]] = None
    ):
        self.clients = clients or {}
        self.tenants = tenants or {}

    def get_client_by_id(self, client_id: str) -> Optional[ClientCompany]:
        return self.clients.get(client_id)

    def get_tenant_by_key(self, api_key: str) -> Optional[Tenant]:
        for tenant in self.tenants.values():
            if tenant.api_key_hash == api_key:
                return tenant
        return None

    def get_tenant_by_id(self, tenant_id: str) -> Optional[Tenant]:
        return self.tenants.get(tenant_id)

    def get_tenant_by_eps_code(self, eps_code: str) -> Optional[Tenant]:
        for tenant in self.tenants.values():
            if tenant.codigo_eps.lower() == eps_code.lower():
                return tenant
        return None


class LedgerRepositoryStub:
    """In-memory stub for LedgerRepositoryProtocol."""

    def __init__(self):
        self.records: List[UsageLedgerRecord] = []

    async def record_usage(self, record: UsageLedgerRecord) -> None:
        self.records.append(record)

    async def get_usage_summary(
        self,
        tenant_id: Optional[str] = None,
        client_id: Optional[str] = None,
        usuario: Optional[str] = None,
    ) -> Dict[str, Any]:
        filtered = [
            r for r in self.records
            if (tenant_id is None or r.tenant_id == tenant_id)
            and (client_id is None or r.client_id == client_id)
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
        tenant_id: Optional[str] = None,
        client_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        users: Dict[str, Dict[str, Any]] = {}
        for r in self.records:
            if tenant_id and r.tenant_id != tenant_id:
                continue
            if client_id and r.client_id != client_id:
                continue
            u = r.usuario or "anonimo"
            if u not in users:
                users[u] = {
                    "usuario": u,
                    "tenant_id": r.tenant_id,
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

    async def get_usage_by_tenant(
        self,
        client_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        tenants: Dict[str, Dict[str, Any]] = {}
        for r in self.records:
            if client_id and r.client_id != client_id:
                continue
            t = r.tenant_id
            if t not in tenants:
                tenants[t] = {
                    "tenant_id": t,
                    "client_id": r.client_id,
                    "total_requests": 0,
                    "total_tokens_input": 0,
                    "total_tokens_output": 0,
                    "total_tokens": 0,
                    "total_cost_usd": 0.0,
                }
            tenants[t]["total_requests"] += 1
            tenants[t]["total_tokens_input"] += r.tokens_input
            tenants[t]["total_tokens_output"] += r.tokens_output
            tenants[t]["total_tokens"] += (r.tokens_input + r.tokens_output)
            tenants[t]["total_cost_usd"] = round(tenants[t]["total_cost_usd"] + r.costo_usd, 6)
        return list(tenants.values())

    async def get_recent_records(
        self,
        limit: int = 50,
        tenant_id: Optional[str] = None,
        usuario: Optional[str] = None,
    ) -> List[UsageLedgerRecord]:
        filtered = [
            r for r in reversed(self.records)
            if (tenant_id is None or r.tenant_id == tenant_id)
            and (usuario is None or r.usuario == usuario)
        ]
        return filtered[:limit]
