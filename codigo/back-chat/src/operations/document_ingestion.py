"""
Pure-Python stdlib Document Text Extraction, Chunking, and Back-Busqueda Sync Operations.
Supports .pdf, .txt, .md, .csv, .json, .xlsx, .docx without external parser binaries.
"""

from __future__ import annotations

import csv
import io
import json
import logging
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Tuple
import xml.etree.ElementTree as ET
import zipfile
import zlib

import httpx

from src.config import settings

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {".pdf", ".txt", ".md", ".csv", ".json", ".xlsx", ".docx"}

_PDF_STRUCTURAL_NOISE = re.compile(
    r"^(?:%PDF-|%%EOF|\d+\s+\d+\s+obj|endobj|xref|trailer|startxref|stream|endstream|<<.*>>)$"
)


def _decode_bytes(raw_bytes: bytes) -> str:
    try:
        return raw_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw_bytes.decode("latin-1", errors="replace")


def _extract_csv_text(raw_bytes: bytes) -> str:
    text_data = _decode_bytes(raw_bytes).strip()
    if not text_data:
        return ""
    sample_lines = [ln for ln in text_data.splitlines()[:10] if ln.strip()]
    sample = "\n".join(sample_lines)
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel

    reader = csv.reader(io.StringIO(text_data), dialect=dialect)
    rows = [[cell.strip() for cell in row] for row in reader if any(c.strip() for c in row)]
    if not rows:
        return ""
    if len(rows) == 1:
        return " | ".join(c for c in rows[0] if c)

    headers = rows[0]
    formatted_rows: List[str] = []
    for row in rows[1:]:
        pairs: List[str] = []
        for idx, val in enumerate(row):
            if not val:
                continue
            header = headers[idx] if idx < len(headers) and headers[idx] else f"col_{idx + 1}"
            pairs.append(f"{header}: {val}")
        if pairs:
            formatted_rows.append(" | ".join(pairs))

    if not formatted_rows:
        return " | ".join(c for c in headers if c)
    return "\n".join(formatted_rows)


def _extract_json_text(raw_bytes: bytes) -> str:
    text_data = _decode_bytes(raw_bytes).strip()
    if not text_data:
        return ""
    try:
        parsed = json.loads(text_data)
        return json.dumps(parsed, ensure_ascii=False, indent=2)
    except json.JSONDecodeError:
        return text_data


