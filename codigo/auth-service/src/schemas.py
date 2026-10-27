"""
Esquemas Pydantic v2 (Request/Response) del Auth Service.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------- Widget
class SessionCreateRequest(BaseModel):
    client_id: Optional[str] = Field("sigires", description="Identificador de la empresa cliente")
    origin: str = Field(..., description="Dominio de origen de la solicitud")
    eps_id: str = Field(..., description="Identificador de la EPS / división")
    ips_code: str = Field(..., description="Código de habilitación de la IPS")


class SessionResponse(BaseModel):
    session_token: str
    client_id: str
    client_name: str
    tenant_id: str
    tenant_name: str
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
    client_id: Optional[str] = None


class AdminProfile(BaseModel):
    admin_id: str
    username: str
    full_name: Optional[str] = None
    role: str
    client_id: Optional[str] = None
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
    role: str = Field(..., description="SUPERADMIN o CLIENT_ADMIN")
    client_id: Optional[str] = Field(None, description="Obligatorio para CLIENT_ADMIN")
    full_name: Optional[str] = Field(None, max_length=255)


class AdminUserUpdateRequest(BaseModel):
    full_name: Optional[str] = Field(None, max_length=255)
    password: Optional[str] = Field(None, min_length=10, max_length=72)
    role: Optional[str] = None
    client_id: Optional[str] = None
    is_active: Optional[bool] = None
