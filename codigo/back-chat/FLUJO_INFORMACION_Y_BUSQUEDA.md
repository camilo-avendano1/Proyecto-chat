# Flujo de Información, System Prompt e Integración con Back - Búsqueda (RAG)

Este documento explica cómo procesa la información el microservicio **`back-chat`**, por qué su diseño es genérico y multi-cliente (desde una petición mínima `{"query": "..."}` hasta consultas enriquecidas con contexto, logs y `extras`), y cómo **`back-busqueda`** provee dinámicamente el conocimiento de cada cliente.

---

## 1. Principio Arquitectónico: Núcleo Agnóstico al Cliente

El sistema separa estrictamente la orquestación conversacional del conocimiento particular de cada empresa:

1. **Contrato de Entrada Flexible (`/api/v1/chat/stream` y `/api/v1/chat/query`):**
   - **Modo Mínimo:** Un cliente nuevo puede integrarse enviando únicamente `{"query": "¿Cómo se aprueba una orden de compra?"}` (junto con `conversation_history` si hay historial).
   - **Modo Enriquecido (Opcional):** El integrador puede añadir `user`, `context`, `logs` y `extras` cuando su aplicación disponga de contexto de pantalla, trazas de error o metadatos de filtrado.
   - **Compatibilidad Retroactiva:** Se conservan `/api/v1/diagnostic/stream` y `/api/v1/diagnostic/query` (y los nombres de campo `system_logs`, `ui_context`, `user_context`) para clientes legacy como SIGIRES.
2. **El System Prompt ([`PromptBuilder`](src/operations/prompt_builder.py)):**
   - Define el rol del asistente virtual adaptado al `client_name` y al perfil del usuario (si se suministra), instruyendo al modelo a responder con base en los fragmentos recuperados por `back-busqueda`.
   - No contiene reglas, catálogos ni resoluciones específicas quemadas en el código.
3. **La Búsqueda Semántica / RAG ([`BusquedaHttpClient`](src/infrastructure/external/busqueda_client.py) -> `back-busqueda`):**
   - Es la fuente de verdad de manuales, políticas, procesos, definiciones de campos y reglamentos de cada cliente.
   - Recibe `query`, `client_id`, `tenant_id`, `top_k` y `extras` sanitizados desde `back-chat`.

---

## 2. Etapas del Flujo Interno en `back-chat`

### A. Sanitización y Guardrails Pre-LLM
1. **PII / PHI Sanitizer:** Enmascara datos personales sensibles (cédulas, teléfonos, correos, etc.) en `query` y `logs` antes de consultar servicios externos o almacenar trazas (Ley 1581 de 2012).
2. **Guardrails (`ChatGuardrails`):** Intercepta saludos/despedidas (Fast-Path con `0` tokens), intentos de Prompt Injection y consultas explícitamente fuera de dominio.

### B. Extracción Condicional de Metadatos (`LogParserOperations`)
- **Consultas Generales (sin `logs` ni códigos de error técnicos):** No fuerza un diagnóstico artificial; `error_diagnostic` se retorna como `null` (JSON) o `data: null` (SSE).
- **Consultas con Trazas (`logs`) o Errores Técnicos:** Extrae señales genéricas sin depender de una norma fija:
  - **Fila / Registro afectado**
  - **Campo / Variable / Columna afectada**
  - **Código de error**
  - **Fase de validación:** `FASE_1_CA` (Archivo/Formato), `FASE_2_CE` (Estructura/Campos), `FASE_3_CD` (Datos/Coherencia).

### C. Consulta al Servicio de Búsqueda (`back-busqueda`)
[`BusquedaHttpClient`](src/infrastructure/external/busqueda_client.py) realiza un `POST` a la URL configurada para el cliente (`http://localhost:8001/api/v1/search` por defecto):
- Combina los `extras` enviados por el llamador con cualquier pista técnica extraída de `logs` (aplicando `sanitize_extras`: claves `snake_case`, valores escalares o listas planas, máx. 20 claves).
- Si `back-busqueda` responde `200 OK`, convierte `results` / `chunks` en `KnowledgeSource` y los inyecta en el prompt.
- Si `back-busqueda` no está disponible y `FALLBACK_LOCAL_SEARCH=true`, usa un banco de contingencia neutro.