def _local_name(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[1]
    return tag


def _extract_docx_text(raw_bytes: bytes) -> str:
    try:
        with zipfile.ZipFile(io.BytesIO(raw_bytes)) as zf:
            if "word/document.xml" not in zf.namelist():
                raise ValueError("El archivo DOCX no contiene word/document.xml.")
            xml_bytes = zf.read("word/document.xml")
    except zipfile.BadZipFile as exc:
        raise ValueError("El archivo DOCX no es un paquete ZIP válido.") from exc

    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        raise ValueError("No se pudo interpretar el XML interno del archivo DOCX.") from exc

    paragraphs: List[str] = []
    for elem in root.iter():
        if _local_name(elem.tag) == "p":
            parts: List[str] = []
            for sub in elem.iter():
                name = _local_name(sub.tag)
                if name == "t" and sub.text:
                    parts.append(sub.text)
                elif name == "tab":
                    parts.append("\t")
                elif name == "br":
                    parts.append("\n")
            line = "".join(parts).strip()
            if line:
                paragraphs.append(line)
    return "\n\n".join(paragraphs)


def _sheet_sort_key(path: str) -> Tuple[int, str]:
    match = re.search(r"sheet(\d+)\.xml$", path)
    if match:
        return (int(match.group(1)), path)
    return (999999, path)


def _col_ref_to_index(cell_ref: str) -> Optional[int]:
    match = re.match(r"^([A-Za-z]+)\d+$", cell_ref or "")
    if not match:
        return None
    col_str = match.group(1).upper()
    idx = 0
    for ch in col_str:
        idx = idx * 26 + (ord(ch) - ord("A") + 1)
    return idx - 1


def _extract_xlsx_text(raw_bytes: bytes) -> str:
    try:
        with zipfile.ZipFile(io.BytesIO(raw_bytes)) as zf:
            names = zf.namelist()
            shared_strings: List[str] = []
            if "xl/sharedStrings.xml" in names:
                try:
                    ss_root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
                    for si in ss_root.iter():
                        if _local_name(si.tag) == "si":
                            text_parts = [
                                t.text or ""
                                for t in si.iter()
                                if _local_name(t.tag) == "t"
                            ]
                            shared_strings.append("".join(text_parts))
                except ET.ParseError as exc:
                    raise ValueError("No se pudo leer xl/sharedStrings.xml del archivo XLSX.") from exc

            sheet_paths = sorted(
                [n for n in names if n.startswith("xl/worksheets/sheet") and n.endswith(".xml")],
                key=_sheet_sort_key,
            )
            if not sheet_paths:
                raise ValueError("El archivo XLSX no contiene hojas de cálculo válidas.")

            sheet_outputs: List[str] = []
            for sheet_path in sheet_paths:
                try:
                    sheet_root = ET.fromstring(zf.read(sheet_path))
                except ET.ParseError as exc:
                    raise ValueError(f"XML inválido en {sheet_path}.") from exc

                row_lines: List[str] = []
                for row_elem in sheet_root.iter():
                    if _local_name(row_elem.tag) != "row":
                        continue
                    row_values: List[str] = []
                    for cell in row_elem:
                        if _local_name(cell.tag) != "c":
                            continue
                        cell_type = cell.attrib.get("t", "")
                        col_idx = _col_ref_to_index(cell.attrib.get("r", ""))
                        val_text = ""

                        v_elem = None
                        is_elem = None
                        for child in cell:
                            cname = _local_name(child.tag)
                            if cname == "v":
                                v_elem = child
                            elif cname == "is":
                                is_elem = child

                        if cell_type == "s" and v_elem is not None and v_elem.text is not None:
                            try:
                                ss_idx = int(v_elem.text.strip())
                                if 0 <= ss_idx < len(shared_strings):
                                    val_text = shared_strings[ss_idx]
                            except ValueError:
                                val_text = v_elem.text
                        elif cell_type == "inlineStr" or is_elem is not None:
                            target = is_elem if is_elem is not None else cell
                            val_text = "".join(
                                t.text or ""
                                for t in target.iter()
                                if _local_name(t.tag) == "t"
                            )
                        elif cell_type == "b" and v_elem is not None and v_elem.text is not None:
                            val_text = "TRUE" if v_elem.text.strip() == "1" else "FALSE"
                        elif v_elem is not None and v_elem.text is not None:
                            val_text = v_elem.text

                        val_text = val_text.strip()
                        if col_idx is not None:
                            while len(row_values) <= col_idx:
                                row_values.append("")
                            row_values[col_idx] = val_text
                        elif val_text:
                            row_values.append(val_text)

                    non_empty = [v for v in row_values if v != ""]
                    if non_empty:
                        row_lines.append(" | ".join(non_empty))

                if row_lines:
                    if len(sheet_paths) > 1:
                        sheet_name = Path(sheet_path).stem
                        sheet_outputs.append(f"[{sheet_name}]\n" + "\n".join(row_lines))
                    else:
                        sheet_outputs.append("\n".join(row_lines))

            return "\n\n".join(sheet_outputs)
    except zipfile.BadZipFile as exc:
        raise ValueError("El archivo XLSX no es un paquete ZIP válido.") from exc


def _decode_pdf_literal_bytes(raw: bytes) -> str:
    out = bytearray()
    i = 0
    n = len(raw)
    while i < n:
        ch = raw[i]
        if ch == 92 and i + 1 < n:  # backslash
            nxt = raw[i + 1]
            if nxt == ord("n"):
                out.append(10)
                i += 2
            elif nxt == ord("r"):
                out.append(13)
                i += 2
            elif nxt == ord("t"):
                out.append(9)
                i += 2
            elif nxt == ord("b"):
                out.append(8)
                i += 2
            elif nxt == ord("f"):
                out.append(12)
                i += 2
            elif nxt in (ord("("), ord(")"), ord("\\")):
                out.append(nxt)
                i += 2
            elif nxt in (10, 13):
                # Line continuation
                i += 2
                if nxt == 13 and i < n and raw[i] == 10:
                    i += 1
            elif 48 <= nxt <= 55:  # octal \ddd
                oct_digits = bytes([nxt])
                j = i + 2
                while j < n and len(oct_digits) < 3 and 48 <= raw[j] <= 55:
                    oct_digits += bytes([raw[j]])
                    j += 1
                out.append(int(oct_digits, 8) & 0xFF)
                i = j
            else:
                out.append(nxt)
                i += 2
        else:
            out.append(ch)
            i += 1

    raw_bytes = bytes(out)
    if raw_bytes.startswith(b"\xfe\xff"):
        return raw_bytes[2:].decode("utf-16-be", errors="replace")
    try:
        return raw_bytes.decode("utf-8")
    except UnicodeDecodeError:
        return raw_bytes.decode("latin-1", errors="replace")


def _decode_pdf_hex_bytes(hex_bytes: bytes) -> str:
    cleaned = re.sub(rb"\s+", b"", hex_bytes)
    if len(cleaned) % 2 == 1:
        cleaned += b"0"
    try:
        raw = bytes.fromhex(cleaned.decode("ascii"))
    except ValueError:
        return ""
    if raw.startswith(b"\xfe\xff"):
        return raw[2:].decode("utf-16-be", errors="replace")
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("latin-1", errors="replace")


def _scan_pdf_text_operators(stream_bytes: bytes) -> List[str]:
    """Extracts text from PDF Tj, TJ, ', and \" operators inside a content stream."""
    extracted: List[str] = []
    n = len(stream_bytes)
    i = 0
    tokens: List[Tuple[str, Any]] = []

    while i < n:
        ch = stream_bytes[i]
        # Skip whitespace
        if ch in (9, 10, 12, 13, 32):
            i += 1
            continue
        # Skip PDF comment
        if ch == 37:  # '%'
            while i < n and stream_bytes[i] not in (10, 13):
                i += 1
            continue
        # Literal string (...)
        if ch == 40:  # '('
            depth = 1
            start = i + 1
            j = start
            while j < n and depth > 0:
                if stream_bytes[j] == 92:  # '\'
                    j += 2
                    continue
                if stream_bytes[j] == 40:
                    depth += 1
                elif stream_bytes[j] == 41:
                    depth -= 1
                    if depth == 0:
                        break
                j += 1
            literal_raw = stream_bytes[start:j]
            tokens.append(("STR", _decode_pdf_literal_bytes(literal_raw)))
            i = j + 1
            continue
        # Hex string <...> (not dictionary <<...>>)
        if ch == 60:  # '<'
            if i + 1 < n and stream_bytes[i + 1] == 60:
                i += 2
                continue
            end = stream_bytes.find(b">", i + 1)
            if end != -1:
                tokens.append(("STR", _decode_pdf_hex_bytes(stream_bytes[i + 1:end])))
                i = end + 1
                continue
            i += 1
            continue
        # Array [...] for TJ
        if ch == 91:  # '['
            j = i + 1
            arr_parts: List[str] = []
            while j < n and stream_bytes[j] != 93:  # ']'
                ach = stream_bytes[j]
                if ach == 40:
                    depth = 1
                    start = j + 1
                    k = start
                    while k < n and depth > 0:
                        if stream_bytes[k] == 92:
                            k += 2
                            continue
                        if stream_bytes[k] == 40:
                            depth += 1
                        elif stream_bytes[k] == 41:
                            depth -= 1
                            if depth == 0:
                                break
                        k += 1
                    arr_parts.append(_decode_pdf_literal_bytes(stream_bytes[start:k]))
                    j = k + 1
                elif ach == 60 and not (j + 1 < n and stream_bytes[j + 1] == 60):
                    end = stream_bytes.find(b">", j + 1)
                    if end != -1:
                        arr_parts.append(_decode_pdf_hex_bytes(stream_bytes[j + 1:end]))
                        j = end + 1
                    else:
                        j += 1
                elif ach in (45, 46) or (48 <= ach <= 57):
                    k = j + 1
                    while k < n and (stream_bytes[k] in (45, 46) or 48 <= stream_bytes[k] <= 57):
                        k += 1
                    try:
                        kern = float(stream_bytes[j:k].decode("ascii"))
                        if kern <= -120 and arr_parts and not arr_parts[-1].endswith(" "):
                            arr_parts.append(" ")
                    except ValueError:
                        pass
                    j = k
                else:
                    j += 1
            tokens.append(("ARR", "".join(arr_parts)))
            i = (j + 1) if j < n else n
            continue
        # Word / operator
        if ch in (39, 34):  # ' or "
            op = chr(ch)
            if tokens and tokens[-1][0] == "STR":
                text_val = tokens[-1][1].strip()
                if text_val:
                    extracted.append(text_val)
            tokens.clear()
            i += 1
            continue
        if (65 <= ch <= 90) or (97 <= ch <= 122) or ch == 42:  # letters or *
            k = i + 1
            while k < n and ((65 <= stream_bytes[k] <= 90) or (97 <= stream_bytes[k] <= 122) or 48 <= stream_bytes[k] <= 57 or stream_bytes[k] == 42):
                k += 1
            op = stream_bytes[i:k].decode("ascii", errors="ignore")
            if op == "Tj" and tokens and tokens[-1][0] == "STR":
                text_val = tokens[-1][1].strip()
                if text_val:
                    extracted.append(text_val)
                tokens.clear()
            elif op == "TJ" and tokens and tokens[-1][0] == "ARR":
                text_val = tokens[-1][1].strip()
                if text_val:
                    extracted.append(text_val)
                tokens.clear()
            elif op in ("Td", "TD", "T*", "ET"):
                tokens.clear()
            i = k
            continue

        i += 1

    return extracted


def _try_zlib_decompress(data: bytes) -> Optional[bytes]:
    candidates = [data, data.strip(b"\r\n"), data.lstrip(b"\r\n")]
    for candidate in candidates:
        if not candidate:
            continue
        try:
            return zlib.decompress(candidate)
        except Exception:
            pass
        try:
            return zlib.decompressobj().decompress(candidate)
        except Exception:
            pass
    return None


def _extract_pdf_text(raw_bytes: bytes, filename: str = "", title: str = "") -> str:
    if not raw_bytes:
        return ""

    extracted_parts: List[str] = []

    try:
        # Match PDF streams with optional preceding dictionary
        stream_pattern = re.compile(
            rb"(<<(?:[^>]|>(?!>))*>>)?\s*stream\r?\n(.*?)\r?\n?endstream",
            re.DOTALL,
        )
        for match in stream_pattern.finditer(raw_bytes):
            dict_bytes = match.group(1) or b""
            stream_data = match.group(2)
            is_flate = b"/FlateDecode" in dict_bytes or (len(stream_data) >= 2 and stream_data[0] == 0x78)

            decoded_stream = _try_zlib_decompress(stream_data) if is_flate else None
            if decoded_stream is None:
                decoded_stream = stream_data

            ops_text = _scan_pdf_text_operators(decoded_stream)
            if ops_text:
                extracted_parts.extend(ops_text)

        # Also scan raw bytes directly in case Tj/TJ exist outside stream/endstream markers
        if not extracted_parts:
            ops_text = _scan_pdf_text_operators(raw_bytes)
            if ops_text:
                extracted_parts.extend(ops_text)

        if extracted_parts:
            return "\n".join(extracted_parts).strip()

        # Fallback 1: readable ASCII/Latin-1 text runs excluding PDF structural tokens
        decoded_text = _decode_bytes(raw_bytes)
        readable_runs: List[str] = []
        for line in decoded_text.splitlines():
            clean = line.strip()
            if len(clean) < 12:
                continue
            if _PDF_STRUCTURAL_NOISE.match(clean):
                continue
            if clean.startswith("/") or "endobj" in clean or "FlateDecode" in clean:
                continue
            alpha_ratio = sum(1 for c in clean if c.isalpha() or c == " ") / max(1, len(clean))
            if alpha_ratio >= 0.65 and " " in clean:
                readable_runs.append(clean)
        if readable_runs:
            return "\n".join(readable_runs).strip()
    except Exception as exc:
        logger.warning("PDF extraction encountered non-fatal issue for %s: %s", filename, exc)

    # Fallback 2: Safe metadata placeholder for binary/scanned PDFs (never fail with 500)
    label = title or filename or "documento.pdf"
    return (
        f"Documento PDF '{label}' ({len(raw_bytes)} bytes). "
        "No se detectó capa de texto plano extraíble (posible PDF escaneado o binario)."
    )


def extract_text_from_bytes(
    filename: str,
    raw_bytes: bytes,
    content_text: Optional[str] = None,
    title: str = "",
) -> str:
    """
    Extracts plain text from supported document formats using only the Python standard library.
    If content_text is non-empty after strip, returns it directly.
    """
    if content_text is not None and content_text.strip():
        return content_text.strip()

    if not raw_bytes:
        return ""

    ext = Path(filename or "").suffix.lower()
    if ext in (".txt", ".md"):
        return _decode_bytes(raw_bytes).strip()
    if ext == ".csv":
        return _extract_csv_text(raw_bytes)
    if ext == ".json":
        return _extract_json_text(raw_bytes)
    if ext == ".docx":
        return _extract_docx_text(raw_bytes)
    if ext == ".xlsx":
        return _extract_xlsx_text(raw_bytes)
    if ext == ".pdf":
        return _extract_pdf_text(raw_bytes, filename=filename, title=title)

    raise ValueError(f"Extensión de archivo no soportada: '{ext}'")


def _split_long_paragraph(paragraph: str, chunk_size: int) -> List[str]:
    if len(paragraph) <= chunk_size:
        return [paragraph]

    sentences = re.split(r"(?<=[.!?])\s+", paragraph)
    units: List[str] = []
    current = ""
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        if len(sentence) > chunk_size:
            if current:
                units.append(current)
                current = ""
            # Split oversized sentence by word boundaries
            words = sentence.split(" ")
            buf = ""
            for word in words:
                candidate = f"{buf} {word}".strip() if buf else word
                if len(candidate) <= chunk_size:
                    buf = candidate
                else:
                    if buf:
                        units.append(buf)
                    while len(word) > chunk_size:
                        units.append(word[:chunk_size])
                        word = word[chunk_size:]
                    buf = word
            if buf:
                units.append(buf)
        else:
            candidate = f"{current} {sentence}".strip() if current else sentence
            if len(candidate) <= chunk_size:
                current = candidate
            else:
                if current:
                    units.append(current)
                current = sentence
    if current:
        units.append(current)
    return units


def chunk_text(
    text: str,
    title: str,
    chunk_size: int = 750,
    overlap: int = 120,
) -> List[Dict[str, Any]]:
    """
    Splits extracted document text cleanly by paragraphs/sentences with overlap.
    Guarantees at least 1 chunk when text is non-empty.
    """
    cleaned = (text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not cleaned:
        return []

    raw_paragraphs = [p.strip() for p in re.split(r"\n\s*\n", cleaned) if p.strip()]
    if not raw_paragraphs:
        raw_paragraphs = [cleaned]

    units_with_sections: List[Tuple[str, str]] = []
    current_section = "General"
    for para in raw_paragraphs:
        first_line = para.splitlines()[0].strip()
        if first_line.startswith("#"):
            heading = first_line.lstrip("#").strip()
            if heading:
                current_section = heading[:255]
        for sub_unit in _split_long_paragraph(para, chunk_size):
            units_with_sections.append((current_section, sub_unit))

    chunks: List[Dict[str, Any]] = []
    current_parts: List[str] = []
    current_section_name = units_with_sections[0][0] if units_with_sections else "General"
    current_len = 0

    def _flush_chunk() -> None:
        nonlocal current_parts, current_len
        if not current_parts:
            return
        content = "\n\n".join(current_parts).strip()
        if content:
            chunks.append(
                {
                    "chunk_index": len(chunks),
                    "section": current_section_name or title[:255] or "General",
                    "content": content,
                    "char_count": len(content),
                }
            )
        if overlap > 0 and content:
            tail = content[-overlap:].strip()
            # Align tail to first whitespace so we don't start mid-word if possible
            space_pos = tail.find(" ")
            if 0 < space_pos < len(tail) - 10:
                tail = tail[space_pos + 1:].strip()
            current_parts = [tail] if tail else []
            current_len = len(tail) if tail else 0
        else:
            current_parts = []
            current_len = 0

    for sec, unit in units_with_sections:
        added_len = len(unit) + (2 if current_parts else 0)
        if current_parts and (current_len + added_len > chunk_size):
            _flush_chunk()
            current_section_name = sec
        elif not current_parts:
            current_section_name = sec

        # Avoid duplicating if overlap already equals unit prefix
        if current_parts and current_parts[-1] == unit:
            continue
        current_parts.append(unit)
        current_len += len(unit) + (2 if len(current_parts) > 1 else 0)

    if current_parts:
        last_content = "\n\n".join(current_parts).strip()
        if last_content and (not chunks or last_content != chunks[-1]["content"]):
            chunks.append(
                {
                    "chunk_index": len(chunks),
                    "section": current_section_name or title[:255] or "General",
                    "content": last_content,
                    "char_count": len(last_content),
                }
            )

    if not chunks:
        chunks.append(
            {
                "chunk_index": 0,
                "section": "General",
                "content": cleaned,
                "char_count": len(cleaned),
            }
        )

    return chunks


def _resolve_busqueda_target_url(org_id: str) -> str:
    return (
        settings.ORG_BUSQUEDA_URLS.get(org_id)
        or settings.ORG_BUSQUEDA_URLS.get("default")
        or settings.BACK_BUSQUEDA_URL
    ).rstrip("/")


async def sync_document_to_busqueda(
    doc: Dict[str, Any],
    chunks: List[Dict[str, Any]],
) -> Tuple[str, str]:
    """
    Syncs document metadata and chunks to the organization's back-busqueda vector API.
    Returns (vector_sync_status, vector_sync_detail).
    """
    target_url = _resolve_busqueda_target_url(doc["org_id"])
    payload = {
        "doc_id": doc["doc_id"],
        "org_id": doc["org_id"],
        "site_id": doc.get("site_id"),
        "scope": doc["scope"],
        "title": doc["title"],
        "filename": doc["filename"],
        "content_hash": doc["content_hash"],
        "tags": doc.get("tags") or [],
        "chunks": chunks,
    }
    headers = {"X-Internal-Key": settings.BUSQUEDA_SERVICE_KEY}

    try:
        async with httpx.AsyncClient(timeout=settings.BACK_BUSQUEDA_TIMEOUT_SECONDS) as client:
            resp = await client.post(
                f"{target_url}/api/v1/documents/ingest",
                json=payload,
                headers=headers,
            )
            if resp.status_code in (200, 201):
                return ("SYNCED_REMOTE", f"Sincronizado con {target_url}")
            return ("SYNC_ERROR", f"Error HTTP {resp.status_code} en {target_url}")
    except (httpx.ConnectError, httpx.TimeoutException, Exception) as exc:
        logger.info("back-busqueda no disponible en %s (%s); documento indexado localmente.", target_url, exc)
        return ("LOCAL_INDEXED", f"Indexado localmente; back-busqueda no disponible en {target_url}")


async def notify_delete_to_busqueda(doc_id: str, org_id: str) -> None:
    """Best-effort notification to delete a document from remote back-busqueda index."""
    target_url = _resolve_busqueda_target_url(org_id)
    headers = {"X-Internal-Key": settings.BUSQUEDA_SERVICE_KEY}
    try:
        async with httpx.AsyncClient(timeout=settings.BACK_BUSQUEDA_TIMEOUT_SECONDS) as client:
            await client.delete(
                f"{target_url}/api/v1/documents/{doc_id}",
                headers=headers,
            )
    except Exception as exc:
        logger.debug("No se pudo notificar borrado de %s a %s: %s", doc_id, target_url, exc)
