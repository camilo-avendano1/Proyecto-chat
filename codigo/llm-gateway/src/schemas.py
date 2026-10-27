"""
Pydantic schemas for LLM Gateway (internal chat and admin usage monitoring).
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class CallerContext(BaseModel):
    client_id: str = Field("sigires", description="Identificador de la empresa cliente")
    tenant_id: str = Field("unknown", description="Identificador del tenant o filial")
    usuario: str = Field("anonimo", description="Identificador del usuario final o sistema")
    rol: Optional[str] = Field(None, description="Rol del usuario (PERFIL_IPS_MEDICO, PERFIL_IPS_RADICADOR, etc.)")
    ips_code: Optional[str] = Field(None, description="Código de habilitación de la IPS")
    operacion: str = Field("DIAGNOSTIC_QUERY", description="Tipo de operación clínica o asistencial")
    request_id: Optional[str] = Field(None, description="ID único correlacional de la petición")
    model_requested: Optional[str] = Field(None, description="Modelo específico solicitado opcional")


class ChatRequest(BaseModel):
    system_prompt: str
    user_prompt: str
    history: Optional[List[Dict[str, str]]] = Field(default_factory=list)
    caller: CallerContext
    stream: bool = False


class ChatResponse(BaseModel):
    response: str
    model_used: str
    provider_used: str
    tokens_input: int
    tokens_output: int
    tokens_total: int
    costo_usd: float
    latencia_ms: int
    token_source: str


class UsageEventRecordRequest(BaseModel):
    caller: CallerContext
    tokens_input: int = 0
    tokens_output: int = 0
    costo_usd: float = 0.0
    latencia_ms: int = 0
    status: str = "COMPLETED"
    is_llm_call: bool = False
    query_preview: Optional[str] = None


class UsageSummaryResponse(BaseModel):
    total_records: int
    total_tokens_input: int
    total_tokens_output: int
    total_tokens: int
    total_cost_usd: float
    saved_fast_path_calls: int


class UserUsageResponse(BaseModel):
    usuario: str
    tenant_id: str
    client_id: str
    rol: str
    total_requests: int
    llm_requests: int
    fast_path_requests: int
    total_tokens_input: int
    total_tokens_output: int
    total_tokens: int
    total_cost_usd: float


class TenantUsageResponse(BaseModel):
    tenant_id: str
    client_id: str
    total_requests: int
    llm_requests: int
    fast_path_requests: int
    total_tokens_input: int
    total_tokens_output: int
    total_tokens: int
    total_cost_usd: float


class RoleUsageResponse(BaseModel):
    rol: str
    client_id: str
    total_requests: int
    total_tokens: int
    total_cost_usd: float


class ModelUsageResponse(BaseModel):
    model: str
    provider: str
    total_requests: int
    total_tokens: int
    total_cost_usd: float


class UsageRecordItemResponse(BaseModel):
    ledger_id: str
    request_id: Optional[str] = None
    client_id: str
    tenant_id: str
    usuario: str
    rol: Optional[str] = None
    ips_code: Optional[str] = None
    operacion: str
    tokens_input: int
    tokens_output: int
    tokens_total: int
    costo_usd: float
    latencia_ms: int
    model: Optional[str] = None
    provider: Optional[str] = None
    status: str
    is_llm_call: bool
    token_source: str
    query_preview: Optional[str] = None
    created_at: Optional[str] = None
