"""
Pydantic schemas for Widget Session Handshake.
Supports multi-client identification and division/tenant mapping.
"""

from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class SessionCreateRequest(BaseModel):
    origin: Optional[str] = Field(
        default=None,
        description="Origen web del host (opcional si se envía en el encabezado Origin)",
    )
    client_id: Optional[str] = Field(
        default=None,
        description="Identificador opcional del cliente/empresa (se infiere desde la API Key)",
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Metadatos opcionales del contexto de sesión (ej. filial, sede, canal)",
    )
    eps_id: Optional[str] = Field(
        default=None,
        description="Alias legado opcional de división o entidad",
    )
    ips_code: Optional[str] = Field(
        default=None,
        description="Alias legado opcional de código de sede o sucursal",
    )


class SessionResponse(BaseModel):
    session_token: str = Field(..., description="JWT de sesión para autorizar consultas")
    client_id: str = Field(..., description="Identificador de la empresa cliente")
    client_name: str = Field(..., description="Razón social o nombre de la empresa cliente")
    tenant_id: str = Field(..., description="UUID del Tenant / división")
    tenant_name: str = Field(..., description="Nombre comercial del Tenant")
    expires_in_seconds: int = Field(1800, description="Vigencia del token en segundos")
