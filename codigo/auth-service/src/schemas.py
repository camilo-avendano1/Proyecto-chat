"""
Esquemas Pydantic v2 (Request/Response) del Auth Service.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------- Widget
class SessionCreateRequest(BaseModel):
    origin: Optional[str] = Field(None, description="Dominio de origen (opcional si se envía en cabecera HTTP Origin)")
    org_id: Optional[str] = Field(None, description="Identificador opcional de la organización; se resuelve desde X-Widget-Key")
    site_code: Optional[str] = Field(None, description="Código opcional de sede/IPS")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Metadatos opcionales propios de la organización o sede")


class SessionResponse(BaseModel):
    session_token: str
    org_id: str
    org_name: str
    site_id: str
    site_name: str
    site_code: str
    site_label: str
    expires_in_seconds: int


# ---------------------------------------------------------------- Admin auth
class AdminLoginRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=100)
    password: str = Field(..., min_length=1, max_length=200)


class AdminTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_seconds: int
    admin_id: str
    username: str
    role: str
    org_id: Optional[str] = None
    org_name: Optional[str] = None
    site_label: Optional[str] = None
    site_label_plural: Optional[str] = None


class AdminProfile(BaseModel):
    admin_id: str
    username: str
    full_name: Optional[str] = None
    role: str
    org_id: Optional[str] = None
    org_name: Optional[str] = None
    site_label: Optional[str] = None
    site_label_plural: Optional[str] = None
    is_active: bool
    last_login_at: Optional[datetime] = None
    created_at: datetime


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., min_length=1, max_length=200)
    new_password: str = Field(..., min_length=10, max_length=72)


# ---------------------------------------------------------------- Admin users
class AdminUserCreateRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=100, pattern=r"^[a-zA-Z0-9._-]+$")
    password: str = Field(..., min_length=10, max_length=72)
    role: str = Field(..., description="GLOBAL_ADMIN u ORG_ADMIN")
    org_id: Optional[str] = Field(None, description="Obligatorio para ORG_ADMIN")
    full_name: Optional[str] = Field(None, max_length=255)


class AdminUserUpdateRequest(BaseModel):
    full_name: Optional[str] = Field(None, max_length=255)
    password: Optional[str] = Field(None, min_length=10, max_length=72)
    role: Optional[str] = None
    org_id: Optional[str] = None
    is_active: Optional[bool] = None


# ---------------------------------------------------------------- Organizations & Sites
class OrganizationSummaryResponse(BaseModel):
    org_id: str
    nombre: str
    busqueda_api_url: str
    dominios_permitidos: List[str]
    site_label: str
    site_label_plural: str
    status: str
    site_count: int
    active_site_count: int
    created_at: datetime


class OrganizationCreateRequest(BaseModel):
    org_id: str = Field(..., min_length=2, max_length=100, pattern=r"^[a-z0-9][a-z0-9_-]{1,99}$")
    nombre: str = Field(..., min_length=2, max_length=255)
    busqueda_api_url: str = Field("http://localhost:8001", max_length=500)
    dominios_permitidos: List[str] = Field(default_factory=lambda: ["*"])
    site_label: str = Field("Sede", min_length=1, max_length=50)
    site_label_plural: str = Field("Sedes", min_length=1, max_length=50)


class OrganizationUpdateRequest(BaseModel):
    nombre: Optional[str] = Field(None, min_length=2, max_length=255)
    busqueda_api_url: Optional[str] = Field(None, max_length=500)
    dominios_permitidos: Optional[List[str]] = None
    site_label: Optional[str] = Field(None, min_length=1, max_length=50)
    site_label_plural: Optional[str] = Field(None, min_length=1, max_length=50)
    status: Optional[str] = None


class SiteSummaryResponse(BaseModel):
    site_id: str
    org_id: str
    org_name: str
    nombre: str
    site_code: str
    dominios_permitidos: List[str]
    api_key_prefix: str
    status: str
    created_at: datetime


class SiteCreateRequest(BaseModel):
    org_id: Optional[str] = Field(None, description="Obligatorio para GLOBAL_ADMIN; ignorado/forzado para ORG_ADMIN")
    nombre: str = Field(..., min_length=2, max_length=255)
    site_code: Optional[str] = Field(None, max_length=100)
    dominios_permitidos: List[str] = Field(default_factory=lambda: ["*"])


class SiteCreatedResponse(SiteSummaryResponse):
    api_key: str


class SiteUpdateRequest(BaseModel):
    nombre: Optional[str] = Field(None, min_length=2, max_length=255)
    site_code: Optional[str] = Field(None, max_length=100)
    dominios_permitidos: Optional[List[str]] = None
    status: Optional[str] = None
    rotate_api_key: bool = False


class SiteUpdatedResponse(SiteSummaryResponse):
    new_api_key: Optional[str] = None
