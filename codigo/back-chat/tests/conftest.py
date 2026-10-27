"""
Pytest configuration and shared fixtures for SIGIRES Back Central.
"""

import os
os.environ["DISABLE_SQLALCHEMY_CEXT"] = "1"
import pytest
from fastapi.testclient import TestClient

# Set test environment
os.environ["ENVIRONMENT"] = "testing"
os.environ["JWT_SECRET_KEY"] = "test_jwt_secret_key_1234567890_abcdef"
os.environ["DEFAULT_WIDGET_API_KEY"] = "pk_live_sigires_8f9a2b1c3d4e5f6a"
os.environ["FALLBACK_LOCAL_SEARCH"] = "true"
os.environ["MOCK_LLM_IF_NO_KEY"] = "true"

from src.main import app
from src.infrastructure.security.jwt_handler import default_jwt_handler


@pytest.fixture
def client() -> TestClient:
    """FastAPI TestClient fixture."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def valid_widget_key() -> str:
    return "pk_live_sigires_8f9a2b1c3d4e5f6a"


@pytest.fixture
def valid_session_token() -> str:
    """Generates a valid signed JWT session token for EPS Sura."""
    token = default_jwt_handler.create_session_token({
        "sub": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
        "tenant_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
        "tenant_name": "EPS Sura - Regional Nor-Occidente",
        "eps_id": "eps_sura_01",
        "ips_code": "631300040301",
        "origin": "https://sigires.procex.co",
    })
    return token


@pytest.fixture
def sample_diagnostic_payload() -> dict:
    return {
        "query": "El validador me rechazó el archivo de la resolución 202 con error en la columna 14.",
        "system_logs": "Consecutivo: 104 | Fila: 45 | Columna: 14 | Log: Variable 'Condicion_Usuaria' inválida para sexo masculino. Código error: CE_VAR_014_INVAL",
        "ui_context": {
            "url": "https://sigires.procex.co/carga-archivos/resolucion-202",
            "pagina_actual": "CARGA_ARCHIVOS_202",
            "modulo": "CARGA_ARCHIVOS",
            "active_button_id": "btn_consultar_progreso",
            "field_in_focus": "var_014_gestante",
            "estado_cargue_actual": "CON_ERRORES",
            "formato_archivo": "RESOLUCION_202_2021_ZIP"
        },
        "user_context": {
            "usuario": "dr.juan.perez",
            "filial": "REGIONAL_NOR_OCCIDENTE",
            "eps": "EPS_SURA",
            "ips_code": "631300040301",
            "ips_nombre": "IPS San Rafael Sede Principal",
            "permisos": "PERFIL_IPS_RADICADOR"
        },
        "conversation_history": [
            {
                "role": "user",
                "content": "Subí el archivo pero quedó en estado naranja."
            },
            {
                "role": "assistant",
                "content": "El estado naranja indica Calidad de Estructura (CE)."
            }
        ]
    }
