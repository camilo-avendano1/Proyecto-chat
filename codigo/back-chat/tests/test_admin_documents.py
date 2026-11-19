"""
Tests for Flujo 3: Admin Knowledge & Vector Documents endpoints,
stdlib document extraction (.txt, .csv, .docx, .xlsx, .pdf), SHA-256 deduplication,
RBAC isolation, remote back-busqueda sync, E2E RAG site isolation, usage proxy params,
and automatic SQLite legacy schema migration.
"""

from __future__ import annotations

import base64
import io
import os
import sqlite3
from unittest.mock import AsyncMock, MagicMock, patch
import zipfile
import zlib

os.environ["DISABLE_SQLALCHEMY_CEXT"] = "1"

import httpx
import jwt
import pytest
from fastapi.testclient import TestClient

from src.config import settings
from src.infrastructure.repositories.document_repo import (
    KnowledgeDocumentRepository,
    reset_document_repository,
)
from src.infrastructure.security.jwt_handler import default_jwt_handler


@pytest.fixture(autouse=True)
def _isolated_doc_repo(tmp_path):
    db_url = f"sqlite:///{(tmp_path / 'test_knowledge_docs.db').as_posix()}"
    reset_document_repository(db_url)
    yield
    reset_document_repository(settings.KNOWLEDGE_DATABASE_URL)


def _generate_admin_token(
    role: str = "GLOBAL_ADMIN",
    org_id: str | None = "sigires",
    username: str = "admin_docs",
) -> str:
    payload = {
        "sub": f"admin_{username}",
        "username": username,
        "email": f"{username}@saas.com",
        "role": role,
        "org_id": org_id,
        "aud": settings.ADMIN_TOKEN_AUDIENCE,
        "typ": "admin",
    }
    return jwt.encode(payload, settings.ADMIN_JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def _build_in_memory_docx(paragraphs: list[str]) -> bytes:
    p_xml = "".join(
        f"<w:p><w:r><w:t>{text}</w:t></w:r></w:p>"
        for text in paragraphs
    )
    document_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{p_xml}</w:body>"
        "</w:document>"
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("word/document.xml", document_xml.encode("utf-8"))
    return buf.getvalue()


def _build_in_memory_xlsx() -> bytes:
    shared_strings_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="2" uniqueCount="2">'
        "<si><t>Servicio</t></si>"
        "<si><t>SLA_Horas</t></si>"
        "</sst>"
    )
    sheet1_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        "<sheetData>"
        '<row r="1">'
        '<c r="A1" t="s"><v>0</v></c>'
        '<c r="B1" t="s"><v>1</v></c>'
        "</row>"
        '<row r="2">'
        '<c r="A2" t="inlineStr"><is><t>Soporte Prioritario</t></is></c>'
        '<c r="B2"><v>4</v></c>'
        "</row>"
        "</sheetData>"
        "</worksheet>"
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("xl/sharedStrings.xml", shared_strings_xml.encode("utf-8"))
        zf.writestr("xl/worksheets/sheet1.xml", sheet1_xml.encode("utf-8"))
    return buf.getvalue()


def _build_in_memory_pdf(text_line: str) -> bytes:
    content_stream = (
        f"BT /F1 12 Tf 72 720 Td ({text_line}) Tj "
        "0 -18 Td [(Garantia ) -120 (Extendida)] TJ ET"
    ).encode("latin-1")
    compressed = zlib.compress(content_stream)
    return (
        b"%PDF-1.4\n"
        b"1 0 obj << /Type /Catalog >> endobj\n"
        b"2 0 obj << /Length " + str(len(compressed)).encode("ascii") + b" /Filter /FlateDecode >>\n"
        b"stream\n" + compressed + b"\nendstream\nendobj\n%%EOF\n"
    )


def test_documents_require_admin_auth(client: TestClient):
    assert client.get("/api/v1/admin/documents").status_code == 401
    assert client.post("/api/v1/admin/documents", json={}).status_code == 401


