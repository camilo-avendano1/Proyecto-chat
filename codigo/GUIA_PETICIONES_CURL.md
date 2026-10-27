# Guía de Peticiones cURL y Contratos de Integración de API

**Ecosistema:** SaaS Core Chat & Diagnóstico en Tiempo Real  
**Equipo de Desarrollo:** Juan Camilo Avendaño, Fran Sneider Quincha, Adriana Moreno  
**Fecha:** Octubre 2026  

Este documento contiene la colección completa de peticiones `cURL` para dos audiencias técnicas:
1. **Desarrolladores de APIs de Búsqueda / RAG (`back-busqueda`)**: Contrato que debe implementar cada servicio de búsqueda por empresa/cliente. **Las situaciones, definiciones de campos, documentos y reglamentos provienen exclusivamente de `back-busqueda`**, que alimenta de contexto normativo al LLM en cada consulta.
2. **Consumidores del Chat y Widget (Frontends, Clientes Web)**: Flujo de autenticación (`auth-service`) y consumo del chat síncrono y streaming SSE (`back-chat`), donde el **System Prompt** define únicamente el rol de asistente técnico para los diferentes formularios y formatos (`CSV`, `TXT`, `XML`, `JSON`, `ZIP`, formularios web) que deben subir médicos, enfermeros, radicadores o auditores.

---

## 🗺️ Mapa de URLs y Puertos por Defecto

| Microservicio | Puerto Base | Protocolo / Uso |
|---|---|---|
| **`auth-service`** | `http://localhost:8002` | Handshake de widgets (`POST /session`) y login de administradores (`POST /login`). |
| **`back-chat`** | `http://localhost:8000` | Orquestador de diagnóstico clínico, SSE streaming y proxy de observabilidad. |
| **`back-busqueda`** | `http://localhost:8001` | Motor de búsqueda semántica / vectorial RAG (específico por cliente). |

---

# PARTE 1: Para Desarrolladores de APIs de Búsqueda (`back-busqueda`)

Cuando un usuario envía una consulta o log de error a `back-chat`, este microservicio clasifica el error y realiza una llamada HTTP POST a la API de búsqueda configurada para ese cliente (por defecto `http://localhost:8001/api/v1/search`).

### 1.1 Contrato del Endpoint que deben implementar

- **Método HTTP:** `POST`
- **Ruta:** `/api/v1/search`
- **Content-Type:** `application/json`
- **Autenticación:** cabecera `X-Internal-Key` (clave de servicio compartida con `back-chat`)
- **Timeout esperado por back-chat:** 5.0 segundos

El contrato es **agnóstico al cliente**: tiene un núcleo fijo (`query`, `client_id`, `tenant_id`, `top_k`) y un objeto `extras` con metadatos opcionales que **cambian según el cliente**. Cada API de búsqueda usa los `extras` que entiende e **ignora los demás**.

#### Petición cURL enviada por `back-chat`:

```bash
curl -X POST "http://localhost:8001/api/v1/search" \
  -H "Content-Type: application/json" \
  -H "X-Internal-Key: dev_busqueda_service_key_change_me" \
  -H "X-Request-ID: 3f6c2a9e-1b7d-4c55-9a0e-2d8f1e7b4c10" \
  -d '{
    "query": "Al subir el formulario de enfermería tengo un error de validación en el campo 6 de signos vitales",
    "client_id": "sigires",
    "tenant_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
    "top_k": 4,
    "extras": {
      "category": "CALIDAD_ESTRUCTURA_CAMPOS",
      "variable_number": 6,
      "error_code": "CE_CAMPO_006_INVAL"
    }
  }'
```

Ejemplo para otro cliente (los `extras` son distintos o vienen vacíos):

```bash
curl -X POST "http://localhost:8001/api/v1/search" \
  -H "Content-Type: application/json" \
  -H "X-Internal-Key: dev_busqueda_service_key_change_me" \
  -d '{
    "query": "¿Cómo se aprueba una orden de compra?",
    "client_id": "otra_empresa",
    "tenant_id": "e55f6a7b-8c9d-0e1f-2a3b-4c5d6e7f8a9b",
    "top_k": 4,
    "extras": {}
  }'
```

#### Descripción de los Campos:

| Campo | Tipo | Requerido | Descripción |
|---|---|---|---|
| `query` | `string` | **Sí** | Pregunta del usuario (ya anonimizada: sin PII/PHI). |
| `client_id` | `string` | **Sí** | Cliente corporativo (`sigires`, `otra_empresa`, ...). |
| `tenant_id` | `string` | **Sí** | Tenant/división del cliente. Úselo para aislar los datos. |
| `top_k` | `integer` | No | Máximo de fragmentos a devolver (por defecto `4`). |
| `extras` | `object` | No | Metadatos opcionales propios de cada cliente (ver reglas abajo). |

