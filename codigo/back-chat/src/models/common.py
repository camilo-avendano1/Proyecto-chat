"""
Shared Pydantic models for context, error diagnostics, and sources.
Follows formal contract defined in especificacion-api-integracion-widget.md.
"""

from typing import Optional, List
from pydantic import BaseModel, Field


class UIContext(BaseModel):
    url: str = Field(..., description="URL de la pantalla o formulario activo en la plataforma cliente")
    pagina_actual: str = Field(..., description="Identificador de la vista o formulario activo")
    modulo: str = Field(..., description="Módulo del sistema (ej. CARGA_ARCHIVOS, FORMULARIOS_CLINICOS, INFORMES)")
    active_button_id: Optional[str] = Field(None, description="ID del botón o acción activa")
    field_in_focus: Optional[str] = Field(None, description="Campo o variable en el que se encuentra el usuario")
    estado_cargue_actual: Optional[str] = Field(
        "NO_APLICA",
        description="Estado de validación/cargue: EXITOSO, CON_ERRORES, RECHAZADO, NO_APLICA"
    )
    formato_archivo: Optional[str] = Field(
        None,
        description="Formato del formulario o archivo a validar (ej. CSV, TXT, XML, JSON, ZIP, FORMULARIO_WEB)"
    )


class UserContext(BaseModel):
    usuario: str = Field(..., description="Identificador del profesional o usuario autenticado (médico, enfermero, radicador, auditor)")
    filial: Optional[str] = Field(None, description="Sede, regional o división operativa")
    eps: str = Field(..., description="Identificador de la entidad aseguradora o división cliente")
    ips_code: str = Field(..., description="Código de habilitación o identificador de la institución prestadora")
    ips_nombre: Optional[str] = Field(None, description="Nombre o razón social de la institución")
    permisos: Optional[str] = Field(
        "PERFIL_IPS_RADICADOR",
        description="Rol del usuario: PERFIL_IPS_MEDICO, PERFIL_IPS_ENFERMERO, PERFIL_IPS_RADICADOR, PERFIL_EPS_AUDITOR, etc."
    )


class ChatMessage(BaseModel):
    role: str = Field(..., description="'user' o 'assistant'")
    content: str = Field(..., description="Contenido textual del mensaje")


class ErrorDiagnosticModel(BaseModel):
    detected_code: str = Field(..., description="Código de error técnico detectado en el log o consulta")
    error_phase: str = Field(..., description="Fase de validación: FASE_1_CA (Archivo/Formato), FASE_2_CE (Estructura/Campos), FASE_3_CD (Datos/Coherencia)")
    affected_variable_number: Optional[int] = Field(None, description="Número de campo, columna o variable afectada")
    affected_variable_name: Optional[str] = Field(None, description="Nombre del campo o variable afectada (si se identifica en el log o contexto)")
    affected_row: Optional[int] = Field(None, description="Fila o número de registro donde ocurrió la inconsistencia")
    severity: str = Field("BLOCKING", description="Severidad: BLOCKING, WARNING, INFO")
    category: str = Field("CALIDAD_ESTRUCTURA_CAMPOS", description="Categoría técnica de validación")


class SourceItem(BaseModel):
    document_title: str = Field(..., description="Título del documento, reglamento o manual recuperado por la búsqueda")
    scope: str = Field(..., description="Alcance del documento: GLOBAL, ACCOUNT, TENANT")
    section: str = Field(..., description="Sección, capítulo o anexo específico")