def test_upload_txt_csv_docx_xlsx_pdf_and_content_text(client: TestClient):
    token = _generate_admin_token(role="GLOBAL_ADMIN")
    headers = {"Authorization": f"Bearer {token}"}

    with patch("src.operations.document_ingestion.httpx.AsyncClient.post", side_effect=httpx.ConnectError("offline")):
        # 1. TXT via content_base64 (with data URI prefix)
        txt_raw = "Manual operativo de radicación electrónica y control de calidad.".encode("utf-8")
        txt_b64 = "data:text/plain;base64," + base64.b64encode(txt_raw).decode("ascii")
        resp_txt = client.post(
            "/api/v1/admin/documents",
            headers=headers,
            json={
                "title": "Manual Radicación TXT",
                "filename": "manual_radicacion.txt",
                "scope": "ORGANIZATION",
                "org_id": "sigires",
                "content_base64": txt_b64,
                "tags": ["manual", "radicacion"],
            },
        )
        assert resp_txt.status_code == 201
        txt_data = resp_txt.json()
        assert txt_data["deduplicated"] is False
        assert txt_data["document"]["file_type"] == "TXT"
        assert txt_data["document"]["chunk_count"] >= 1
        assert txt_data["document"]["vector_sync_status"] == "LOCAL_INDEXED"

        # 2. CSV via content_base64
        csv_raw = "codigo,descripcion,accion\nE001,Fecha futura invalida,Corregir fecha\n".encode("utf-8")
        resp_csv = client.post(
            "/api/v1/admin/documents",
            headers=headers,
            json={
                "title": "Catálogo Errores CSV",
                "filename": "errores.csv",
                "scope": "SITE",
                "org_id": "sigires",
                "site_id": "eps_sura",
                "content_base64": base64.b64encode(csv_raw).decode("ascii"),
            },
        )
        assert resp_csv.status_code == 201
        csv_doc_id = resp_csv.json()["document"]["doc_id"]
        chunks_csv = client.get(f"/api/v1/admin/documents/{csv_doc_id}/chunks", headers=headers)
        assert chunks_csv.status_code == 200
        assert "codigo: E001" in chunks_csv.json()["chunks"][0]["content"]
        assert "accion: Corregir fecha" in chunks_csv.json()["chunks"][0]["content"]

        # 3. DOCX built in-memory with zipfile
        docx_bytes = _build_in_memory_docx([
            "Política Corporativa de Copias de Seguridad",
            "Los respaldos diarios se conservan durante 90 días en bóveda cifrada.",
        ])
        resp_docx = client.post(
            "/api/v1/admin/documents",
            headers=headers,
            json={
                "title": "Política Backups DOCX",
                "filename": "backups.docx",
                "scope": "ORGANIZATION",
                "org_id": "sigires",
                "content_base64": base64.b64encode(docx_bytes).decode("ascii"),
            },
        )
        assert resp_docx.status_code == 201
        docx_doc_id = resp_docx.json()["document"]["doc_id"]
        chunks_docx = client.get(f"/api/v1/admin/documents/{docx_doc_id}/chunks", headers=headers)
        assert "bóveda cifrada" in chunks_docx.json()["chunks"][0]["content"]

        # 4. XLSX built in-memory with zipfile (sharedStrings + inlineStr)
        xlsx_bytes = _build_in_memory_xlsx()
        resp_xlsx = client.post(
            "/api/v1/admin/documents",
            headers=headers,
            json={
                "title": "Matriz SLA XLSX",
                "filename": "matriz_sla.xlsx",
                "scope": "ORGANIZATION",
                "org_id": "sigires",
                "content_base64": base64.b64encode(xlsx_bytes).decode("ascii"),
            },
        )
        assert resp_xlsx.status_code == 201
        xlsx_doc_id = resp_xlsx.json()["document"]["doc_id"]
        chunks_xlsx = client.get(f"/api/v1/admin/documents/{xlsx_doc_id}/chunks", headers=headers)
        xlsx_content = chunks_xlsx.json()["chunks"][0]["content"]
        assert "Servicio | SLA_Horas" in xlsx_content
        assert "Soporte Prioritario | 4" in xlsx_content

        # 5. PDF with FlateDecode Tj/TJ + binary PDF fallback
        pdf_bytes = _build_in_memory_pdf("Reglamento de Mesa de Ayuda Nivel 2")
        resp_pdf = client.post(
            "/api/v1/admin/documents",
            headers=headers,
            json={
                "title": "Reglamento PDF",
                "filename": "reglamento.pdf",
                "scope": "GLOBAL",
                "content_base64": base64.b64encode(pdf_bytes).decode("ascii"),
            },
        )
        assert resp_pdf.status_code == 201
        pdf_doc_id = resp_pdf.json()["document"]["doc_id"]
        chunks_pdf = client.get(f"/api/v1/admin/documents/{pdf_doc_id}/chunks", headers=headers)
        pdf_content = chunks_pdf.json()["chunks"][0]["content"]
        assert "Reglamento de Mesa de Ayuda Nivel 2" in pdf_content
        assert "Garantia Extendida" in pdf_content

        binary_pdf = b"%PDF-1.4\n\x80\x81\x82\x83\x84\x85%%EOF"
        resp_bin_pdf = client.post(
            "/api/v1/admin/documents",
            headers=headers,
            json={
                "title": "Escaneado Binario",
                "filename": "escaneado.pdf",
                "scope": "GLOBAL",
                "content_base64": base64.b64encode(binary_pdf).decode("ascii"),
            },
        )
        assert resp_bin_pdf.status_code == 201

        # 6. Direct content_text upload
        resp_direct = client.post(
            "/api/v1/admin/documents",
            headers=headers,
            json={
                "title": "Guía Directa",
                "filename": "guia.md",
                "scope": "SITE",
                "org_id": "otra_empresa",
                "site_id": "sede_norte",
                "content_text": "# Guía\n\nProcedimiento directo de aprobación en portal.",
            },
        )
        assert resp_direct.status_code == 201

        # List with counts_by_site
        list_resp = client.get("/api/v1/admin/documents", headers=headers)
        assert list_resp.status_code == 200
        list_data = list_resp.json()
        assert list_data["total"] == 7
        assert list_data["counts_by_site"]["eps_sura"] == 1
        assert list_data["counts_by_site"]["sede_norte"] == 1


