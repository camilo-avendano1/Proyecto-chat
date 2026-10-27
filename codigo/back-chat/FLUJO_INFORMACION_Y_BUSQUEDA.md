# Flujo de Información, Rol del System Prompt e Integración con Back - Búsqueda (RAG)

Este documento explica cómo procesa la información el microservicio **`back-chat`**, por qué su diseño es general y desacoplado de un caso o reglamento puntual, cuál es la función exacta del **System Prompt**, y cómo **`back-busqueda`** provee dinámicamente las situaciones, documentos y reglamentos para darle contexto al LLM al momento de responder.

---

## 1. Principio Arquitectónico: Desacoplamiento entre Rol y Conocimiento Normativo

El sistema separa estrictamente dos responsabilidades que no deben mezclarse:

1. **El System Prompt ([`PromptBuilder`](src/operations/prompt_builder.py)):**
   - **Solo define el rol y comportamiento del asistente:** actuar como un **Asistente Técnico Especializado** para médicos, enfermeros, radicadores, auditores y analistas que deben diligenciar, validar o subir diferentes formularios y archivos en múltiples formatos (`CSV`, `TXT`, `XML`, `JSON`, `ZIP`, formularios web).
   - **No contiene reglamentos ni variables quemadas:** no asume de antemano una resolución, ni un número fijo de columnas, ni un caso puntual de un cliente.
   - Instruye al LLM a basar su diagnóstico, regla técnica y fundamento normativo **exclusivamente en los documentos y reglamentos recuperados por la búsqueda** e inyectados en el prompt de la consulta.

2. **La Búsqueda Semántica / RAG ([`BusquedaHttpClient`](src/infrastructure/external/busqueda_client.py) -> `back-busqueda`):**
   - **Es la fuente de verdad de situaciones, documentos y reglamentos:** cuando el profesional hace una pregunta o adjunta un log de validación, `back-chat` consulta a `back-busqueda` (`/api/v1/search`) enviando la pregunta sanitizada y los metadatos extraídos del log (fila, campo/variable, código de error, fase/categoría).
   - `back-busqueda` retorna los fragmentos exactos del reglamento, manual o anexo técnico aplicable a ese formulario y cliente, los cuales se inyectan en el **User Prompt** para darle todo el contexto normativo al LLM antes de generar la respuesta.

---

## 2. Etapas del Flujo Interno en `back-chat`

### A. Extracción Genérica de Metadatos de Logs ([`LogParserOperations`](src/operations/log_parser_operations.py))
Cuando el médico, enfermero o radicador adjunta un log de error o describe un fallo:
```text
Fila: 12 | Campo: 6 | Variable 'Signos_Vitales' fuera de rango permitido. Error CE_CAMPO_006_INVAL
```
El parser extrae señales estructurales **sin depender de ningún catálogo normativo fijo**:
- **Fila / Registro afectado:** `12`
- **Campo / Variable afectada:** `6` (y el nombre explícito `'Signos_Vitales'` si viene citado en la traza)
- **Código de Error:** `CE_CAMPO_006_INVAL`
- **Fase y Categoría genérica:**
  - `FASE_1_CA` (`CALIDAD_ARCHIVO_FORMATO`): estructura del archivo, delimitadores, codificación, extensión.
  - `FASE_2_CE` (`CALIDAD_ESTRUCTURA_CAMPOS`): tipos de dato, fechas, rangos, catálogos permitidos.
  - `FASE_3_CD` (`CALIDAD_DATOS_CRUCES_LOGICOS`): coherencia cruzada entre campos clínicos o administrativos.

### B. Consulta al Servicio de Búsqueda (`back-busqueda`)
Con la pregunta y los metadatos extraídos, [`BusquedaHttpClient`](src/infrastructure/external/busqueda_client.py) realiza una petición `POST` a la URL configurada para el cliente (`http://localhost:8001/api/v1/search` por defecto):
- Si `back-busqueda` responde (`200 OK`), sus fragmentos (`chunks` / `results`) se convierten en objetos [`KnowledgeSource`](src/domain/entities.py) y se inyectan directamente en el prompt del LLM.
- **Modo de Contingencia Local (Solo si `back-busqueda` está apagado en desarrollo):** Si el servicio externo no responde y `FALLBACK_LOCAL_SEARCH=true`, se utiliza un banco ligero de contingencia general. Si ninguna palabra clave coincide, retorna una guía técnica general de validación de formularios (nunca fuerza un caso puntual como una variable específica).

