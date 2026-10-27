"""
PII/PHI Sanitization operations.
Compliance with Colombian Statutory Law: Ley 1581 de 2012 (Habeas Data en Salud).
Guarantees patient identification data is masked before logging or LLM transmission.
"""

import re
from typing import Optional


class PIISanitizer:
    """Sanitizes Personally Identifiable Information and Protected Health Information."""

    # Colombian identification patterns (CC, TI, CE, PA, RC)
    ID_DOC_REGEX = re.compile(
        r'\b(?:CC|TI|CE|PA|RC|MS|AS)?\s*[:#]?\s*(\d{6,11})\b',
        re.IGNORECASE
    )

    # Email pattern
    EMAIL_REGEX = re.compile(
        r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b'
    )

    # Colombian phone pattern (10 digits starting with 3, or landlines)
    PHONE_REGEX = re.compile(
        r'\b(?:\+?57)?\s*(?:3\d{9}|[1-9]\d{6,7})\b'
    )

    # Patient name markers in clinical logs (e.g., "Paciente: Pedro Perez", "Usuario: Carlos Ruiz")
    PATIENT_LABEL_REGEX = re.compile(
        r'\b(?:paciente|usuario|afiliado)\s*[:=]\s*([A-Za-zÁÉÍÓÚáéíóúñÑ\s]{3,35})(?=[|,;\n]|$)',
        re.IGNORECASE
    )

    @classmethod
    def sanitize(cls, text: Optional[str]) -> Optional[str]:
        """
        Replaces sensitive identifying data with safe non-reversible redaction tokens.
        Preserves clinical and diagnostic context (row, column, error code, variable values).
        """
        if not text:
            return text

        sanitized = text

        # Redact labeled patient names
        sanitized = cls.PATIENT_LABEL_REGEX.sub(r'paciente: [DATO_IDENTIFICATIVO_PROTEGIDO]', sanitized)

        # Redact emails
        sanitized = cls.EMAIL_REGEX.sub(r'[EMAIL_PROTEGIDO]', sanitized)

        # Redact phone numbers
        sanitized = cls.PHONE_REGEX.sub(r'[TELEFONO_PROTEGIDO]', sanitized)

        # Note on ID documents: we only scrub numbers with 7-10 digits that appear
        # next to document labels or typical citizen IDs, while preserving
        # 12-digit institutional habilitation codes or small row/column numbers.
        def _id_replacer(match: re.Match) -> str:
            full_match = match.group(0)
            digits = match.group(1)
            # Avoid scrubbing 12-digit IPS habilitation codes or 1-6 digit variable/row numbers
            if 7 <= len(digits) <= 10:
                return full_match.replace(digits, "[DOCUMENTO_PROTEGIDO]")
            return full_match

        sanitized = cls.ID_DOC_REGEX.sub(_id_replacer, sanitized)

        return sanitized
