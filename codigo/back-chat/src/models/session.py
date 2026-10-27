"""
Pydantic schemas for Widget Session Handshake.
Supports multi-client identification and division/tenant mapping.
"""

from typing import Optional
from pydantic import BaseModel, Field


class SessionCreateRequest(BaseModel):
    client_id: Optional[str] = Field("sigires", description="Identificador del cliente/empresa (ej. sigires)")
    origin: str = Field(..., description="Origen web del host (ej. https://sigires.procex.co)")
    eps_id: str = Field(..., description="Identificador de la EPS o división (ej. eps_sura_01, eps_sanitas_01)")
    ips_code: str = Field(..., description="Código de habilitación o sucursal de la institución")


class SessionResponse(BaseModel):
    session_token: str = Field(..., description="JWT de sesión para autorizar consultas")
    client_id: str = Field("sigires", description="Identificador de la empresa cliente")
    client_name: str = Field(..., description="Razón social o nombre de la empresa cliente")
    tenant_id: str = Field(..., description="UUID del Tenant / EPS")
    tenant_name: str = Field(..., description="Nombre comercial del Tenant")
    expires_in_seconds: int = Field(1800, description="Vigencia del token en segundos")