### C. Ensamblaje del Prompt ([`PromptBuilder`](src/operations/prompt_builder.py))
- **`build_system_prompt`**: Configura el rol del asistente técnico adaptado al perfil del usuario (`Estimado Dr.`, `Estimado(a) Profesional de Enfermería`, `Estimado Radicador`, `Estimado Auditor`) y establece las reglas de concisión, formato en 4 secciones y guardrails de seguridad.
- **`build_user_prompt`**: Inyecta:
  1. Contexto del cliente y del profesional.
  2. Contexto de la pantalla y formato del formulario activo (`formato_archivo`, `pagina_actual`, `modulo`).
  3. Metadatos técnicos extraídos del log.
  4. **Documentos y reglamentos recuperados de la búsqueda (`knowledge_sources`)** para que el LLM responda con contexto real.

---

## 3. Contrato de Comunicación con `back-busqueda`

### A. Petición enviada desde `back-chat` (Request)

- **Método HTTP:** `POST`
- **URL por defecto:** `http://localhost:8001/api/v1/search`  
  *(o la URL configurada por cliente en `CLIENT_BUSQUEDA_URLS`)*
- **Headers:**  
  - `Content-Type: application/json`
  - `X-Internal-Key: <BUSQUEDA_SERVICE_KEY>`
  - `X-Request-ID: <UUID>`
- **Payload JSON:**
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

### B. Respuesta esperada por `back-chat` (Response)

El microservicio `back-busqueda` responde con código `200 OK` y la lista de fragmentos relevantes bajo `"chunks"` o `"results"`:

```json
{
  "chunks": [
    {
      "title": "Reglamento Técnico de Formularios Clínicos y de Enfermería",
      "scope": "GLOBAL",
      "section": "Validación de Campos Obligatorios y Rangos Fisiológicos",
      "content": "Todo formulario clínico o registro de enfermería debe incluir identificación del profesional, fecha/hora en formato ISO (AAAA-MM-DD HH:MM) y valores dentro de rangos clínicos válidos antes de su radicación.",
      "score": 0.94
    },
    {
      "title": "Manual Operativo de Cargue de Formatos",
      "scope": "ACCOUNT",
      "section": "Reglas de Estructura CSV / Web",
      "content": "El error CE_CAMPO_006_INVAL se presenta cuando el campo numérico de signos vitales contiene unidades de texto o valores fuera de la tabla de referencia.",
      "score": 0.89
    }
  ]
}
```

---

## 4. Diagrama del Flujo de Datos Completo

```
┌───────────────────────────────────────────────────────────────────┐
│   Profesional (Médico / Enfermero / Radicador / Auditor)          │
│   Envía duda o log sobre un formulario en cualquier formato       │
└─────────────────────────────────┬─────────────────────────────────┘
                                  │ POST /api/v1/diagnostic/stream
                                  ▼
┌───────────────────────────────────────────────────────────────────┐
│                      back-chat (FastAPI:8000)                     │
│                                                                   │
│ 1. PIISanitizer + ChatGuardrails:                                 │
│    Protege datos personales (Ley 1581) y filtra saludos/ataques   │
│                                                                   │
│ 2. LogParserOperations (Genérico):                                │
│    Extrae Fila, Campo/Variable, Código de Error y Fase (CA/CE/CD) │
│    sin asumir ningún reglamento fijo                              │
│                                                                   │
│ 3. BusquedaHttpClient -> back-busqueda (:8001):                   │
│    Recupera las situaciones, documentos y reglamentos aplicables  │
│                                                                   │
│ 4. PromptBuilder:                                                 │
│    System Prompt (Rol Asistente Técnico de Formularios)           │
│    + User Prompt (Metadatos del Formulario + Fragmentos RAG)      │
│                                                                   │
│ 5. LLMGatewayClient -> llm-gateway (:8003):                       │
│    Genera respuesta contextualizada y transmite eventos SSE       │
└─────────────────┬─────────────────────────────────┬───────────────┘
                  │                                 │
                  ▼                                 ▼
   ┌─────────────────────────────┐   ┌─────────────────────────────┐
   │        back-busqueda        │   │         llm-gateway         │
   │  (Documentos y Reglamentos) │   │ (Inferencia + Contabilidad) │
   └─────────────────────────────┘   └─────────────────────────────┘
```
