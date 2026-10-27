"""
Main FastAPI Application Entry Point for SaaS Auth Service.
Port: 8002
Desarrollado por: Juan Camilo Avendaño, Fran Sneider Quincha, Adriana Moreno.
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
from src.core.audit import audit_logger
from src.core.exceptions import ServiceError
from src.core.logging_system import request_id_ctx, setup_logging
from src.db.seed import bootstrap_superadmin, seed_demo_data
from src.dependencies import get_db_instance
from src.routers.admin_router import router as admin_router
from src.routers.widget_router import router as widget_router

logger = logging.getLogger("auth_service")


class SecurityAuditMiddleware(BaseHTTPMiddleware):
    """
    Middleware que asigna un X-Request-ID a cada llamada,
    configura la variable de contexto para correlación de logs y mide latencia.
    """

    async def dispatch(self, request: Request, call_next: Callable):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id
        token = request_id_ctx.set(request_id)
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
        finally:
            request_id_ctx.reset(token)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for application startup and shutdown."""
    settings.validate_production_safety()

    setup_logging(
        service=settings.SERVICE_NAME,
        level=settings.LOG_LEVEL,
        log_dir=settings.LOG_DIR,
        json_console=settings.LOG_JSON_CONSOLE,
        max_bytes=settings.LOG_FILE_MAX_BYTES,
        backup_count=settings.LOG_FILE_BACKUP_COUNT,
    )

    logger.info("================================================================")
    logger.info(f"Iniciando {settings.APP_NAME} v{settings.APP_VERSION}")
    logger.info(f"Ambiente: {settings.ENVIRONMENT} | Puerto: {settings.PORT}")
    logger.info("Inicializando esquemas de Base de Datos...")

    db_instance = get_db_instance()
    db_instance.create_all()

    with next(db_instance.session()) as session:
        if settings.SEED_DEMO_DATA:
            seed_demo_data(session, settings)
        bootstrap_superadmin(session, settings)

    logger.info("Base de Datos y Administradores inicializados correctamente.")
    logger.info("================================================================")
    yield
    logger.info("Cerrando SaaS Auth Service...")
    audit_logger.close()
    get_db_instance().dispose()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Microservicio de autenticación de usuarios de widget y administradores.",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(SecurityAuditMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS if "*" not in settings.CORS_ORIGINS else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*", "X-Request-ID"],
)


# Exception Handlers
@app.exception_handler(ServiceError)
async def service_error_handler(request: Request, exc: ServiceError):
    req_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": exc.detail,
            "error_type": exc.__class__.__name__,
            "request_id": req_id,
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    req_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    clean_errors = [
        {"field": ".".join(str(loc) for loc in err.get("loc", [])), "message": err.get("msg")}
        for err in exc.errors()
    ]
    logger.warning(f"Error de validación en {request.url.path}: {clean_errors}")
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
            "detail": "Ha ocurrido un error interno en el servidor de autenticación.",
            "request_id": req_id,
        },
    )


# Health & Status endpoints
@app.get("/health", status_code=status.HTTP_200_OK, tags=["Health"])
async def health_check():
    return {"status": "ok", "service": settings.SERVICE_NAME}


@app.get("/api/v1/status", status_code=status.HTTP_200_OK, tags=["Health"])
async def service_status():
    return {
        "status": "healthy",
        "service": settings.SERVICE_NAME,
        "app_name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
    }


# Include Routers
app.include_router(widget_router)
app.include_router(admin_router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.main:app", host=settings.HOST, port=settings.PORT, reload=settings.DEBUG)
