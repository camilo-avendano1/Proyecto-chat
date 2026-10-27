"""
Configuración del LLM Gateway (Pydantic Settings).
Puerto: 8003
Desarrollado por: Juan Camilo Avendaño, Fran Sneider Quincha, Adriana Moreno.

Responsabilidades del servicio:
- Único punto de contacto hacia proveedores de LLM (LM Studio, Ollama, OpenAI, DeepSeek).
- Fallback a simulación clínica de contingencia.
- Atribución detallada de consumo: cliente, tenant, usuario, rol, operación, request_id, modelo.
- Almacenamiento persistente del libro de consumo (Usage Ledger).
- Consultas de auditoría de consumo agrupadas por usuario, tenant, rol y modelo.
"""

from pathlib import Path
from typing import Dict, List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

SERVICE_DIR = Path(__file__).resolve().parents[1]
CODIGO_DIR = SERVICE_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    SERVICE_NAME: str = "llm-gateway"
    APP_NAME: str = "SaaS Core LLM Gateway & Ingestion Proxy"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    HOST: str = "0.0.0.0"
    PORT: int = 8003
    DEBUG: bool = True

    # Clave de servicio interna (requerida en peticiones /internal/v1/*)
    INTERNAL_SERVICE_KEY: str = "dev_internal_gateway_key_998877"

    # Verificación de JWT de administrador para endpoints /api/v1/usage/*
    ADMIN_JWT_SECRET: str = "dev_admin_jwt_secret_change_me_in_production_0002"
    JWT_ALGORITHM: str = "HS256"
    ADMIN_TOKEN_AUDIENCE: str = "saas-admin"
    JWT_ISSUER: str = "saas-auth-service"

    # Base de datos propia para el libro de consumo de tokens (Usage Ledger)
    DATABASE_URL: str = f"sqlite:///{(SERVICE_DIR / 'data' / 'ledger.db').as_posix()}"

    # Base de datos compartida de auditoría de logs
    LOGS_DATABASE_URL: str = f"sqlite:///{(CODIGO_DIR / 'data' / 'saas_logs.db').as_posix()}"
    ENABLE_AUDIT_DB: bool = True
    LOG_LEVEL: str = "INFO"
    LOG_DIR: str = str(SERVICE_DIR / "logs")
    LOG_JSON_CONSOLE: bool = False
    LOG_FILE_MAX_BYTES: int = 10 * 1024 * 1024
    LOG_FILE_BACKUP_COUNT: int = 10

    # Proveedor LLM (LM Studio por defecto, Ollama u OpenAI)
    LLM_PROVIDER: str = "lmstudio"
    LLM_BASE_URL: str = "http://localhost:1234/v1"
    LLM_MODEL: str = "local-model"
    LLM_API_KEY: str = "lm-studio"
    LLM_TEMPERATURE: float = 0.2
    LLM_MAX_TOKENS: int = 2000
    FALLBACK_SIMULATION_ON_LLM_ERROR: bool = True

    # Precios configurables por millón de tokens (USD)
    # Por defecto para gpt-4o-mini ($0.15 input / $0.60 output por 1M tokens)
    # Modelos locales (lmstudio, ollama) tienen costo 0.0
    INPUT_TOKEN_PRICE_PER_M: float = 0.15
    OUTPUT_TOKEN_PRICE_PER_M: float = 0.60

    CORS_ORIGINS: List[str] = [
        "https://sigires.procex.co",
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ]


settings = Settings()
