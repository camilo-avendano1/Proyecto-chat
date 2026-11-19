"""
Pydantic schemas for Widget Session Handshake.
Supports multi-organization identification and site mapping.
"""

from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class SessionCreateRequest(BaseModel):
    origin: Optional[str] = Field(
        default=None,
        description="Origen web del host (opcional si se envía en el encabezado Origin)",
    )
    org_id: Optional[str] = Field(
        default=None,
        description="Identificador opcional de la organización (se infiere desde la API Key)",
    )
    site_code: Optional[str] = Field(
        default=None,
        description="Código opcional de sede o sucursal",
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Metadatos opcionales del contexto de sesión (ej. filial, sede, canal)",
    )


class SessionResponse(BaseModel):
    session_token: str = Field(..., description="JWT de sesión para autorizar consultas")
    org_id: str = Field(..., description="Identificador de la organización")
    org_name: str = Field(..., description="Nombre o razón social de la organización")
    site_id: str = Field(..., description="UUID de la sede (Site)")
    site_name: str = Field(..., description="Nombre comercial de la sede")
    site_code: Optional[str] = Field(default=None, description="Código de la sede")
    site_label: str = Field(default="Sede", description="Etiqueta visible de sede para la organización")
    expires_in_seconds: int = Field(1800, description="Vigencia del token en segundos")
