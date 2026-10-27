"""
Pydantic schemas for Diagnostic and Chat endpoints.
"""

from typing import Optional, List
from pydantic import BaseModel, Field

from src.models.common import (
    UIContext,
    UserContext,
    ChatMessage,
    ErrorDiagnosticModel,
    SourceItem
)


class DiagnosticStreamRequest(BaseModel):
    query: str = Field(..., description="Pregunta en lenguaje natural del usuario")
    system_logs: Optional[str] = Field(None, description="Trazas o logs de error descargados")
    ui_context: UIContext = Field(..., description="Contexto de navegación de la pantalla activa")
    user_context: UserContext = Field(..., description="Contexto del usuario autenticado")
    conversation_history: Optional[List[ChatMessage]] = Field(
        default_factory=list,
        description="Historial de mensajes previos en la sesión"
    )


class DiagnosticQueryResponse(BaseModel):
    response: str = Field(..., description="Diagnóstico y pasos de solución generados por el asistente")
    error_diagnostic: Optional[ErrorDiagnosticModel] = Field(None, description="Detalles técnicos del error detectado")
    sources: List[SourceItem] = Field(default_factory=list, description="Documentos normativos o manuales consultados")


class StatusResponse(BaseModel):
    status: str = "healthy"
    app_name: str
    version: str
    environment: str
    authors: List[str]
    llm_provider: str
    llm_model: str
    llm_base_url: str
    back_busqueda_status: str
    llm_service_status: str
    auth_service_status: Optional[str] = "not_probed"
    llm_gateway_status: Optional[str] = "not_probed"


class UsageSummaryResponse(BaseModel):
    total_records: int
    total_tokens_input: int
    total_tokens_output: int
    total_tokens: int = 0
    total_cost_usd: float
    saved_fast_path_calls: int = 0


class UserUsageResponse(BaseModel):
    usuario: str
    tenant_id: str
    client_id: Optional[str] = "sigires"
    total_requests: int
    llm_requests: int
    fast_path_requests: int
    total_tokens_input: int
    total_tokens_output: int
    total_tokens: int
    total_cost_usd: float


class TenantUsageResponse(BaseModel):
    tenant_id: str
    client_id: Optional[str] = "sigires"
    total_requests: int
    llm_requests: int
    fast_path_requests: int
    total_tokens_input: int
    total_tokens_output: int
    total_tokens: int
    total_cost_usd: float


class SecurityEventItemResponse(BaseModel):
    event_id: str
    request_id: Optional[str] = None
    event_type: str
    severity: str
    client_id: str
    tenant_id: str
    usuario: str
    ips_code: Optional[str] = None
    ip_address: Optional[str] = None
    details: dict = Field(default_factory=dict)
    created_at: str


class MessageLogItemResponse(BaseModel):
    log_id: str
    request_id: Optional[str] = None
    direction: str
    client_id: str
    tenant_id: str
    usuario: str
    ips_code: Optional[str] = None
    content: str
    tokens: int
    costo_usd: float
    latencia_ms: int
    status: str
    created_at: str
