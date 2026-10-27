"""
Configuración del Auth Service (Pydantic Settings).
Desarrollado por: Juan Camilo Avendaño, Fran Sneider Quincha, Adriana Moreno.

Responsabilidades del servicio:
- Autenticación de usuarios finales del widget (handshake con API Key pública + JWT de sesión).
- Autenticación de administradores (usuario/contraseña bcrypt + JWT de admin con roles).
"""

from pathlib import Path
from typing import Dict, List, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict

SERVICE_DIR = Path(__file__).resolve().parents[1]
CODIGO_DIR = SERVICE_DIR.parent

INSECURE_DEFAULT_SECRETS = {
    "dev_widget_jwt_secret_change_me_in_production_0001",
    "dev_admin_jwt_secret_change_me_in_production_0002",
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    SERVICE_NAME: str = "auth-service"
    APP_NAME: str = "SaaS Auth Service (Usuarios Widget y Administradores)"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    HOST: str = "0.0.0.0"
    PORT: int = 8002
    DEBUG: bool = True

    # Base de datos propia del servicio (clientes, tenants, administradores)
    DATABASE_URL: str = f"sqlite:///{(SERVICE_DIR / 'data' / 'auth.db').as_posix()}"

    # Sistema de logs
    LOG_LEVEL: str = "INFO"
    LOG_DIR: str = str(SERVICE_DIR / "logs")
    LOG_JSON_CONSOLE: bool = False
    LOG_FILE_MAX_BYTES: int = 10 * 1024 * 1024
    LOG_FILE_BACKUP_COUNT: int = 10
    ENABLE_AUDIT_DB: bool = True
    LOGS_DATABASE_URL: str = f"sqlite:///{(CODIGO_DIR / 'data' / 'saas_logs.db').as_posix()}"

    # JWT (secretos compartidos con los servicios que verifican)
    WIDGET_JWT_SECRET: str = "dev_widget_jwt_secret_change_me_in_production_0001"
    ADMIN_JWT_SECRET: str = "dev_admin_jwt_secret_change_me_in_production_0002"
    JWT_ALGORITHM: str = "HS256"
    JWT_ISSUER: str = "saas-auth-service"
    WIDGET_TOKEN_AUDIENCE: str = "saas-widget"
    ADMIN_TOKEN_AUDIENCE: str = "saas-admin"
    SESSION_EXPIRES_SECONDS: int = 1800
    ADMIN_TOKEN_EXPIRES_SECONDS: int = 3600

    # Protección contra fuerza bruta en login de administradores
    ADMIN_MAX_FAILED_ATTEMPTS: int = 5
    ADMIN_LOCKOUT_MINUTES: int = 15

    # SUPERADMIN inicial (solo se crea si no existe ningún administrador)
    BOOTSTRAP_ADMIN_USERNAME: str = "superadmin"
    BOOTSTRAP_ADMIN_PASSWORD: Optional[str] = None

    # Datos de demostración (clientes SIGIRES / otra_empresa y sus tenants)
    SEED_DEMO_DATA: bool = True
    DEFAULT_WIDGET_API_KEY: str = "pk_live_sigires_8f9a2b1c3d4e5f6a"
    CLIENT_BUSQUEDA_URLS: Dict[str, str] = {
        "sigires": "http://localhost:8001",
        "default": "http://localhost:8001",
    }

    CORS_ORIGINS: List[str] = [
        "https://sigires.procex.co",
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ]

    def validate_production_safety(self) -> None:
        """Impide arrancar en producción con secretos por defecto."""
        if self.ENVIRONMENT.lower() != "production":
            return
        if self.WIDGET_JWT_SECRET in INSECURE_DEFAULT_SECRETS or self.ADMIN_JWT_SECRET in INSECURE_DEFAULT_SECRETS:
            raise RuntimeError("Configure WIDGET_JWT_SECRET y ADMIN_JWT_SECRET propios antes de desplegar en producción.")
        if self.WIDGET_JWT_SECRET == self.ADMIN_JWT_SECRET:
            raise RuntimeError("WIDGET_JWT_SECRET y ADMIN_JWT_SECRET deben ser distintos.")


settings = Settings()
