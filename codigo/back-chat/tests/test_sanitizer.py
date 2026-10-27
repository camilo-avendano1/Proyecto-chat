"""
Unit tests for PII and PHI Sanitization operations (Ley 1581 de 2012).
"""

from src.operations.sanitizer_operations import PIISanitizer


def test_sanitize_empty_and_none():
    assert PIISanitizer.sanitize(None) is None
    assert PIISanitizer.sanitize("") == ""


def test_sanitize_emails():
    text = "El auditor contacto a medico@ipsanrafael.com para el reporte."
    sanitized = PIISanitizer.sanitize(text)
    assert "[EMAIL_PROTEGIDO]" in sanitized
    assert "medico@ipsanrafael.com" not in sanitized


def test_sanitize_patient_labels_and_names():
    text = "Error en registro | Paciente: Maria Alejandra Gomez | Fila: 12"
    sanitized = PIISanitizer.sanitize(text)
    assert "[DATO_IDENTIFICATIVO_PROTEGIDO]" in sanitized
    assert "Maria Alejandra Gomez" not in sanitized
    assert "Fila: 12" in sanitized


def test_sanitize_citizen_identification_numbers():
    text = "El usuario con CC 1020304050 presentó inconsistencia en la variable 14."
    sanitized = PIISanitizer.sanitize(text)
    assert "[DOCUMENTO_PROTEGIDO]" in sanitized
    assert "1020304050" not in sanitized
    assert "variable 14" in sanitized


def test_preserves_ips_12_digit_habilitation_code():
    text = "Cargue realizado por la IPS habilitación 631300040301 en fecha 2026-07-31."
    sanitized = PIISanitizer.sanitize(text)
    # The 12-digit code beginning with 631300 must be preserved for institutional identification
    assert "631300040301" in sanitized
