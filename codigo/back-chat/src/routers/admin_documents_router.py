"""
Router for Administrator Knowledge Base & Vector Documents Management (Flujo 3).
Protected by get_current_admin with strict multi-organization & RBAC isolation.
Uses pure-JSON payloads (content_base64 / content_text) and stdlib parsers.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
from pathlib import Path
import re
from typing import Any, Dict, List, Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from src.config import settings
from src.infrastructure.repositories.document_repo import get_document_repository
from src.infrastructure.security.audit_logger import audit_logger
from src.infrastructure.security.jwt_handler import get_current_admin
from src.operations.document_ingestion import (
    ALLOWED_EXTENSIONS,
    chunk_text,
    extract_text_from_bytes,
    notify_delete_to_busqueda,
    sync_document_to_busqueda,
)

router = APIRouter(
    prefix="/api/v1/admin/documents",
    tags=["Admin Knowledge & Vector Documents"],
)

_ALLOWED_SCOPES = ("SITE", "ORGANIZATION", "GLOBAL")


def _apply_role_scope(admin: Dict[str, Any], org_id: Optional[str]) -> Optional[str]:
    """
    Enforces organization isolation:
    - GLOBAL_ADMIN can view/filter any org_id or all.
    - ORG_ADMIN is strictly locked to its own org_id.
    """
    role = admin.get("role", "ORG_ADMIN")
    if role == "GLOBAL_ADMIN":
        return org_id
    admin_org = admin.get("org_id")
    if not admin_org:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="El token de administrador no tiene org_id asociado.",
        )
    return admin_org


def _enforce_doc_ownership(admin: Dict[str, Any], doc: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if doc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Documento no encontrado.",
        )
    role = admin.get("role", "ORG_ADMIN")
    if role != "GLOBAL_ADMIN":
        if doc.get("scope") == "GLOBAL" or doc.get("org_id") != admin.get("org_id"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tiene permisos para acceder o modificar documentos globales o de otra organización.",
            )
    return doc


class DocumentUploadRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=255, description="Título descriptivo del documento")
    filename: str = Field(..., min_length=1, max_length=255, description="Nombre del archivo con extensión")
    scope: str = Field(..., description="Alcance jerárquico: SITE, ORGANIZATION o GLOBAL")
    org_id: Optional[str] = Field(default=None, description="ID de la organización")
    site_id: Optional[str] = Field(default=None, description="ID de la sede (obligatorio para SITE)")
    content_base64: Optional[str] = Field(default=None, description="Contenido del archivo en Base64")
    content_text: Optional[str] = Field(default=None, description="Contenido textual directo (alternativa a Base64)")
    tags: Optional[List[str]] = Field(default_factory=list, description="Etiquetas opcionales de clasificación")


@router.get(
    "",
    summary="Listar documentos de conocimiento",
    description="Lista documentos indexados con filtros por organización, sede, alcance y búsqueda textual.",
)
async def list_documents(
    org_id: Optional[str] = Query(None, description="Filtrar por Organización"),
    site_id: Optional[str] = Query(None, description="Filtrar por Sede"),
    scope: Optional[str] = Query(None, description="Filtrar por alcance: SITE, ORGANIZATION o GLOBAL"),
    search: Optional[str] = Query(None, description="Búsqueda parcial en título o nombre de archivo"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    admin: Dict[str, Any] = Depends(get_current_admin),
) -> Dict[str, Any]:
    scoped_org = _apply_role_scope(admin, org_id)
    repo = get_document_repository()
    result = repo.list_documents(
        org_id=scoped_org,
        site_id=site_id,
        scope=scope,
        search=search,
        limit=limit,
        offset=offset,
    )
    result["org_id_scoped"] = scoped_org
    return result


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Cargar e indexar documento de conocimiento",
    description=(
        "Extrae texto en Python puro, valida deduplicación SHA-256, divide en fragmentos, "
        "almacena localmente y sincroniza con el servicio back-busqueda de la organización."
    ),
)
async def upload_document(
    body: DocumentUploadRequest,
    admin: Dict[str, Any] = Depends(get_current_admin),
):
    title = body.title.strip()
    filename = body.filename.strip()
    if not title or not filename:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Los campos 'title' y 'filename' no pueden estar vacíos.",
        )

    scope_upper = body.scope.strip().upper()
    if scope_upper not in _ALLOWED_SCOPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Alcance inválido '{body.scope}'. Valores permitidos: {', '.join(_ALLOWED_SCOPES)}.",
        )

    role = admin.get("role", "ORG_ADMIN")
    admin_org = (admin.get("org_id") or "").strip() or None
    req_org = (body.org_id or "").strip() or None

    if role != "GLOBAL_ADMIN":
        if scope_upper == "GLOBAL":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Solo GLOBAL_ADMIN puede cargar documentos con alcance GLOBAL.",
            )
        if req_org and req_org != admin_org:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tiene permisos para cargar documentos en otra organización.",
            )
        if not admin_org:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="El token de administrador no tiene org_id asociado.",
            )
        effective_org = admin_org
    else:
        if scope_upper in ("SITE", "ORGANIZATION") and not req_org:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"El campo 'org_id' es obligatorio para documentos con alcance {scope_upper}.",
            )
        effective_org = req_org or "global"

    effective_site = (body.site_id or "").strip() or None
    if scope_upper == "SITE" and not effective_site:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="El campo 'site_id' es obligatorio cuando scope='SITE'.",
        )
    if scope_upper != "SITE":
        effective_site = None

    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Extensión '{ext or '(sin extensión)'}' no soportada. Permitidas: {', '.join(sorted(ALLOWED_EXTENSIONS))}.",
        )

    has_b64 = bool(body.content_base64 and body.content_base64.strip())
    has_text = bool(body.content_text and body.content_text.strip())
    if not has_b64 and not has_text:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Debe enviar 'content_base64' o 'content_text' con contenido válido.",
        )

    if has_b64:
        b64_data = body.content_base64.strip()
        if b64_data.startswith("data:") and ";base64," in b64_data:
            b64_data = b64_data.split(";base64,", 1)[1]
        b64_data = re.sub(r"\s+", "", b64_data)
        if len(b64_data) > ((settings.MAX_DOCUMENT_SIZE_BYTES * 4) // 3 + 4096):
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail=f"El documento excede el límite máximo permitido de {settings.MAX_DOCUMENT_SIZE_BYTES} bytes.",
            )
        try:
            raw_bytes = base64.b64decode(b64_data, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="El campo 'content_base64' no contiene Base64 válido.",
            ) from exc
    else:
        raw_bytes = body.content_text.encode("utf-8")

    if not raw_bytes:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="El archivo o texto enviado está vacío.",
        )

    if len(raw_bytes) > settings.MAX_DOCUMENT_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"El documento ({len(raw_bytes)} bytes) excede el límite máximo de {settings.MAX_DOCUMENT_SIZE_BYTES} bytes.",
        )

    content_hash = hashlib.sha256(raw_bytes).hexdigest()
    repo = get_document_repository()
    existing = repo.find_by_hash(
        org_id=effective_org,
        site_id=effective_site,
        scope=scope_upper,
        content_hash=content_hash,
    )
    if existing is not None:
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "deduplicated": True,
                "message": "Documento idéntico ya indexado (SHA-256).",
                "document": existing,
            },
        )

    try:
        extracted_text = extract_text_from_bytes(
            filename=filename,
            raw_bytes=raw_bytes,
            content_text=body.content_text,
            title=title,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc

    if not extracted_text or not extracted_text.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="No se pudo extraer contenido textual del documento.",
        )

    chunks = chunk_text(extracted_text, title=title)
    if not chunks:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="No se pudieron generar fragmentos de texto indexables.",
        )

    clean_tags = [str(tag).strip() for tag in (body.tags or []) if str(tag).strip()]
    doc_id = str(uuid.uuid4())
    doc_data = {
        "doc_id": doc_id,
        "org_id": effective_org,
        "site_id": effective_site,
        "scope": scope_upper,
        "title": title,
        "filename": filename,
        "file_type": ext.lstrip(".").upper(),
        "file_size_bytes": len(raw_bytes),
        "content_hash": content_hash,
        "chunk_count": len(chunks),
        "status": "READY",
        "vector_sync_status": "LOCAL_INDEXED",
        "tags": clean_tags,
        "uploaded_by": admin.get("username") or admin.get("email") or "admin",
    }

    created_doc = repo.create_document_with_chunks(doc_data, chunks)
    sync_status, sync_detail = await sync_document_to_busqueda(created_doc, chunks)
    updated_doc = repo.update_sync_status(doc_id, sync_status, sync_detail) or created_doc

    audit_logger.log_security_event(
        event_type="DOCUMENT_UPLOADED",
        severity="LOW",
        org_id=effective_org,
        site_id=effective_site or "all",
        usuario=admin.get("username", "admin"),
        details={
            "doc_id": doc_id,
            "title": title,
            "filename": filename,
            "scope": scope_upper,
            "chunk_count": len(chunks),
            "vector_sync_status": sync_status,
        },
    )

    return {
        "deduplicated": False,
        "message": "Documento procesado e indexado correctamente.",
        "document": updated_doc,
    }


@router.get(
    "/{doc_id}/chunks",
    summary="Obtener fragmentos (chunks) de un documento",
    description="Retorna los fragmentos de texto indexados para un documento específico.",
)
async def get_document_chunks(
    doc_id: str,
    admin: Dict[str, Any] = Depends(get_current_admin),
) -> Dict[str, Any]:
    repo = get_document_repository()
    doc = _enforce_doc_ownership(admin, repo.get_document(doc_id))
    chunks = repo.get_chunks(doc_id)
    return {
        "doc_id": doc_id,
        "document": doc,
        "chunks": chunks,
    }


@router.post(
    "/{doc_id}/sync",
    summary="Re-sincronizar documento con back-busqueda",
    description="Reintenta la sincronización vectorial de los fragmentos de un documento hacia back-busqueda.",
)
async def sync_document(
    doc_id: str,
    admin: Dict[str, Any] = Depends(get_current_admin),
) -> Dict[str, Any]:
    repo = get_document_repository()
    doc = _enforce_doc_ownership(admin, repo.get_document(doc_id))
    chunks = repo.get_chunks(doc_id)
    sync_status, sync_detail = await sync_document_to_busqueda(doc, chunks)
    updated_doc = repo.update_sync_status(doc_id, sync_status, sync_detail)
    return updated_doc or doc


@router.delete(
    "/{doc_id}",
    summary="Eliminar documento de conocimiento",
    description="Elimina el documento y sus fragmentos localmente y notifica de forma best-effort a back-busqueda.",
)
async def delete_document(
    doc_id: str,
    admin: Dict[str, Any] = Depends(get_current_admin),
) -> Dict[str, Any]:
    repo = get_document_repository()
    doc = _enforce_doc_ownership(admin, repo.get_document(doc_id))

    deleted = repo.delete_document(doc_id)
    await notify_delete_to_busqueda(doc_id=doc_id, org_id=doc["org_id"])

    audit_logger.log_security_event(
        event_type="DOCUMENT_DELETED",
        severity="LOW",
        org_id=doc["org_id"],
        site_id=doc.get("site_id") or "all",
        usuario=admin.get("username", "admin"),
        details={
            "doc_id": doc_id,
            "title": doc["title"],
            "scope": doc["scope"],
        },
    )

    return {
        "deleted": deleted,
        "doc_id": doc_id,
        "message": "Documento eliminado correctamente.",
    }
