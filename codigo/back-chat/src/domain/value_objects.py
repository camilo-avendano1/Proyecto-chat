"""
Value Objects for the Multi-Client Technical & Normative Form Validation Domain.
Pure Python enums and immutable value objects.
"""

from enum import Enum


class ErrorPhase(str, Enum):
    """
    General 3-phase technical validation model for forms and files:
    - FASE_1_CA: Calidad de Archivo / Formato (file format, structure, delimiters, encoding) -> Rechazo de archivo
    - FASE_2_CE: Calidad de Estructura / Campos (data types, mandatory fields, dates, allowed catalogs) -> Con Errores
    - FASE_3_CD: Calidad de Datos / Coherencia (cross-field logic, clinical or normative coherence) -> Alerta / Ajuste
    """
    FASE_1_CA = "FASE_1_CA"
    FASE_2_CE = "FASE_2_CE"
    FASE_3_CD = "FASE_3_CD"
    GENERAL = "GENERAL"


class Severity(str, Enum):
    BLOCKING = "BLOCKING"
    WARNING = "WARNING"
    INFO = "INFO"


class KnowledgeScope(str, Enum):
    """
    Multi-level knowledge scopes returned by the search microservice (back-busqueda):
    - GLOBAL: National/external regulations, technical annexes, clinical guidelines, standards
    - ACCOUNT: Client platform operational manuals, form templates, validator catalogs
    - TENANT: Specific institution/EPS/IPS overrides, local protocols, contract rules
    """
    GLOBAL = "GLOBAL"
    ACCOUNT = "ACCOUNT"
    TENANT = "TENANT"


class DocumentCategory(str, Enum):
    NORMATIVA_TECNICA = "NORMATIVA_TECNICA"
    REGLAMENTO_FORMULARIO = "REGLAMENTO_FORMULARIO"
    MANUAL_OPERATIVO = "MANUAL_OPERATIVO"
    CATALOGO_ERRORES = "CATALOGO_ERRORES"
    # Categorías específicas heredadas (compatibilidad)
    RESOLUCION_202_2021 = "RESOLUCION_202_2021"
    CUENTAS_ALTO_COSTO = "CUENTAS_ALTO_COSTO"
    RESOLUCION_3280_2018 = "RESOLUCION_3280_2018"
    RIPS_RESOLUCION_3374 = "RIPS_RESOLUCION_3374"
    MANUAL_SIGIRES_UI = "MANUAL_SIGIRES_UI"


class UserRole(str, Enum):
    PERFIL_IPS_MEDICO = "PERFIL_IPS_MEDICO"
    PERFIL_IPS_ENFERMERO = "PERFIL_IPS_ENFERMERO"
    PERFIL_IPS_RADICADOR = "PERFIL_IPS_RADICADOR"
    PERFIL_EPS_AUDITOR = "PERFIL_EPS_AUDITOR"
    PERFIL_EPS_ZONAL = "PERFIL_EPS_ZONAL"
    PERFIL_EPS_NACIONAL = "PERFIL_EPS_NACIONAL"
    PERFIL_ANALISTA = "PERFIL_ANALISTA"
