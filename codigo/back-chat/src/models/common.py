"""
Shared Pydantic models for context, user info, error diagnostics, and sources.
Supports both generic multi-client payloads and legacy UIContext/UserContext contracts.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class UserInfo(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: Optional[str] = Field(default=None, description="Identificador del usuario en la plataforma cliente")
    role: Optional[str] = Field(default=None, description="Rol o perfil del usuario")
    organization: Optional[str] = Field(
        default=None,
        description="Organización, sede, sucursal o división del usuario",
    )
    attributes: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Atributos adicionales opcionales del usuario específicos del cliente",
    )


class UIContext(BaseModel):
    model_config = ConfigDict(extra="allow")

    url: Optional[str] = Field(default=None, description="URL de la pantalla o vista activa en la plataforma cliente")
    pagina_actual: Optional[str] = Field(default=None, description="Identificador de la vista o pantalla activa")
    modulo: Optional[str] = Field(default=None, description="Módulo o sección del sistema cliente")
    active_button_id: Optional[str] = Field(default=None, description="ID del botón o acción activa")
    field_in_focus: Optional[str] = Field(default=None, description="Campo o variable en el que se encuentra el usuario")
    estado_cargue_actual: Optional[str] = Field(
        default=None,
        description="Estado opcional de validación o proceso actual (ej. EXITOSO, CON_ERRORES, RECHAZADO)",
    )
    formato_archivo: Optional[str] = Field(
        default=None,
        description="Formato opcional del recurso o archivo (ej. CSV, TXT, XML, JSON, ZIP)",
    )


class UserContext(BaseModel):
    model_config = ConfigDict(extra="allow")

    usuario: Optional[str] = Field(default=None, description="Identificador del usuario autenticado")
    filial: Optional[str] = Field(default=None, description="Sede, regional o división operativa")
    eps: Optional[str] = Field(default=None, description="Identificador de la división o entidad asociada")
    ips_code: Optional[str] = Field(default=None, description="Código de sede, sucursal u organización")
    ips_nombre: Optional[str] = Field(default=None, description="Nombre o razón social de la sede o institución")
    permisos: Optional[str] = Field(default=None, description="Rol o perfil de permisos del usuario")


class ChatMessage(BaseModel):
    role: str = Field(..., description="'user' o 'assistant'")
    content: str = Field(..., description="Contenido textual del mensaje")


class ErrorDiagnosticModel(BaseModel):
    detected_code: str = Field(..., description="Código de error técnico detectado en el log o consulta")
    error_phase: str = Field(..., description="Fase técnica detectada en el log o validación")
    affected_variable_number: Optional[int] = Field(None, description="Número de campo, columna o variable afectada")
    affected_variable_name: Optional[str] = Field(None, description="Nombre del campo o variable afectada (si se identifica en el log o contexto)")
    affected_row: Optional[int] = Field(None, description="Fila o número de registro donde ocurrió la inconsistencia")
    severity: str = Field("BLOCKING", description="Severidad: BLOCKING, WARNING, INFO")
    category: str = Field("CALIDAD_ESTRUCTURA_CAMPOS", description="Categoría técnica de validación")


class SourceItem(BaseModel):
    document_title: str = Field(..., description="Título del documento, política, guía o manual recuperado por la búsqueda")
    scope: str = Field(..., description="Alcance del documento: GLOBAL, ACCOUNT, TENANT")
    section: str = Field(..., description="Sección, capítulo o apartado específico")