def test_sha256_deduplication_returns_200(client: TestClient):
    token = _generate_admin_token(role="GLOBAL_ADMIN")
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "title": "Guía Deduplicada",
        "filename": "guia.txt",
        "scope": "ORGANIZATION",
        "org_id": "otra_empresa",
        "content_text": "Contenido idéntico para prueba de hash SHA-256.",
    }

    with patch("src.operations.document_ingestion.httpx.AsyncClient.post", side_effect=httpx.ConnectError("offline")):
        first = client.post("/api/v1/admin/documents", headers=headers, json=payload)
        assert first.status_code == 201
        assert first.json()["deduplicated"] is False
        doc_id = first.json()["document"]["doc_id"]

        second = client.post("/api/v1/admin/documents", headers=headers, json=payload)
        assert second.status_code == 200
        sec_data = second.json()
        assert sec_data["deduplicated"] is True
        assert "SHA-256" in sec_data["message"]
        assert sec_data["document"]["doc_id"] == doc_id


def test_upload_validation_and_size_limit(client: TestClient):
    token = _generate_admin_token(role="GLOBAL_ADMIN")
    headers = {"Authorization": f"Bearer {token}"}

    # Unsupported extension
    resp_ext = client.post(
        "/api/v1/admin/documents",
        headers=headers,
        json={
            "title": "Binario",
            "filename": "malware.exe",
            "scope": "ORGANIZATION",
            "org_id": "sigires",
            "content_text": "hello",
        },
    )
    assert resp_ext.status_code == 422

    # Missing site_id for SITE scope
    resp_site = client.post(
        "/api/v1/admin/documents",
        headers=headers,
        json={
            "title": "Sin Sede",
            "filename": "doc.txt",
            "scope": "SITE",
            "org_id": "sigires",
            "content_text": "hello",
        },
    )
    assert resp_site.status_code == 422

    # Exceeds MAX_DOCUMENT_SIZE_BYTES -> 413
    with patch.object(settings, "MAX_DOCUMENT_SIZE_BYTES", 20):
        resp_big = client.post(
            "/api/v1/admin/documents",
            headers=headers,
            json={
                "title": "Archivo Grande",
                "filename": "grande.txt",
                "scope": "ORGANIZATION",
                "org_id": "sigires",
                "content_text": "Este texto supera claramente el limite de 20 bytes configurado.",
            },
        )
        assert resp_big.status_code == 413