#### Reglas de seguridad de `extras`

`back-chat` sanea `extras` antes de enviarlo; la API de búsqueda **también debe validarlo** (no confiar en el emisor):

- **Claves:** solo `snake_case`, regex `^[a-z][a-z0-9_]{0,63}$`.
- **Valores:** solo `string`, `number`, `boolean` o listas planas de esos tipos. **Sin objetos anidados ni `null`.**
- **Límites:** máximo 20 claves; strings de máximo 500 caracteres.
- **Uso:** solo como **filtros/boost** de la búsqueda. Nunca concatenarlos en SQL, ni usarlos como nombres de tabla/índice o rutas de archivo; usar consultas parametrizadas.
- **Claves desconocidas:** ignorarlas (no responder con error).
- **Aislamiento:** filtrar **siempre** por `client_id` + `tenant_id`; un `extra` nunca debe ampliar el alcance a otro tenant.

Extras enviados por el extractor genérico de logs de `back-chat`:

| Clave | Tipo | Ejemplo |
|---|---|---|
| `category` | `string` | `CALIDAD_ESTRUCTURA_CAMPOS`, `CALIDAD_ARCHIVO_FORMATO`, `CALIDAD_DATOS_CRUCES_LOGICOS` |
| `variable_number` | `integer` | `6` |
| `error_code` | `string` | `CE_CAMPO_006_INVAL` |

#### Respuestas de error esperadas

| Código | Cuándo |
|---|---|
| `401` | Falta `X-Internal-Key` o es inválida. |
| `422` | Falta `query`/`client_id`/`tenant_id` o `extras` no cumple las reglas. |

Cualquier error o timeout hace que `back-chat` use su base de conocimiento local de contingencia.

---

### 1.2 Respuesta JSON esperada por `back-chat` (HTTP 200 OK)

Su API de búsqueda debe responder con una lista de fragmentos bajo la clave `results` (o alternativamente `chunks`):

```json
{
  "results": [
    {
      "title": "Resolución 202 de 2021 - Anexo Técnico",
      "scope": "GLOBAL",
      "section": "Definición de Variable 14 - Condición de la Usuaria",
      "score": 0.94,
      "snippet": "Variable 14 (Condición de la Usuaria): Valores permitidos: 0 = No aplica, 1 = Gestante, 2 = No gestante. Si la Variable 11 (Sexo) es Masculino ('M'), el valor de la Variable 14 debe ser obligatoriamente '0' (No aplica). Reportar 1 o 2 para sexo masculino provoca rechazo en Fase 2 (CE)."
    },
    {
      "title": "Manual Técnico de Validación SIGIRES",
      "scope": "ACCOUNT",
      "section": "Fase 2: Cruces de Coherencia de Género",
      "score": 0.88,
      "snippet": "El validador de estructura rechaza filas donde Variable 11='M' y Variable 14 presente valores diferentes de '0'. Corrija el registro en el archivo TXT antes de reenviar el paquete ZIP."
    }
  ]
}
```

#### Campos de cada fragmento retornado:
- `title` (o `document_title`): Título de la norma o manual.
- `scope`: Alcance del fragmento (`GLOBAL`, `ACCOUNT` o `TENANT`).
- `section`: Capítulo, anexo o subtítulo de donde se extrajo.
- `score`: Puntuación de relevancia semántica (número entre 0.0 y 1.0).
- `snippet` (o `content`): Texto exacto del fragmento normativo que leerá el LLM para responder.

> **Nota de Resiliencia:** Si `back-busqueda` no está encendido o responde con error/timeout, `back-chat` no se cae; activa automáticamente su banco de conocimiento interno de contingencia.

---

# PARTE 2: Para Consumidores del Chat y Widget (Frontends)

El consumo de las APIs del chat sigue un flujo de **dos pasos**:
1. **Handshake de Sesión**: Se solicita un token temporal JWT al `auth-service`.
2. **Consulta al Chat**: Se envía la consulta al `back-chat` usando el token obtenido en la cabecera `Authorization: Bearer <token>`.

---

### 2.1 Paso 1: Inicialización de Sesión del Widget (`auth-service`)

- **Método:** `POST`
- **URL:** `http://localhost:8002/api/v1/widget/session`
- **Cabeceras obligatorias:**
  - `Content-Type: application/json`
  - `X-Widget-Key: <API_KEY_PUBLICA>`
  - `Origin: <DOMINIO_DEL_FRONTEND>`