### D. Ensamblaje del Prompt e Inferencia (`llm-gateway`)
- Construye `system_prompt` y `user_prompt` (incluyendo únicamente las secciones de `user`, `context`, `logs` y `error_diagnostic` que realmente existan en la petición, más los fragmentos RAG).
- Envía la inferencia a `llm-gateway` (`POST /internal/v1/chat`) con la atribución de `client_id`, `tenant_id`, `usuario`, `rol` y `operacion`, emitiendo chunks SSE o JSON consolidado.

---

## 3. Contrato de Comunicación con `back-busqueda`

### A. Petición Genérica Mínima (Ej. `otra_empresa`)

- **Método HTTP:** `POST`
- **URL por defecto:** `http://localhost:8001/api/v1/search` *(o la URL por cliente en `CLIENT_BUSQUEDA_URLS`)*
- **Headers:** `Content-Type: application/json`, `X-Internal-Key: <BUSQUEDA_SERVICE_KEY>`, `X-Request-ID: <UUID>`

```json
{
  "query": "¿Cómo se aprueba una orden de compra?",
  "client_id": "otra_empresa",
  "tenant_id": "e55f6a7b-8c9d-0e1f-2a3b-4c5d6e7f8a9b",
  "top_k": 4,
  "extras": {}
}
```

### B. Petición con `extras` Personalizados o Pistas de Log (Ej. SIGIRES)

```json
{
  "query": "Al subir el formulario de enfermería tengo un error de validación en el campo 6 de signos vitales",
  "client_id": "sigires",
  "tenant_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
  "top_k": 4,
  "extras": {
    "category": "CALIDAD_ESTRUCTURA_CAMPOS",
    "variable_number": 6,
    "error_code": "CE_CAMPO_006_INVAL"
  }
}
```

### C. Respuesta esperada por `back-chat` (`200 OK`)

`back-busqueda` retorna la lista de fragmentos relevantes bajo `"results"` o `"chunks"`:

```json
{
  "results": [
    {
      "title": "Manual Corporativo de Compras y Aprobaciones",
      "scope": "ACCOUNT",
      "section": "Flujo de Aprobación de Órdenes de Compra",
      "snippet": "Toda orden de compra debe ser registrada por el analista en el portal de compras, validada por el jefe de área hasta 50 SMMLV y aprobada por Gerencia Administrativa si supera dicho umbral.",
      "score": 0.94
    }
  ]
}
```

---

## 4. Diagrama del Flujo de Datos Completo

```
┌───────────────────────────────────────────────────────────────────┐
│   Cliente / Widget / Integración Backend                          │
│   Envía {"query": "..."} (+ user, context, logs, extras opcional) │
└─────────────────────────────────┬─────────────────────────────────┘
                                  │ POST /api/v1/chat/stream
                                  ▼
┌───────────────────────────────────────────────────────────────────┐
│                      back-chat (FastAPI:8000)                     │
│                                                                   │
│ 1. PIISanitizer + ChatGuardrails:                                 │
│    Protege datos personales (Ley 1581) y filtra saludos/ataques   │
│                                                                   │
│ 2. LogParserOperations (Condicional):                             │
│    Solo extrae Fase/Variable/Código si hay logs o error técnico;  │
│    de lo contrario error_diagnostic = null                        │
│                                                                   │
│ 3. BusquedaHttpClient -> back-busqueda (:8001):                   │
│    Envía query + client_id + tenant_id + extras sanitizados       │
│                                                                   │
│ 4. PromptBuilder:                                                 │
│    System Prompt (Asistente Virtual SaaS)                         │
│    + User Prompt (Contexto opcional + Fragmentos RAG)             │
│                                                                   │
│ 5. LLMGatewayClient -> llm-gateway (:8003):                       │
│    Genera respuesta contextualizada y emite eventos SSE / JSON    │
└─────────────────┬─────────────────────────────────┬───────────────┘
                  │                                 │
                  ▼                                 ▼
   ┌─────────────────────────────┐   ┌─────────────────────────────┐
   │        back-busqueda        │   │         llm-gateway         │
   │  (Documentos y Reglamentos) │   │ (Inferencia + Contabilidad) │
   └─────────────────────────────┘   └─────────────────────────────┘
```