def test_rbac_isolation_for_org_admin(client: TestClient):
    sigires_admin = _generate_admin_token(role="ORG_ADMIN", org_id="sigires", username="admin_sigires")
    other_admin = _generate_admin_token(role="ORG_ADMIN", org_id="otra_empresa", username="admin_otra")

    with patch("src.operations.document_ingestion.httpx.AsyncClient.post", side_effect=httpx.ConnectError("offline")):
        # ORG_ADMIN cannot upload GLOBAL
        resp_global = client.post(
            "/api/v1/admin/documents",
            headers={"Authorization": f"Bearer {sigires_admin}"},
            json={
                "title": "Global Prohibido",
                "filename": "global.txt",
                "scope": "GLOBAL",
                "content_text": "No permitido para org admin.",
            },
        )
        assert resp_global.status_code == 403

        # ORG_ADMIN cannot upload to another org
        resp_cross = client.post(
            "/api/v1/admin/documents",
            headers={"Authorization": f"Bearer {sigires_admin}"},
            json={
                "title": "Cross Org",
                "filename": "cross.txt",
                "scope": "ORGANIZATION",
                "org_id": "otra_empresa",
                "content_text": "Intento de cruce.",
            },
        )
        assert resp_cross.status_code == 403

        # sigires admin uploads valid ORGANIZATION doc (omitting org_id -> forced to sigires)
        resp_ok = client.post(
            "/api/v1/admin/documents",
            headers={"Authorization": f"Bearer {sigires_admin}"},
            json={
                "title": "Manual Privado SIGIRES",
                "filename": "manual_sigires.txt",
                "scope": "ORGANIZATION",
                "content_text": "Procedimiento confidencial exclusivo de SIGIRES.",
            },
        )
        assert resp_ok.status_code == 201
        sigires_doc_id = resp_ok.json()["document"]["doc_id"]
        assert resp_ok.json()["document"]["org_id"] == "sigires"

    # otra_empresa admin cannot list sigires docs even passing ?org_id=sigires
    list_other = client.get(
        "/api/v1/admin/documents?org_id=sigires",
        headers={"Authorization": f"Bearer {other_admin}"},
    )
    assert list_other.status_code == 200
    assert list_other.json()["org_id_scoped"] == "otra_empresa"
    assert list_other.json()["total"] == 0

    # otra_empresa admin gets 403 on chunks / sync / delete of sigires doc
    assert client.get(
        f"/api/v1/admin/documents/{sigires_doc_id}/chunks",
        headers={"Authorization": f"Bearer {other_admin}"},
    ).status_code == 403

    assert client.post(
        f"/api/v1/admin/documents/{sigires_doc_id}/sync",
        headers={"Authorization": f"Bearer {other_admin}"},
    ).status_code == 403

    assert client.delete(
        f"/api/v1/admin/documents/{sigires_doc_id}",
        headers={"Authorization": f"Bearer {other_admin}"},
    ).status_code == 403

    assert client.get(
        "/api/v1/admin/documents/nonexistent-id/chunks",
        headers={"Authorization": f"Bearer {other_admin}"},
    ).status_code == 404