#### Petición cURL (Ejemplo con EPS Sura - SIGIRES):

```bash
curl -X POST "http://localhost:8002/api/v1/widget/session" \
  -H "Content-Type: application/json" \
  -H "X-Widget-Key: pk_live_sigires_8f9a2b1c3d4e5f6a" \
  -H "Origin: http://localhost:5173" \
  -d '{
    "client_id": "sigires",
    "origin": "http://localhost:5173",
    "eps_id": "EPS_SURA",
    "ips_code": "631300040301"
  }'
```

#### Respuesta esperada (HTTP 200 OK):

```json
{
  "session_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ3aWRnZXRfc2Vzc2lvbl8...",
  "client_id": "sigires",
  "client_name": "SIGIRES (Procex Software S.A.S)",
  "tenant_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
  "tenant_name": "EPS Sura - Regional Nor-Occidente",
  "expires_in_seconds": 1800
}
```

> **Importante:** Guarde el `session_token` en memoria o en el `sessionStorage` del cliente. Este token tiene una vigencia de 30 minutos (1800 segundos).

---

### 2.2 Paso 2A: Consulta en Streaming en Tiempo Real SSE (`back-chat`) ⭐ (Recomendado)

Permite recibir la respuesta token por token mediante Server-Sent Events (SSE), ideal para la experiencia de tipeo en vivo del widget.

- **Método:** `POST`
- **URL:** `http://localhost:8000/api/v1/diagnostic/stream`
- **Cabeceras:**
  - `Content-Type: application/json`
  - `Authorization: Bearer <SESSION_TOKEN_AQUI>`
  - `Accept: text/event-stream`

#### Petición cURL (Usando la bandera `-N` para evitar almacenamiento en búfer):

```bash
curl -N -X POST "http://localhost:8000/api/v1/diagnostic/stream" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
  -H "Accept: text/event-stream" \
  -d '{
    "query": "¿Por qué me rechaza el cargue en la variable 14 si el paciente es hombre?",
    "system_logs": "ERROR CE_GENERAL_VAL_ERR: Fila 142 - Inconsistencia entre Variable 11 (Sexo: M) y Variable 14 (Condicion Usuaria: 1)",
    "ui_context": {
      "url": "https://sigires.procex.co/carga-archivos/resolucion-202",
      "pagina_actual": "CARGA_ARCHIVOS_202",
      "modulo": "CARGA_ARCHIVOS",
      "active_button_id": "btn_validar_archivo",
      "field_in_focus": "var_014_gestante",
      "estado_cargue_actual": "CON_ERRORES",
      "formato_archivo": "RESOLUCION_202_2021_ZIP"
    },
    "user_context": {
      "usuario": "dr.juan.perez",
      "filial": "EPS Sura - Regional Nor-Occidente",
      "eps": "EPS_SURA",
      "ips_code": "631300040301",
      "ips_nombre": "Clínica Las Américas",
      "permisos": "PERFIL_IPS_RADICADOR"
    },
    "conversation_history": []
  }'
```

#### Eventos emitidos por el flujo SSE:

```text
event: error_diagnostic
data: {"detected_code":"CE_GENERAL_VAL_ERR","error_phase":"FASE_2_CE","affected_variable_number":14,"severity":"BLOCKING"}

event: sources
data: [{"document_title":"Resolución 202 de 2021 - Anexo Técnico","scope":"GLOBAL","section":"Definición de Variable 14"}]

event: chunk
data: {"text":"Estimado "}

event: chunk
data: {"text":"Radicador,\n\n### 1. Diagnóstico:\nEl error "}

event: done
data: {"status":"COMPLETED","tokens":1380,"latency_ms":1200}
```

---

### 2.3 Paso 2B: Consulta Síncrona JSON (`back-chat`)

Para integraciones directas o clientes móviles que prefieran recibir una única respuesta JSON consolidada.

- **Método:** `POST`
- **URL:** `http://localhost:8000/api/v1/diagnostic/query`
- **Cabeceras:**
  - `Content-Type: application/json`
  - `Authorization: Bearer <SESSION_TOKEN_AQUI>`

#### Petición cURL:

```bash
curl -X POST "http://localhost:8000/api/v1/diagnostic/query" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
  -d '{
    "query": "¿Cuál es la regla de la variable 14?",
    "system_logs": null,
    "ui_context": {
      "url": "https://sigires.procex.co/carga-archivos/resolucion-202",
      "pagina_actual": "CARGA_ARCHIVOS_202",
      "modulo": "CARGA_ARCHIVOS",
      "active_button_id": null,
      "field_in_focus": "var_014_gestante",
      "estado_cargue_actual": "NO_APLICA",
      "formato_archivo": "RESOLUCION_202_2021_ZIP"
    },
    "user_context": {
      "usuario": "dr.juan.perez",
      "filial": "EPS Sura - Regional Nor-Occidente",
      "eps": "EPS_SURA",
      "ips_code": "631300040301",
      "ips_nombre": "Clínica Las Américas",
      "permisos": "PERFIL_IPS_RADICADOR"
    },
    "conversation_history": []
  }'
```

