"""
Unit tests for Generic Technical Log Parser and Form Validation Classifier operations.
"""

from src.domain.value_objects import ErrorPhase, Severity
from src.operations.log_parser_operations import LogParserOperations


def test_parse_phase_2_explicit_field_and_code():
    system_logs = "Consecutivo: 104 | Fila: 45 | Columna: 14 | Log: Variable 'Condicion_Usuaria' inválida para sexo masculino. Código error: CE_VAR_014_INVAL"
    query = "El validador me rechazó el formulario con error en la columna 14."

    diagnostic = LogParserOperations.parse_log_or_query(
        system_logs=system_logs,
        query=query,
        formato_archivo="FORMULARIO_CLINICO_CSV"
    )

    assert diagnostic.affected_row == 45
    assert diagnostic.affected_variable_number == 14
    assert diagnostic.affected_variable_name == "Condicion_Usuaria"
    assert diagnostic.error_phase == ErrorPhase.FASE_2_CE
    assert diagnostic.category == "CALIDAD_ESTRUCTURA_CAMPOS"
    assert diagnostic.detected_code == "CE_VAR_014_INVAL"
    assert diagnostic.severity == Severity.BLOCKING


def test_parse_phase_1_file_format_and_delimiters():
    system_logs = "Error de Calidad de Archivo: La fila 80 no contiene el numero de columnas requeridas. Delimitador pipeline incompleto."
    query = "El cargue del formato fue rechazado en Fase 1."

    diagnostic = LogParserOperations.parse_log_or_query(
        system_logs=system_logs,
        query=query,
        formato_archivo="ARCHIVO_PLANO_TXT"
    )

    assert diagnostic.affected_row == 80
    assert diagnostic.error_phase == ErrorPhase.FASE_1_CA
    assert diagnostic.category == "CALIDAD_ARCHIVO_FORMATO"
    assert diagnostic.severity == Severity.BLOCKING


def test_parse_phase_3_cross_field_coherence():
    system_logs = "Alerta Fase 3 Calidad de Datos: Cruce lógico en fila 12. Inconsistencia entre diagnóstico y procedimiento reportado en campo 77."
    query = "Tengo una alerta de coherencia en el formulario."

    diagnostic = LogParserOperations.parse_log_or_query(
        system_logs=system_logs,
        query=query,
        formato_archivo="REPORTE_CLINICO_XML"
    )

    assert diagnostic.affected_row == 12
    assert diagnostic.affected_variable_number == 77
    assert diagnostic.error_phase == ErrorPhase.FASE_3_CD
    assert diagnostic.category == "CALIDAD_DATOS_CRUCES_LOGICOS"


def test_parse_when_no_logs_provided_does_not_hardcode_variable_names():
    system_logs = None
    query = "¿Cómo corrijo el valor del campo 11 sobre sexo en mayúscula?"

    diagnostic = LogParserOperations.parse_log_or_query(
        system_logs=system_logs,
        query=query,
    )

    assert diagnostic.affected_variable_number == 11
    # Variable definition comes from back-busqueda, not hardcoded in the parser
    assert diagnostic.affected_variable_name is None
    assert diagnostic.error_phase == ErrorPhase.FASE_2_CE
    assert diagnostic.detected_code == "CE_VAR_011_INVAL"
