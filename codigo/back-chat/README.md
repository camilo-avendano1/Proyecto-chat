# Core SaaS Chat & RAG Gateway (`back-chat`)
## Orquestador Conversacional y de Búsqueda RAG Multi-Organización

> **Equipo de Desarrollo (Autores):**  
> - **Juan Camilo Avendaño**  
> - **Fran Sneider Quincha**  
> - **Adriana Moreno**  
>
> **Enfoque Genérico y Desacoplado:**  
> Este microservicio actúa como el **orquestador central de chat RAG** para múltiples organizaciones y sedes (portales corporativos, comercios/tiendas, talleres, IPS/clínicas, mesas de ayuda y plataformas técnicas como **SIGIRES**).  
> - Expone los endpoints principales **`POST /api/v1/chat/stream`** (SSE) y **`POST /api/v1/chat/query`** (JSON), aceptando peticiones tan simples como `{"query": "..."}` y enriquecimiento opcional (`user`, `context`, `logs`, `extras`, `conversation_history`).  
> - Mantiene **`POST /api/v1/diagnostic/stream`** y **`POST /api/v1/diagnostic/query`** (junto con `system_logs`, `ui_context`, `user_context`) como alias de compatibilidad retroactiva.  
> - El conocimiento, manuales, políticas y reglamentos no están quemados en este servicio: provienen dinámicamente de **`back-busqueda`** (`POST /api/v1/search`) y de los documentos cargados por organización/sede (`/api/v1/admin/documents`).

---

## 1. Diagrama de Flujo y Enrutamiento Multi-Organización

```
┌────────────────────────────────────────────────────────┐
│            Clientes Web / Widget / APIs                │
│  - Petición mínima: {"query": "..."}                   │
│  - Opcional: user, context, logs, extras, history      │
└───────────────────────────┬────────────────────────────┘
                            │ POST /api/v1/chat/stream | /query
                            ▼
┌────────────────────────────────────────────────────────────────────────┐
│                      SAAS CORE BACK CENTRAL (back-chat)                │
│  (Desarrollado por: Juan Camilo Avendaño, Fran Sneider Quincha, Adriana Moreno)│
│                                                                        │
│  1. Validación de JWT de Sesión (org_id, site_id, busqueda_url)        │
│  2. Sanitización PII / PHI (Cumplimiento Ley Estatutaria 1581 de 2012) │
│  3. Guardrails Pre-LLM (Respuestas directas 0 tokens, Anti-Injection)  │
│  4. Extracción Condicional de Logs (solo si hay logs/código técnico)   │
│  5. Búsqueda RAG en `back-busqueda`: query + extras sanitizados        │
│  6. Ensamblaje de Prompt Genérico: Rol + Contexto Opcional + RAG       │
│  7. Inferencia vía `llm-gateway` (:8003) y Emisión SSE / JSON          │
└───────────────┬────────────────────────────────────────┬───────────────┘
                │ POST /api/v1/search                    │ Inferencia + Ledger
                ▼                                        ▼
┌──────────────────────────────┐         ┌──────────────────────────────┐
│    back-busqueda (:8001)     │         │      llm-gateway (:8003)     │
│                              │         │                              │
│ - Devuelve fragmentos RAG    │         │ - LOCAL (LM Studio :1234)    │
│   aislados por org_id y      │         │ - LOCAL (Ollama :11434)      │
│   site_id (SITE/ORG/GLOBAL)  │         │ - CLOUD (OpenAI / DeepSeek)  │
└──────────────────────────────┘         └──────────────────────────────┘
```

---

## 2. Contrato Genérico y Separación de Responsabilidades

1. **Endpoints de Chat (`/api/v1/chat/stream` y `/api/v1/chat/query`):**
   - El único campo obligatorio es `query`.
   - Campos opcionales: `user` (identidad/rol/organización/sede), `context` (pantalla/módulo/formato/estado), `logs` (trazas de error), `extras` (metadatos para filtrar o priorizar en `back-busqueda`) y `conversation_history`.
   - Alias de compatibilidad: `/api/v1/diagnostic/stream` y `/api/v1/diagnostic/query`.
