"""
Generic Technical Log Parser and Form Validation Classifier.
Extracts structured technical metadata from raw validator logs and user queries
across multiple form formats (TXT, CSV, XML, JSON, ZIP, Web Forms) without
hardcoding any specific regulation or variable catalog:
- Phase:
  * FASE_1_CA: Calidad de Archivo / Formato (structure, delimiters, encoding, columns)
  * FASE_2_CE: Calidad de Estructura / Campos (data types, dates, allowed catalogs, ranges)
  * FASE_3_CD: Calidad de Datos / Coherencia (cross-field clinical or logical rules)
- Row / Record number, Column / Field / Variable number and explicitly cited field name
- Error Code, Severity, and Generic Validation Category to pass as search hints to back-busqueda.
"""

import re
from typing import Optional, Tuple

from src.domain.entities import ErrorDiagnostic
from src.domain.value_objects import ErrorPhase, Severity


class LogParserOperations:
    """
    Parses and extracts generic diagnostic metadata from validation logs and user text.
    Does not assume a specific regulation; field definitions and normative rules
    are resolved dynamically by the search service (back-busqueda).
    """

    ROW_REGEX = re.compile(
        r'\b(?:fila|row|l[ií]nea|registro|record)\s*(?:no\.?|n[uú]mero|#|:|=)?\s*(\d+)\b',
        re.IGNORECASE,
    )
    COL_REGEX = re.compile(
        r'\b(?:columna|col|variable|var|campo|field|posici[oó]n)\s*(?:no\.?|n[uú]mero|#|:|=)?\s*(\d+)\b',
        re.IGNORECASE,
    )
    CONSECUTIVE_REGEX = re.compile(
        r'\b(?:consecutivo|consec)\s*[:=]?\s*(\d+)\b',
        re.IGNORECASE,
    )
    CODE_REGEX = re.compile(r'\b([A-Z]{2,6}_[A-Z0-9_]{2,25})\b')

    # Extracts explicitly quoted or labeled field/variable names in logs, e.g.:
    # Variable 'Condicion_Usuaria', Campo "fecha_ingreso", campo: peso_kg
    FIELD_NAME_QUOTED_REGEX = re.compile(
        r'\b(?:variable|campo|columna|field)\s*(?:\d+\s*)?[:=-]?\s*[\'"]([A-Za-zÁÉÍÓÚáéíóúñÑ0-9_ -]{2,50})[\'"]',
        re.IGNORECASE,
    )
    FIELD_NAME_PAREN_REGEX = re.compile(
        r'\b(?:variable|campo|columna)\s+\d+\s*\(\s*([A-Za-zÁÉÍÓÚáéíóúñÑ0-9_ -]{2,50})\s*\)',
        re.IGNORECASE,
    )

    @classmethod
    def parse_log_or_query(
        cls,
        system_logs: Optional[str],
        query: str,
        formato_archivo: Optional[str] = None,
    ) -> ErrorDiagnostic:
        """
        Extracts row, column/field number, explicitly mentioned field name, validation phase, and error code.
        Combines system_logs and query to provide clean search metadata for back-busqueda.
        """
        combined_text = f"{system_logs or ''} {query}".strip()

        # 1. Extract Row / Record number
        affected_row = None
        row_match = cls.ROW_REGEX.search(combined_text)
        if row_match:
            try:
                affected_row = int(row_match.group(1))
            except ValueError:
                affected_row = None

        # 2. Extract Column / Variable / Field number
        var_num = None
        col_match = cls.COL_REGEX.search(combined_text)
        if col_match:
            try:
                var_num = int(col_match.group(1))
            except ValueError:
                var_num = None

        # 3. Detect Validation Phase (CA / CE / CD) and generic category
        phase, category = cls._detect_phase(combined_text, formato_archivo)

        # 4. Extract Variable / Field Name ONLY if explicitly present in the log or query
        var_name = cls._extract_explicit_field_name(combined_text)

        # 5. Detect explicit Error Code or synthesize a generic one
        code_match = cls.CODE_REGEX.search(combined_text)
        if code_match:
            detected_code = code_match.group(1)
        else:
            detected_code = cls._synthesize_error_code(phase, var_num)

        # Determine severity
        severity = (
            Severity.BLOCKING
            if phase in (ErrorPhase.FASE_1_CA, ErrorPhase.FASE_2_CE)
            else Severity.WARNING
        )

        return ErrorDiagnostic(
            detected_code=detected_code,
            error_phase=phase,
            affected_variable_number=var_num,
            affected_variable_name=var_name,
            affected_row=affected_row,
            severity=severity,
            category=category,
        )

    @classmethod
    def _extract_explicit_field_name(cls, text: str) -> Optional[str]:
        """
        Extracts a field/variable name only when explicitly cited in the log or query
        (e.g., Variable 'Condicion_Usuaria' or Variable 14 (Gestante)), without
        consulting any hardcoded regulation table.
        """
        quoted_match = cls.FIELD_NAME_QUOTED_REGEX.search(text)
        if quoted_match:
            return quoted_match.group(1).strip()

        paren_match = cls.FIELD_NAME_PAREN_REGEX.search(text)
        if paren_match:
            return paren_match.group(1).strip()

        return None

    @classmethod
    def _detect_phase(cls, text: str, formato_archivo: Optional[str]) -> Tuple[ErrorPhase, str]:
        lower = text.lower()

        # FASE 1: Calidad de Archivo / Formato (CA)
        # Delimitadores, estructura del archivo/formulario, conteo de columnas, codificación, extensión
        if (
            "fase 1" in lower
            or "calidad de archivo" in lower
            or "delimitador" in lower
            or "pipeline" in lower
            or "piping" in lower
            or "caracteres especiales" in lower
            or "numero de columnas" in lower
            or "columnas requeridas" in lower
            or "estructura del archivo" in lower
            or "formato de archivo" in lower
            or "codificacion" in lower
            or "ca_" in lower
        ):
            return ErrorPhase.FASE_1_CA, "CALIDAD_ARCHIVO_FORMATO"

        # FASE 3: Calidad de Datos / Coherencia Lógica (CD)
        # Cruces lógicos inter-campos o coherencia clínica/normativa
        if (
            "fase 3" in lower
            or "calidad de datos" in lower
            or "cruce logico" in lower
            or "cruce lógico" in lower
            or "coherencia" in lower
            or "inconsistencia entre" in lower
            or "cd_" in lower
        ):
            return ErrorPhase.FASE_3_CD, "CALIDAD_DATOS_CRUCES_LOGICOS"

        # FASE 2: Calidad de Estructura / Campos (CE) - Default para validación de campos/variables
        return ErrorPhase.FASE_2_CE, "CALIDAD_ESTRUCTURA_CAMPOS"

    @classmethod
    def _synthesize_error_code(cls, phase: ErrorPhase, var_num: Optional[int]) -> str:
        prefix = "CE"
        if phase == ErrorPhase.FASE_1_CA:
            prefix = "CA"
        elif phase == ErrorPhase.FASE_3_CD:
            prefix = "CD"

        if var_num:
            return f"{prefix}_VAR_{var_num:03d}_INVAL"
        return f"{prefix}_GENERAL_VAL_ERR"
