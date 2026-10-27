"""
Main FastAPI Application Entry Point for SaaS LLM Gateway.
Port: 8003
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
from src.core.logging_system import request_id_ctx, setup_logging
from src.dependencies import get_db_instance
from src.routers.admin_usage_router import router as admin_usage_router
from src.routers.internal_router import router as internal_router

logger = logging.getLogger("llm_gateway")


class SecurityAuditMiddleware(BaseHTTPMiddleware):
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
    logger.info(f"Proveedor LLM: {settings.LLM_PROVIDER} | URL: {settings.LLM_BASE_URL}")
    logger.info(f"Modelo Primario: {settings.LLM_MODEL}")
    logger.info("Inicializando esquemas de Base de Datos para Usage Ledger...")

    db_instance = get_db_instance()
    db_instance.create_all()

    logger.info("Usage Ledger inicializado correctamente.")
    logger.info("================================================================")
    yield
    logger.info("Cerrando SaaS LLM Gateway...")
    audit_logger.close()
    get_db_instance().dispose()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Microservicio Gateway de Modelos de Lenguaje e Ingesta de Consumo.",
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
            "detail": "Ha ocurrido un error interno en el LLM Gateway.",
            "request_id": req_id,
        },
    )


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
        "llm_provider": settings.LLM_PROVIDER,
        "llm_model": settings.LLM_MODEL,
        "llm_base_url": settings.LLM_BASE_URL,
    }


app.include_router(internal_router)
app.include_router(admin_usage_router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.main:app", host=settings.HOST, port=settings.PORT, reload=settings.DEBUG)