def test_remote_busqueda_sync_and_retry_and_delete(client: TestClient):
    token = _generate_admin_token(role="GLOBAL_ADMIN")
    headers = {"Authorization": f"Bearer {token}"}

    mock_ok_resp = MagicMock()
    mock_ok_resp.status_code = 200
    mock_post_ok = AsyncMock(return_value=mock_ok_resp)

    # 1. Remote back-busqueda online -> SYNCED_REMOTE
    with patch("src.operations.document_ingestion.httpx.AsyncClient.post", new=mock_post_ok):
        resp_online = client.post(
            "/api/v1/admin/documents",
            headers=headers,
            json={
                "title": "Doc Online Sync",
                "filename": "online.txt",
                "scope": "ORGANIZATION",
                "org_id": "otra_empresa",
                "content_text": "Documento sincronizado remotamente.",
            },
        )
        assert resp_online.status_code == 201
        assert resp_online.json()["document"]["vector_sync_status"] == "SYNCED_REMOTE"
        assert mock_post_ok.await_count == 1
        sent_headers = mock_post_ok.call_args.kwargs["headers"]
        assert sent_headers["X-Internal-Key"] == settings.BUSQUEDA_SERVICE_KEY

    # 2. Offline -> LOCAL_INDEXED, then /sync retry -> SYNCED_REMOTE
    with patch("src.operations.document_ingestion.httpx.AsyncClient.post", side_effect=httpx.ConnectError("offline")):
        resp_offline = client.post(
            "/api/v1/admin/documents",
            headers=headers,
            json={
                "title": "Doc Offline Retry",
                "filename": "offline.txt",
                "scope": "ORGANIZATION",
                "org_id": "otra_empresa",
                "content_text": "Documento indexado localmente y luego re-sincronizado.",
            },
        )
        assert resp_offline.status_code == 201
        offline_doc = resp_offline.json()["document"]
        assert offline_doc["vector_sync_status"] == "LOCAL_INDEXED"
        doc_id = offline_doc["doc_id"]

    mock_post_retry = AsyncMock(return_value=mock_ok_resp)
    with patch("src.operations.document_ingestion.httpx.AsyncClient.post", new=mock_post_retry):
        retry_resp = client.post(f"/api/v1/admin/documents/{doc_id}/sync", headers=headers)
        assert retry_resp.status_code == 200
        assert retry_resp.json()["vector_sync_status"] == "SYNCED_REMOTE"
        assert mock_post_retry.await_count == 1

    # 3. Delete doc -> deletes locally & calls remote delete best-effort
    mock_delete = AsyncMock(return_value=mock_ok_resp)
    with patch("src.operations.document_ingestion.httpx.AsyncClient.delete", new=mock_delete):
        del_resp = client.delete(f"/api/v1/admin/documents/{doc_id}", headers=headers)
        assert del_resp.status_code == 200
        assert del_resp.json()["deleted"] is True
        assert mock_delete.await_count == 1

    assert client.get(f"/api/v1/admin/documents/{doc_id}/chunks", headers=headers).status_code == 404