#### Respuesta esperada (HTTP 200 OK):

```json
{
  "response": "Estimado Radicador,\n\n### 1. Diagnóstico:\nLa Variable 14 corresponde a la Condición de la Usuaria...\n\n### 2. Regla Técnica:\nSi el Sexo (Var 11) es 'M', el valor debe ser obligatoriamente '0' (No aplica)...\n\n### 3. Pasos de Solución:\n1. Revise los registros con sexo masculino.\n2. Asigne '0' en la variable 14.\n\n### 4. Fundamento Normativo:\nResolución 202 de 2021 - Anexo Técnico.",
  "error_diagnostic": {
    "detected_code": "CE_VAR_014",
    "error_phase": "FASE_2_CE",
    "affected_variable_number": 14,
    "affected_variable_name": "Condición de la Usuaria",
    "affected_row": null,
    "severity": "BLOCKING",
    "category": "CALIDAD_ESTRUCTURA_CAMPOS"
  },
  "sources": [
    {
      "document_title": "Resolución 202 de 2021 - Anexo Técnico",
      "scope": "GLOBAL",
      "section": "Definición de Variable 14 - Condición de la Usuaria"
    }
  ]
}
```

---

# PARTE 3: Para Administradores y Monitoreo (Observabilidad)

El panel administrativo permite consultar consumo de tokens, costos en USD, trazas de mensajes sanitizados y eventos de seguridad.

### 3.1 Login de Administrador (`auth-service`)

- **Método:** `POST`
- **URL:** `http://localhost:8002/api/v1/admin/auth/login`
- **Cabeceras:** `Content-Type: application/json`

#### A. Login como SUPERADMIN (Acceso Global a todos los clientes):

```bash
curl -X POST "http://localhost:8002/api/v1/admin/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "superadmin",
    "password": "AdminSuperSecret2025!"
  }'
```

#### B. Login como CLIENT_ADMIN (Acceso restringido a SIGIRES):

```bash
curl -X POST "http://localhost:8002/api/v1/admin/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "sigires_admin",
    "password": "AdminSigires2025!"
  }'
```

#### Respuesta esperada (HTTP 200 OK):

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "expires_in_seconds": 3600,
  "admin_id": "c1f7b889-1234-4b8a-9f12-9876543210ab",
  "username": "superadmin",
  "role": "SUPERADMIN",
  "client_id": null
}
```

---

### 3.2 Consulta de Métricas de Uso y Costos (`back-chat`)

- **Método:** `GET`
- **URL:** `http://localhost:8000/api/v1/admin/usage/summary`
- **Cabecera:** `Authorization: Bearer <ADMIN_ACCESS_TOKEN>`

```bash
curl -X GET "http://localhost:8000/api/v1/admin/usage/summary" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

---

### 3.3 Consulta de Logs de Seguridad y Guardrails (`back-chat`)

Permite auditar bloqueos por inyección de prompts, consultas fuera de dominio y fallos de autenticación:

- **Método:** `GET`
- **URL:** `http://localhost:8000/api/v1/admin/logs/security?limit=50`
- **Cabecera:** `Authorization: Bearer <ADMIN_ACCESS_TOKEN>`

```bash
curl -X GET "http://localhost:8000/api/v1/admin/logs/security?limit=50" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

---

### 3.4 Consulta de Trazas de Mensajes Sanitizados (`back-chat`)

Permite auditar las consultas realizadas, verificando que los datos PII hayan sido anonimizados:

- **Método:** `GET`
- **URL:** `http://localhost:8000/api/v1/admin/logs/messages?limit=50`
- **Cabecera:** `Authorization: Bearer <ADMIN_ACCESS_TOKEN>`

```bash
curl -X GET "http://localhost:8000/api/v1/admin/logs/messages?limit=50" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

---

# PARTE 4: Verificación de Estado (Health Checks)

Puede usar estas peticiones rápidas para verificar que todos los servicios estén encendidos:

```bash
# 1. Estado del Auth Service
curl -s http://localhost:8002/health

# 2. Estado del Back Central Chat (Verifica conexión con LLM y Auth)
curl -s http://localhost:8000/api/v1/status

# 3. Estado del LLM Gateway
curl -s http://localhost:8003/health
```
