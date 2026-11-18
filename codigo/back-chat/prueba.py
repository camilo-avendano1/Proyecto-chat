"""Script de verificación rápida del flujo genérico multi-cliente (Handshake + Chat SSE)."""

import json
import httpx

BASE_URL = "http://localhost:8000"


def stream_chat(token: str, payload: dict) -> None:
    """Envía una consulta a POST /api/v1/chat/stream e imprime el stream SSE."""
    with httpx.stream(
        "POST",
        f"{BASE_URL}/api/v1/chat/stream",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "text/event-stream",
        },
        json=payload,
        timeout=60.0,
    ) as stream_resp:
        stream_resp.raise_for_status()
        current_event = "message"
        for line in stream_resp.iter_lines():
            if not line:
                current_event = "message"
                continue
            if line.startswith("event:"):
                current_event = line[6:].strip()
            elif line.startswith("data:"):
                data_content = line[5:].strip()
                try:
                    parsed = json.loads(data_content)
                except json.JSONDecodeError:
                    continue
                if current_event == "chunk" and isinstance(parsed, dict) and "text" in parsed:
                    print(parsed["text"], end="", flush=True)
                elif current_event in ("error_diagnostic", "sources", "done", "error"):
                    print(f"\n[{current_event}] {json.dumps(parsed, ensure_ascii=False)}")


def main() -> None:
    # 1. Handshake mínimo (solo X-Widget-Key + Origin + body vacío {})
    session_resp = httpx.post(
        f"{BASE_URL}/api/v1/widget/session",
        headers={
            "X-Widget-Key": "pk_live_otraempresa_1a2b3c4d5e6f7a8b",
            "Origin": "http://localhost:5173",
        },
        json={},
        timeout=10.0,
    )
    session_resp.raise_for_status()
    session = session_resp.json()
    token = session["session_token"]
    print(
        f"✅ Sesión creada | client={session.get('client_id')} "
        f"({session.get('client_name')}) | tenant={session.get('tenant_name')}"
    )

    # 2. Chat en Streaming Mínimo (únicamente {"query": "..."})
    print("\n=== 2. Chat Streaming Mínimo (solo query) ===")
    minimal_payload = {
        "query": "¿Cómo se aprueba una orden de compra?",
    }
    stream_chat(token, minimal_payload)

    # 3. Ejemplo Enriquecido Opcional (con user, context, logs y extras)
    print("\n=== 3. Chat Streaming Enriquecido (user + context + logs + extras) ===")
    enriched_payload = {
        "query": "Al subir la orden de compra tengo un error de validación en el campo 6 de centro de costos",
        "logs": "Fila: 12 | Campo: 6 | Variable 'Centro_Costo' fuera de catálogo permitido. Error CE_CAMPO_006_INVAL",
        "user": {
            "id": "ana.martinez",
            "role": "ANALISTA_COMPRAS",
            "organization": "División Operativa Central",
            "unit_code": "CORP-01",
        },
        "context": {
            "url": "https://portal.empresa.com/compras/ordenes",
            "view": "APROBACION_ORDENES",
            "module": "COMPRAS",
            "status": "CON_ERRORES",
            "file_format": "ORDEN_COMPRA_CSV",
        },
        "extras": {
            "departamento": "compras",
            "moneda": "COP",
        },
    }
    stream_chat(token, enriched_payload)
    print("\n--- Flujo completado ---")


if __name__ == "__main__":
    main()