def test_e2e_rag_site_isolation_in_chat_query(client: TestClient):
    admin_token = _generate_admin_token(role="GLOBAL_ADMIN")

    # Upload policy doc strictly for site-a of otra_empresa
    with patch("src.operations.document_ingestion.httpx.AsyncClient.post", side_effect=httpx.ConnectError("offline")):
        upload_resp = client.post(
            "/api/v1/admin/documents",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "title": "Política VIP de Devoluciones Sede A",
                "filename": "devoluciones_vip.md",
                "scope": "SITE",
                "org_id": "otra_empresa",
                "site_id": "site-a",
                "content_text": (
                    "# Política VIP\n\n"
                    "La politica de devoluciones vip 45 dias aplica exclusivamente para usuarios "
                    "corporativos autorizados de site-a con factura original."
                ),
            },
        )
        assert upload_resp.status_code == 201

    token_site_a = default_jwt_handler.create_session_token({
        "sub": "user-a",
        "org_id": "otra_empresa",
        "org_name": "Otra Empresa",
        "site_id": "site-a",
        "site_name": "Sede A",
    })
    token_site_b = default_jwt_handler.create_session_token({
        "sub": "user-b",
        "org_id": "otra_empresa",
        "org_name": "Otra Empresa",
        "site_id": "site-b",
        "site_name": "Sede B",
    })

    query_payload = {"query": "¿Cuál es la politica de devoluciones vip 45 dias?"}

    with patch("src.infrastructure.external.busqueda_client.httpx.AsyncClient.post", side_effect=httpx.ConnectError("offline")):
        # Site A receives its uploaded policy doc
        resp_a = client.post(
            "/api/v1/chat/query",
            headers={"Authorization": f"Bearer {token_site_a}"},
            json=query_payload,
        )
        assert resp_a.status_code == 200
        data_a = resp_a.json()
        assert any(s["document_title"] == "Política VIP de Devoluciones Sede A" and s["scope"] == "SITE" for s in data_a["sources"])
        assert "Política VIP de Devoluciones Sede A" in data_a["response"]
        assert "factura original" in data_a["response"]
        assert "45 dias" in data_a["response"]

        # Site B MUST NOT receive Site A's document
        resp_b = client.post(
            "/api/v1/chat/query",
            headers={"Authorization": f"Bearer {token_site_b}"},
            json=query_payload,
        )
        assert resp_b.status_code == 200
        data_b = resp_b.json()
        assert all(s["document_title"] != "Política VIP de Devoluciones Sede A" for s in data_b["sources"])
        assert "Política VIP de Devoluciones Sede A" not in data_b["response"]
        assert "factura original" not in data_b["response"]
        assert "usuarios corporativos autorizados" not in data_b["response"]


