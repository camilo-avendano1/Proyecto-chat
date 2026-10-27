import httpx
import json

BASE_URL = "http://localhost:8000"

# 1. Crear Sesión
session_resp = httpx.post(
    f"{BASE_URL}/api/v1/widget/session",
    headers={"X-Widget-Key": "pk_live_sigires_8f9a2b1c3d4e5f6a"},
    json={
        "client_id": "sigires",
        "origin": "https://sigires.procex.co",
        "eps_id": "eps_sura_01",
        "ips_code": "631300040301"
    }
)
session = session_resp.json()
token = session["session_token"]
print("✅ Sesión creada exitosamente. Token obtenido.")

# 2. Diagnóstico en Streaming (Consulta general de formulario apoyada en Búsqueda RAG)
payload = {
    "query": "Al subir el formulario de enfermería tengo un error de validación en el campo 6 de signos vitales",
    "system_logs": "Fila: 12 | Campo: 6 | Variable 'Signos_Vitales' fuera de rango permitido. Error CE_CAMPO_006_INVAL",
    "ui_context": {
        "url": "https://plataforma.salud.co/formularios/enfermeria",
        "pagina_actual": "REGISTRO_ENFERMERIA",
        "modulo": "FORMULARIOS_CLINICOS",
        "estado_cargue_actual": "CON_ERRORES",
        "formato_archivo": "FORMULARIO_CLINICO_CSV"
    },
    "user_context": {
        "usuario": "enf.laura.gomez",
        "eps": "EPS_SURA",
        "ips_code": "631300040301",
        "permisos": "PERFIL_IPS_ENFERMERO"
    }
}

print("\n--- Respuesta Streaming desde el LLM / Motor Asistencial ---")
with httpx.stream(
    "POST",
    f"{BASE_URL}/api/v1/diagnostic/stream",
    headers={"Authorization": f"Bearer {token}", "Accept": "text/event-stream"},
    json=payload,
    timeout=60.0
) as stream_resp:
    for line in stream_resp.iter_lines():
        if line.startswith("data: "):
            data_content = line[6:]
            try:
                parsed = json.loads(data_content)
                if "text" in parsed:
                    print(parsed["text"], end="", flush=True)
            except json.JSONDecodeError:
                pass
print("\n\n--- Flujo completado ---")
