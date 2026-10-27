"""
Instancia de auditoría del Back-Chat Service.
Usa el módulo común logging_system con la base central de logs.
Desarrollado por: Juan Camilo Avendaño, Fran Sneider Quincha, Adriana Moreno.
"""

import os
os.environ["DISABLE_SQLALCHEMY_CEXT"] = "1"

from typing import Optional

from src.config import settings
from src.core.logging_system import AuditLogger, AuditLogStore


def _build_store() -> Optional[AuditLogStore]:
    if not settings.ENABLE_AUDIT_DB:
        return None
    return AuditLogStore(settings.LOGS_DATABASE_URL)


audit_logger = AuditLogger(service=settings.SERVICE_NAME, store_factory=_build_store)