def test_admin_usage_proxy_forwards_date_filters(client: TestClient):
    token = _generate_admin_token(role="GLOBAL_ADMIN")
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"total_requests": 5}
    mock_get = AsyncMock(return_value=mock_resp)

    with patch("src.routers.admin_logs_router.httpx.AsyncClient.get", new=mock_get):
        resp = client.get(
            "/api/v1/admin/usage/by-site?days=14&date_from=2026-11-01&date_to=2026-11-15&site_id=sede-1",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json() == {"total_requests": 5}
        forwarded_params = mock_get.call_args.kwargs["params"]
        assert forwarded_params["days"] == 14
        assert forwarded_params["date_from"] == "2026-11-01"
        assert forwarded_params["date_to"] == "2026-11-15"
        assert forwarded_params["site_id"] == "sede-1"
        forwarded_headers = mock_get.call_args.kwargs["headers"]
        assert "X-Admin-Org-Id" in forwarded_headers


def test_sqlite_legacy_knowledge_migration(tmp_path):
    legacy_db = tmp_path / "legacy_knowledge.db"
    conn = sqlite3.connect(legacy_db)
    try:
        conn.executescript(
            """
            CREATE TABLE knowledge_documents (
                doc_id VARCHAR(36) PRIMARY KEY,
                client_id VARCHAR(100) NOT NULL,
                tenant_id VARCHAR(100),
                scope VARCHAR(20) NOT NULL,
                title VARCHAR(255) NOT NULL,
                filename VARCHAR(255) NOT NULL,
                file_type VARCHAR(20) NOT NULL,
                file_size_bytes INTEGER NOT NULL,
                content_hash VARCHAR(64) NOT NULL,
                chunk_count INTEGER NOT NULL DEFAULT 0,
                status VARCHAR(20) NOT NULL DEFAULT 'READY',
                vector_sync_status VARCHAR(30) NOT NULL DEFAULT 'LOCAL_INDEXED',
                vector_sync_detail TEXT,
                tags JSON NOT NULL,
                uploaded_by VARCHAR(100),
                created_at DATETIME NOT NULL
            );
            CREATE TABLE knowledge_chunks (
                chunk_id VARCHAR(36) PRIMARY KEY,
                doc_id VARCHAR(36) NOT NULL REFERENCES knowledge_documents(doc_id) ON DELETE CASCADE,
                client_id VARCHAR(100) NOT NULL,
                tenant_id VARCHAR(100),
                scope VARCHAR(20) NOT NULL,
                chunk_index INTEGER NOT NULL,
                section VARCHAR(255) NOT NULL,
                content TEXT NOT NULL,
                char_count INTEGER NOT NULL,
                created_at DATETIME NOT NULL
            );
            INSERT INTO knowledge_documents VALUES (
                'doc-leg-1', 'talleres_sur', 'sede-taller-01', 'TENANT',
                'Manual Cambio Aceite Legacy', 'aceite.txt', 'TXT', 120, 'hash1', 1,
                'READY', 'LOCAL_INDEXED', NULL, '[]', 'admin', '2026-11-01 10:00:00'
            );
            INSERT INTO knowledge_chunks VALUES (
                'chk-leg-1', 'doc-leg-1', 'talleres_sur', 'sede-taller-01', 'TENANT',
                0, 'General', 'Protocolo cambio aceite sintetico cada 5000 kilometros.', 55, '2026-11-01 10:00:00'
            );
            INSERT INTO knowledge_documents VALUES (
                'doc-leg-2', 'talleres_sur', NULL, 'ACCOUNT',
                'Manual Corporativo Talleres', 'corp.txt', 'TXT', 90, 'hash2', 1,
                'READY', 'LOCAL_INDEXED', NULL, '[]', 'admin', '2026-11-01 10:05:00'
            );
            INSERT INTO knowledge_chunks VALUES (
                'chk-leg-2', 'doc-leg-2', 'talleres_sur', NULL, 'ACCOUNT',
                0, 'General', 'Horarios de atencion corporativa talleres de lunes a sabado.', 60, '2026-11-01 10:05:00'
            );
            """
        )
        conn.commit()
    finally:
        conn.close()

    repo = KnowledgeDocumentRepository(database_url=f"sqlite:///{legacy_db.as_posix()}")
    try:
        listing = repo.list_documents(org_id="talleres_sur")
        assert listing["total"] == 2
        assert listing["counts_by_site"]["sede-taller-01"] == 1
        scopes_by_id = {d["doc_id"]: d["scope"] for d in listing["records"]}
        assert scopes_by_id["doc-leg-1"] == "SITE"
        assert scopes_by_id["doc-leg-2"] == "ORGANIZATION"

        matches_site = repo.search_chunks(
            query="cambio aceite sintetico 5000 kilometros",
            org_id="talleres_sur",
            site_id="sede-taller-01",
            top_k=4,
        )
        assert len(matches_site) >= 1
        assert matches_site[0]["title"] == "Manual Cambio Aceite Legacy"
        assert matches_site[0]["scope"] == "SITE"

        matches_org = repo.search_chunks(
            query="horarios atencion corporativa",
            org_id="talleres_sur",
            site_id="otra-sede",
            top_k=4,
        )
        assert any(m["title"] == "Manual Corporativo Talleres" and m["scope"] == "ORGANIZATION" for m in matches_org)
        assert all(m["title"] != "Manual Cambio Aceite Legacy" for m in matches_org)
    finally:
        repo.close()