2. **System Prompt y Prompt de Usuario ([`src/operations/prompt_builder.py`](src/operations/prompt_builder.py)):**
   - Configura un asistente virtual técnico/operativo adaptado a `org_name` y al perfil del usuario (si se envía).
   - Se apoya en los fragmentos recuperados desde `back-busqueda` o desde los documentos locales del asistente sin asumir reglas de un dominio específico cuando no están presentes en el contexto.
3. **Parser Condicional de Logs ([`src/operations/log_parser_operations.py`](src/operations/log_parser_operations.py)):**
   - Si no se adjuntan `logs` ni patrones técnicos explícitos en la consulta, `error_diagnostic` se retorna como `null` (JSON) o `data: null` (SSE).
   - Cuando se adjuntan trazas técnicas, extrae fila, campo/variable, código de error y fase (`FASE_1_CA`, `FASE_2_CE`, `FASE_3_CD`).
4. **Búsqueda de Contexto ([`src/infrastructure/external/busqueda_client.py`](src/infrastructure/external/busqueda_client.py)):**
   - Envía `{ query, org_id, site_id, top_k, extras }` a la URL de `back-busqueda` configurada para la organización (`ORG_BUSQUEDA_URLS`).
   - Sanea `extras` (claves `snake_case`, valores escalares o listas planas, máx. 20 claves) combinando los `extras` enviados por la integración y las pistas extraídas de logs si existen.
   - Si `back-busqueda` no está disponible y `FALLBACK_LOCAL_SEARCH=true`, resuelve contra los documentos cargados en `data/knowledge_docs.db` respetando estrictamente `org_id`, `site_id` y alcance (`SITE`, `ORGANIZATION`, `GLOBAL`).

---

## 3. Compatibilidad con Modelos de IA: Local (LM Studio) y Producción

### Opción A: Pruebas en Local con LM Studio (Por Defecto)
1. Abra **LM Studio**, cargue el modelo deseado e inicie el **Local Server** en el puerto `1234`.
2. En el archivo `.env` (en `llm-gateway` y `back-chat`):
   ```env
   LLM_PROVIDER="lmstudio"
   LLM_BASE_URL="http://localhost:1234/v1"
   LLM_MODEL="local-model"
   LLM_API_KEY="lm-studio"
   ```

### Opción B: Despliegue en Producción (OpenAI / DeepSeek / Azure)
```env
LLM_PROVIDER="openai"
LLM_BASE_URL="https://api.openai.com/v1"
LLM_MODEL="gpt-4o-mini"
LLM_API_KEY="sk-proj-tu-api-key-de-produccion-aqui"
```

---

## 4. Estructura del Proyecto (Clean Architecture)

```text
codigo/back-chat/
├── prueba.py                            # Script rápido de prueba end-to-end (otra_empresa + chat/stream)
├── src/
│   ├── main.py                          # Entrada FastAPI, lifespan, CORS, middleware de auditoría
│   ├── config.py                        # Configuración Pydantic Settings (.env)
│   ├── domain/                          # Entidades y objetos de valor desacoplados
│   ├── operations/                      # Casos de uso (orquestación chat/RAG, documentos, guardrails, log parser, prompt builder, PII sanitizer, sesión)
│   ├── infrastructure/                  # Adaptadores HTTP (busqueda_client, llm_gateway_client), repositorios, seguridad JWT y auditoría
│   ├── models/                          # Esquemas Pydantic v2 (chat mínimo/enriquecido y gestión de documentos/sedes)
│   └── routers/                         # Endpoints FastAPI (/api/v1/chat/*, /api/v1/diagnostic/*, /api/v1/widget/session, /api/v1/admin/*)
└── tests/                               # Suite automatizada con pytest
```

---

## 5. Ejecución y Pruebas

```powershell
# Iniciar el servidor en desarrollo
$env:DISABLE_SQLALCHEMY_CEXT="1"; uvicorn src.main:app --reload --port 8000

# Prueba rápida end-to-end (con auth-service y back-chat activos)
python prueba.py

# Ejecutar suite de pruebas
$env:DISABLE_SQLALCHEMY_CEXT="1"; pytest -v
```
