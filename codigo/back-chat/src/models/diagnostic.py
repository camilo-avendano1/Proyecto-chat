"""
Pydantic schemas for Chat and Diagnostic endpoints.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from src.models.common import (
    ChatMessage,
    ErrorDiagnosticModel,
    SourceItem,
    UIContext,
    UserContext,
    UserInfo,
)


class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Consulta o pregunta en lenguaje natural del usuario")
    user: Optional[UserInfo] = Field(
        default=None,
        description="Información genérica del usuario autenticado en la plataforma cliente",
    )
    context: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Contexto genérico de la pantalla, flujo o recurso activo",
    )
    logs: Optional[str] = Field(
        default=None,
        description="Trazas técnicas o logs adjuntos opcionales",
    )
    extras: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Metadatos o filtros opcionales específicos del cliente para la búsqueda RAG",
    )
    conversation_history: Optional[List[ChatMessage]] = Field(
        default_factory=list,
        description="Historial de mensajes previos en la sesión",
    )
    # Alias legados compatibles con integraciones anteriores
    system_logs: Optional[str] = Field(
        default=None,
        description="Alias legado de 'logs' (trazas o logs de error adjuntos)",
    )
    ui_context: Optional[UIContext] = Field(
        default=None,
        description="Alias legado de 'context' para UI del widget",
    )
    user_context: Optional[UserContext] = Field(
        default=None,
        description="Alias legado de 'user' para contexto del usuario",
    )

    def get_logs(self) -> Optional[str]:
        return self.logs or self.system_logs

    def get_usuario(self) -> str:
        if self.user and self.user.id:
            return self.user.id
        if self.user_context and self.user_context.usuario:
            return self.user_context.usuario
        return "anonimo"

    def get_role(self) -> Optional[str]:
        if self.user and self.user.role:
            return self.user.role
        if self.user_context and self.user_context.permisos:
            return self.user_context.permisos
        return None

    def get_org_code(self) -> Optional[str]:
        if self.user and self.user.organization:
            return self.user.organization
        if self.user_context and self.user_context.ips_code:
            return self.user_context.ips_code
        return None

    def get_context_dict(self) -> Dict[str, Any]:
        merged: Dict[str, Any] = {}
        if self.ui_context is not None:
            for key, value in self.ui_context.model_dump(exclude_none=True).items():
                if value is not None:
                    merged[key] = value
            if self.ui_context.model_extra:
                for key, value in self.ui_context.model_extra.items():
                    if value is not None:
                        merged[key] = value
        if self.context:
            for key, value in self.context.items():
                if value is not None:
                    merged[key] = value
        return merged

    def get_user_attributes(self) -> Dict[str, Any]:
        attrs: Dict[str, Any] = {}
        if self.user_context is not None:
            for key in ("filial", "eps", "ips_code", "ips_nombre"):
                value = getattr(self.user_context, key, None)
                if value is not None:
                    attrs[key] = value
            if self.user_context.model_extra:
                for key, value in self.user_context.model_extra.items():
                    if value is not None:
                        attrs[key] = value
        if self.user is not None:
            if self.user.organization is not None:
                attrs["organization"] = self.user.organization
            if self.user.attributes:
                for key, value in self.user.attributes.items():
                    if value is not None:
                        attrs[key] = value
            if self.user.model_extra:
                for key, value in self.user.model_extra.items():
                    if value is not None:
                        attrs[key] = value
        return attrs

    def get_formato_archivo(self) -> Optional[str]:
        ctx = self.get_context_dict()
        value = ctx.get("formato_archivo") or ctx.get("file_format")
        return str(value) if value is not None else None


DiagnosticStreamRequest = ChatRequest


class ChatQueryResponse(BaseModel):
    response: str = Field(..., description="Respuesta o diagnóstico generado por el asistente")
    error_diagnostic: Optional[ErrorDiagnosticModel] = Field(
        None,
        description="Detalles técnicos del error detectado (null si no aplica)",
    )
    sources: List[SourceItem] = Field(default_factory=list, description="Documentos o manuales consultados")


DiagnosticQueryResponse = ChatQueryResponse


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
    client_id: Optional[str] = "default"
    total_requests: int
    llm_requests: int
    fast_path_requests: int
    total_tokens_input: int
    total_tokens_output: int
    total_tokens: int
    total_cost_usd: float


class TenantUsageResponse(BaseModel):
    tenant_id: str
    client_id: Optional[str] = "default"
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
