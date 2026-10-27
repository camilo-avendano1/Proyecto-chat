"""
Main FastAPI Application Entry Point for SaaS Core Back Central.
Developed by: Juan Camilo Avendaño, Fran Sneider Quincha, Adriana Moreno.
Follows Clean Architecture, modern lifespan context management, multi-client routing,
audit logging, and advanced error handling.
"""

from contextlib import asynccontextmanager
import logging
import time
from typing import Callable
import uuid

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from src.config import settings
from src.core.logging_system import request_id_ctx, setup_logging
from src.domain.exceptions import DomainException, SecurityException
from src.infrastructure.security.audit_logger import audit_logger
from src.routers.admin_logs_router import router as admin_logs_router
from src.routers.diagnostic_router import router as diagnostic_router
from src.routers.health_router import router as health_router
from src.routers.session_router import router as session_router

setup_logging(
    service=settings.SERVICE_NAME,
    level=settings.LOG_LEVEL,
    log_dir=settings.LOG_DIR,
    json_console=settings.LOG_JSON_CONSOLE,
    max_bytes=settings.LOG_FILE_MAX_BYTES,
    backup_count=settings.LOG_FILE_BACKUP_COUNT,
)
logger = logging.getLogger("back_chat")


class SecurityAuditMiddleware(BaseHTTPMiddleware):
    """
    Middleware that assigns a unique Request ID to each call,
    measures end-to-end latency, and audits HTTP interactions.
    """

    async def dispatch(self, request: Request, call_next: Callable):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id
        request_id_ctx.set(request_id)
        start_time = time.perf_counter()

        client_ip = request.client.host if request.client else "unknown"
        method = request.method
        path = request.url.path

        try:
            response = await call_next(request)
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            response.headers["X-Request-ID"] = request_id

            logger.info(
                f"[HTTP] {method} {path} | Status: {response.status_code} | "
                f"Latency: {duration_ms}ms | IP: {client_ip} | ReqId: {request_id}"
            )
            return response
        except Exception as exc:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            audit_logger.log_system_error(
                error_type="UNHANDLED_EXCEPTION",
                message=str(exc),
                request_id=request_id,
                exception_str=type(exc).__name__,
            )
            raise exc


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for application startup and shutdown."""
    logger.info("================================================================")
    logger.info(f"Iniciando {settings.APP_NAME} v{settings.APP_VERSION}")
    logger.info(f"Equipo de Desarrollo: {', '.join(settings.AUTHORS)}")
    logger.info(f"Ambiente: {settings.ENVIRONMENT}")
    logger.info(f"Proveedor LLM: {settings.LLM_PROVIDER} ({settings.LLM_BASE_URL})")
    logger.info(f"Modelo LLM: {settings.LLM_MODEL}")
    logger.info(f"Rutas de Búsqueda Clientes: {settings.CLIENT_BUSQUEDA_URLS}")
    logger.info("Sistema de Logs de Seguridad y Auditoría de Tokens: ACTIVO")
    logger.info("Guardrails y Fast-Path para Saludos / Fuera de Dominio: ACTIVO")
    logger.info("================================================================")
    yield
    logger.info("Cerrando SaaS Core Back Central...")
    from src.core.audit import audit_logger as persistent_audit_logger
    persistent_audit_logger.flush()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "Core Backend SaaS y Gateway de Diagnóstico en tiempo real. "
        "Desarrollado por Juan Camilo Avendaño, Fran Sneider Quincha y Adriana Moreno. "
        "Orquesta consultas para clientes empresariales (incluyendo la plataforma clínica SIGIRES / Procex Software S.A.S). "
        "Gestiona sesiones multi-cliente, sanitiza PII (Ley 1581 de 2012), enruta búsquedas RAG a las APIs correspondientes, "
        "aplica Guardrails de seguridad contra inyecciones y filtra consultas triviales para ahorro de tokens."
    ),
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Custom Security & Observability Middleware
app.add_middleware(SecurityAuditMiddleware)

# CORS Configuration for Web Widgets & Consoles
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS if "*" not in settings.CORS_ORIGINS else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*", "X-Request-ID"],
)


# Exception Handlers
@app.exception_handler(SecurityException)
async def security_exception_handler(request: Request, exc: SecurityException):
    """Handles security guardrail violations (Prompt Injection, Out of Domain, etc.)."""
    req_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    audit_logger.log_security_event(
        event_type="SECURITY_EXCEPTION_TRIGGERED",
        severity="HIGH",
        client_id="unknown",
        tenant_id="unknown",
        usuario="unknown",
        details={"error": str(exc), "type": exc.__class__.__name__},
        request_id=req_id,
    )
    return JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN,
        content={
            "detail": str(exc),
            "error_type": exc.__class__.__name__,
            "request_id": req_id,
        },
    )


@app.exception_handler(DomainException)
async def domain_exception_handler(request: Request, exc: DomainException):
    """Translates business domain exceptions to appropriate HTTP responses."""
    logger.warning(f"Domain exception encountered: {exc}")
    req_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "detail": str(exc),
            "error_type": exc.__class__.__name__,
            "request_id": req_id,
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Formats Pydantic request validation errors cleanly without exposing internals."""
    req_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    clean_errors = [
        {"field": ".".join(str(loc) for loc in err.get("loc", [])), "message": err.get("msg")}
        for err in exc.errors()
    ]
    logger.warning(f"Validation error on {request.url.path}: {clean_errors}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": "Error de validación en la estructura de la solicitud.",
            "errors": clean_errors,
            "request_id": req_id,
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Safe fallback for unexpected 500 errors to prevent credential leakage."""
    req_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    audit_logger.log_system_error(
        error_type="INTERNAL_SERVER_ERROR",
        message=str(exc),
        request_id=req_id,
        exception_str=type(exc).__name__,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "Ha ocurrido un error interno en el servidor. Por favor contacte a soporte con su Request ID.",
            "request_id": req_id,
        },
    )


# Include Routers
app.include_router(session_router)
app.include_router(diagnostic_router)
app.include_router(health_router)
app.include_router(admin_logs_router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.main:app", host=settings.HOST, port=settings.PORT, reload=settings.DEBUG)
