"""
Configuration settings for SaaS Core Back Central.
Developed by: Juan Camilo Avendaño, Fran Sneider Quincha, Adriana Moreno.
Managed via Pydantic Settings.
"""

from pathlib import Path
from typing import Dict, List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

SERVICE_DIR = Path(__file__).resolve().parents[1]
CODIGO_DIR = SERVICE_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    SERVICE_NAME: str = "back-chat"
    APP_NAME: str = "Core SaaS Chat & Diagnostic Gateway (Back Central)"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = True

    # Authors / Development Team
    AUTHORS: List[str] = [
        "Juan Camilo Avendaño",
        "Fran Sneider Quincha",
        "Adriana Moreno"
    ]

    # Microservicios satélite
    AUTH_SERVICE_URL: str = "http://localhost:8002"
    LLM_GATEWAY_URL: str = "http://localhost:8003"
    INTERNAL_SERVICE_KEY: str = "dev_internal_gateway_key_998877"

    # LLM Settings (para fallback local o reenvío a gateway)
    LLM_PROVIDER: str = "lmstudio"
    LLM_BASE_URL: str = "http://localhost:1234/v1"
    LLM_MODEL: str = "local-model"
    LLM_API_KEY: str = "lm-studio"
    LLM_TEMPERATURE: float = 0.2
    LLM_MAX_TOKENS: int = 1200
    FALLBACK_SIMULATION_ON_LLM_ERROR: bool = True

    # Multi-Client Search API routing
    BACK_BUSQUEDA_URL: str = "http://localhost:8001"
    CLIENT_BUSQUEDA_URLS: Dict[str, str] = {
        "sigires": "http://localhost:8001",
        "default": "http://localhost:8001"
    }
    BACK_BUSQUEDA_TIMEOUT_SECONDS: float = 5.0
    FALLBACK_LOCAL_SEARCH: bool = True
    # Clave de servicio enviada en X-Internal-Key a las APIs de búsqueda
    BUSQUEDA_SERVICE_KEY: str = "dev_busqueda_service_key_change_me"

    # Security & Tokens
    WIDGET_JWT_SECRET: str = "dev_widget_jwt_secret_change_me_in_production_0001"
    ADMIN_JWT_SECRET: str = "dev_admin_jwt_secret_change_me_in_production_0002"
    JWT_SECRET_KEY: str = "dev_widget_jwt_secret_change_me_in_production_0001"
    JWT_ALGORITHM: str = "HS256"
    WIDGET_TOKEN_AUDIENCE: str = "saas-widget"
    ADMIN_TOKEN_AUDIENCE: str = "saas-admin"
    JWT_ISSUER: str = "saas-auth-service"
    SESSION_EXPIRES_SECONDS: int = 1800
    DEFAULT_WIDGET_API_KEY: str = "pk_live_sigires_8f9a2b1c3d4e5f6a"

    # Base de datos central de auditoría de logs
    LOGS_DATABASE_URL: str = f"sqlite:///{(CODIGO_DIR / 'data' / 'saas_logs.db').as_posix()}"
    ENABLE_AUDIT_DB: bool = True
    LOG_LEVEL: str = "INFO"
    LOG_DIR: str = str(SERVICE_DIR / "logs")
    LOG_JSON_CONSOLE: bool = False
    LOG_FILE_MAX_BYTES: int = 10 * 1024 * 1024
    LOG_FILE_BACKUP_COUNT: int = 10

    # Compliance & Data Privacy (Habeas Data - Ley 1581 de 2012)
    ENABLE_PII_SCRUBBING: bool = True

    # CORS
    CORS_ORIGINS: List[str] = [
        "https://sigires.procex.co",
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ]


settings = Settings()
