# Guía de Peticiones cURL y Contratos de Integración de API

**Ecosistema:** SaaS Core Chat & Gateway Multi-Cliente en Tiempo Real  
**Equipo de Desarrollo:** Juan Camilo Avendaño, Fran Sneider Quincha, Adriana Moreno  
**Fecha:** Octubre 2026  

Este documento contiene la colección completa de peticiones `cURL` para tres audiencias técnicas:
1. **Desarrolladores de APIs de Búsqueda / RAG (`back-busqueda`)**: Contrato agnóstico al cliente que debe implementar cada servicio de búsqueda. **El conocimiento específico de cada negocio, documentos, manuales y reglamentos proviene exclusivamente de `back-busqueda`**, que alimenta dinámicamente al LLM en cada consulta.
2. **Consumidores del Chat y Widget (Frontends, Clientes Web)**: Flujo genérico de dos pasos (`auth-service` + `back-chat`) diseñado para funcionar con una petición mínima (`-d '{}'` en sesión y `{"query": "..."}` en chat), además de campos enriquecidos opcionales (`user`, `context`, `logs`, `extras`) y compatibilidad retroactiva para clientes legacy como **SIGIRES**.
3. **Administradores y Observabilidad**: Autenticación administrativa (`SUPERADMIN` / `CLIENT_ADMIN`), creación de usuarios administradores y consulta de métricas y auditoría.

---

## 🗺️ Mapa de URLs y Puertos por Defecto

| Microservicio | Puerto Base | Protocolo / Uso |
|---|---|---|
| **`auth-service`** | `http://localhost:8002` | Handshake de widgets (`POST /api/v1/widget/session`) y auth/gestión de administradores (`POST /api/v1/admin/auth/login`, `POST /api/v1/admin/users`). |
| **`back-chat`** | `http://localhost:8000` | Orquestador de chat multi-cliente (`POST /api/v1/chat/stream`, `POST /api/v1/chat/query`, alias `/api/v1/diagnostic/*`) y proxy de observabilidad. |
| **`back-busqueda`** | `http://localhost:8001` | Motor de búsqueda semántica / vectorial RAG (específico por cliente). |
| **`llm-gateway`** | `http://localhost:8003` | Gateway de inferencia LLM y contabilidad de tokens/costos por cliente, tenant, usuario y rol. |

---

# PARTE 1: Para Desarrolladores de APIs de Búsqueda (`back-busqueda`)

Cuando un usuario envía una consulta a `back-chat`, este microservicio sanitiza datos sensibles (PII/PHI) y realiza una llamada HTTP `POST` a la API de búsqueda configurada para ese cliente (por defecto `http://localhost:8001/api/v1/search`).

### 1.1 Contrato del Endpoint que deben implementar

- **Método HTTP:** `POST`
- **Ruta:** `/api/v1/search`
- **Content-Type:** `application/json`
- **Autenticación:** cabecera `X-Internal-Key` (clave de servicio compartida con `back-chat`)
- **Timeout esperado por `back-chat`:** 5.0 segundos

El contrato es **agnóstico al cliente**: tiene un núcleo fijo (`query`, `client_id`, `tenant_id`, `top_k`) y un objeto `extras` con metadatos opcionales que **cambian según el cliente**. Cada API de búsqueda usa los `extras` que entiende e **ignora los demás**.

#### A. Petición Genérica Mínima (Cliente Corporativo `otra_empresa` con `extras: {}`):

```bash
curl -X POST "http://localhost:8001/api/v1/search" \
  -H "Content-Type: application/json" \
  -H "X-Internal-Key: dev_busqueda_service_key_change_me" \
  -H "X-Request-ID: 3f6c2a9e-1b7d-4c55-9a0e-2d8f1e7b4c10" \
  -d '{
    "query": "¿Cómo se aprueba una orden de compra?",
    "client_id": "otra_empresa",
    "tenant_id": "e55f6a7b-8c9d-0e1f-2a3b-4c5d6e7f8a9b",
    "top_k": 4,
    "extras": {}
  }'
```

#### B. Petición con `extras` Personalizados de Negocio (`otra_empresa`):

Cuando el cliente envía `extras` en `/api/v1/chat/stream` o `/api/v1/chat/query`, `back-chat` los valida y los reenvía a `back-busqueda`:

```bash
curl -X POST "http://localhost:8001/api/v1/search" \
  -H "Content-Type: application/json" \
  -H "X-Internal-Key: dev_busqueda_service_key_change_me" \
  -H "X-Request-ID: 7a1b2c3d-4e5f-6789-abcd-0123456789ef" \
  -d '{
    "query": "¿Cuál es el límite de aprobación para compras de tecnología?",
    "client_id": "otra_empresa",
    "tenant_id": "e55f6a7b-8c9d-0e1f-2a3b-4c5d6e7f8a9b",
    "top_k": 4,
    "extras": {
      "departamento": "compras",
      "nivel_aprobacion": "gerencia",
      "moneda": "COP"
    }
  }'
```

#### C. Ejemplo de Cliente Específico (`sigires` con `extras` extraídos de logs de validación):

Si un cliente adjunta trazas de error técnicas (`logs`), el parser genérico de `back-chat` enriquece `extras` con pistas como `category`, `variable_number` y `error_code`:

```bash
curl -X POST "http://localhost:8001/api/v1/search" \
  -H "Content-Type: application/json" \
  -H "X-Internal-Key: dev_busqueda_service_key_change_me" \
  -H "X-Request-ID: 9c4d8e2f-1a3b-4c5d-8e9f-0a1b2c3d4e5f" \
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

#### Descripción de los Campos:

| Campo | Tipo | Requerido | Descripción |
|---|---|---|---|
| `query` | `string` | **Sí** | Pregunta del usuario (ya anonimizada: sin PII/PHI). |
| `client_id` | `string` | **Sí** | Cliente corporativo (`otra_empresa`, `sigires`, ...). |
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
      "title": "Manual Corporativo de Compras y Aprobaciones",
      "scope": "ACCOUNT",
      "section": "Flujo de Aprobación de Órdenes de Compra",
      "score": 0.94,
      "snippet": "Toda orden de compra debe ser registrada por el analista en el portal de compras, validada por el jefe de área para montos hasta 50 SMMLV y aprobada por Gerencia Administrativa cuando supere dicho umbral."
    },
    {
      "title": "Política de Control Presupuestal",
      "scope": "TENANT",
      "section": "Validación de Centro de Costos",
      "score": 0.87,
      "snippet": "Antes de aprobar la orden, verifique la disponibilidad presupuestal del centro de costos asignado y adjunte al menos dos cotizaciones vigentes."
    }
  ]
}
```

#### Campos de cada fragmento retornado:
- `title` (o `document_title`): Título del documento, guía o manual.
- `scope`: Alcance del fragmento (`GLOBAL`, `ACCOUNT` o `TENANT`).
- `section`: Capítulo, sección o subtítulo de donde se extrajo.
- `score`: Puntuación de relevancia semántica (número entre 0.0 y 1.0).
- `snippet` (o `content`): Texto exacto del fragmento documental que leerá el LLM para responder.

> **Nota de Resiliencia:** Si `back-busqueda` no está encendido o responde con error/timeout, `back-chat` no se cae; activa automáticamente su motor de respaldo local de contingencia.

---

# PARTE 2: Para Consumidores del Chat y Widget (Frontends)

El consumo de las APIs del chat sigue un flujo genérico de **dos pasos**:
1. **Handshake de Sesión**: Se solicita un token temporal JWT al `auth-service` (basta con enviar `X-Widget-Key`, `Origin` y `{}`).
2. **Consulta al Chat**: Se envía la consulta a `back-chat` (`/api/v1/chat/stream` o `/api/v1/chat/query`) usando el token en `Authorization: Bearer <token>`. El único campo obligatorio en el body es `"query"`.

---

### 2.1 Paso 1: Inicialización de Sesión del Widget (`auth-service`)

- **Método:** `POST`
- **URL:** `http://localhost:8002/api/v1/widget/session` *(también disponible vía proxy en `http://localhost:8000/api/v1/widget/session`)*
- **Cabeceras:**
  - `Content-Type: application/json`
  - `X-Widget-Key: <API_KEY_PUBLICA>` (obligatoria; identifica al cliente y tenant)
  - `Origin: <DOMINIO_DEL_FRONTEND>` (obligatoria si no se envía `origin` en el JSON)

#### A. Handshake Mínimo (Recomendado — body vacío `-d '{}'`):

```bash
curl -X POST "http://localhost:8002/api/v1/widget/session" \
  -H "Content-Type: application/json" \
  -H "X-Widget-Key: pk_live_otraempresa_1a2b3c4d5e6f7a8b" \
  -H "Origin: http://localhost:5173" \
  -d '{}'
```

#### B. Handshake con `metadata` Genérica (Opcional):

Permite adjuntar atributos arbitrarios de sesión (división, sede, canal, etc.) que quedan firmados en el JWT:

```bash
curl -X POST "http://localhost:8002/api/v1/widget/session" \
  -H "Content-Type: application/json" \
  -H "X-Widget-Key: pk_live_otraempresa_1a2b3c4d5e6f7a8b" \
  -H "Origin: http://localhost:5173" \
  -d '{
    "origin": "http://localhost:5173",
    "metadata": {
      "division": "compras",
      "sede": "CORP-01",
      "canal": "portal_web"
    }
  }'
```

#### C. Ejemplo Cliente SIGIRES (Compatibilidad con `eps_id` / `ips_code`):

Para integraciones legacy de SIGIRES, los campos opcionales `client_id`, `eps_id` e `ips_code` continúan aceptándose y se incorporan automáticamente a los metadatos de la sesión:

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
  "session_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJlNTVmNmE3Yi0...",
  "client_id": "otra_empresa",
  "client_name": "Entidad Corporativa Externa",
  "tenant_id": "e55f6a7b-8c9d-0e1f-2a3b-4c5d6e7f8a9b",
  "tenant_name": "División Operativa Central",
  "expires_in_seconds": 1800
}
```

> **Importante:** Guarde el `session_token` en memoria o en `sessionStorage`. Tiene vigencia de 30 minutos (`1800` segundos).

---

### 2.2 Paso 2A: Consulta en Streaming en Tiempo Real SSE (`back-chat`) ⭐ (Recomendado)

Permite recibir la respuesta token por token mediante Server-Sent Events (SSE).

- **Método:** `POST`
- **URL:** `http://localhost:8000/api/v1/chat/stream`
- **Cabeceras:**
  - `Content-Type: application/json`
  - `Authorization: Bearer <SESSION_TOKEN_AQUI>`
  - `Accept: text/event-stream`

#### A. Petición Mínima (Únicamente `query` — Recomendada para integraciones nuevas):

Use la bandera `-N` de `curl` para deshabilitar el almacenamiento en búfer:

```bash
curl -N -X POST "http://localhost:8000/api/v1/chat/stream" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <SESSION_TOKEN_AQUI>" \
  -H "Accept: text/event-stream" \
  -d '{
    "query": "¿Cómo se aprueba una orden de compra?"
  }'
```

#### B. Petición Enriquecida Opcional (`user`, `context`, `logs`, `extras`, `conversation_history`):

Todos los campos adicionales son opcionales; envíe únicamente los que apliquen a su plataforma:

```bash
curl -N -X POST "http://localhost:8000/api/v1/chat/stream" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <SESSION_TOKEN_AQUI>" \
  -H "Accept: text/event-stream" \
  -d '{
    "query": "¿Cuál es el límite de aprobación para compras de tecnología?",
    "user": {
      "id": "ana.martinez",
      "role": "ANALISTA_COMPRAS",
      "organization": "División Operativa Central",
      "unit_code": "CORP-01"
    },
    "context": {
      "url": "https://portal.empresa.com/compras/ordenes",
      "view": "APROBACION_ORDENES",
      "module": "COMPRAS",
      "status": "EN_REVISION"
    },
    "extras": {
      "departamento": "compras",
      "nivel_aprobacion": "gerencia",
      "moneda": "COP"
    },
    "conversation_history": []
  }'
```

#### C. Ejemplo Cliente SIGIRES + Alias de Compatibilidad (`/api/v1/diagnostic/stream`):

> **Nota de Compatibilidad:** Las rutas anteriores `POST /api/v1/diagnostic/stream` y `POST /api/v1/diagnostic/query` (así como los campos legacy `system_logs`, `ui_context`, `user_context`) siguen disponibles como alias retrocompatibles para clientes SIGIRES ya integrados. Para nuevas integraciones utilice `/api/v1/chat/stream` y `/api/v1/chat/query`.

```bash
curl -N -X POST "http://localhost:8000/api/v1/chat/stream" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <SESSION_TOKEN_SIGIRES>" \
  -H "Accept: text/event-stream" \
  -d '{
    "query": "¿Por qué me rechaza el cargue en la variable 14 si el paciente es hombre?",
    "logs": "ERROR CE_GENERAL_VAL_ERR: Fila 142 - Inconsistencia entre Variable 11 (Sexo: M) y Variable 14 (Condicion Usuaria: 1)",
    "user": {
      "id": "dr.juan.perez",
      "role": "PERFIL_IPS_RADICADOR",
      "organization": "EPS_SURA",
      "unit_code": "631300040301"
    },
    "context": {
      "url": "https://sigires.procex.co/carga-archivos/resolucion-202",
      "view": "CARGA_ARCHIVOS_202",
      "module": "CARGA_ARCHIVOS",
      "file_format": "RESOLUCION_202_2021_ZIP",
      "status": "CON_ERRORES"
    }
  }'
```

#### Eventos emitidos por el flujo SSE:

En consultas generales sin logs técnicos, `error_diagnostic` se emite como `null`:

```text
event: chunk
data: {"text":"Según el Manual "}

event: chunk
data: {"text":"Corporativo de Compras, las órdenes requieren..."}

event: error_diagnostic
data: null

event: sources
data: [{"document_title":"Manual Corporativo de Compras y Aprobaciones","scope":"ACCOUNT","section":"Flujo de Aprobación de Órdenes de Compra"}]

event: done
data: {"status":"COMPLETED"}
```

Cuando la petición incluye trazas técnicas (`logs`) o detección de error estructurado, `error_diagnostic` se puebla con el detalle extraído (`detected_code`, `error_phase`, `affected_variable_number`, `affected_row`, `severity`, `category`).

---

### 2.3 Paso 2B: Consulta Síncrona JSON (`back-chat`)

Para integraciones backend-to-backend, bots o clientes móviles que prefieran recibir una única respuesta JSON consolidada.

- **Método:** `POST`
- **URL:** `http://localhost:8000/api/v1/chat/query` *(alias legacy compatible: `POST http://localhost:8000/api/v1/diagnostic/query`)*
- **Cabeceras:**
  - `Content-Type: application/json`
  - `Authorization: Bearer <SESSION_TOKEN_AQUI>`

#### A. Petición Mínima (Solo `query`):

```bash
curl -X POST "http://localhost:8000/api/v1/chat/query" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <SESSION_TOKEN_AQUI>" \
  -d '{
    "query": "¿Cómo se aprueba una orden de compra?"
  }'
```

#### Respuesta esperada (HTTP 200 OK — consulta general sin logs):

```json
{
  "response": "Según el Manual Corporativo de Compras y Aprobaciones, toda orden debe registrarse en el portal de compras, validarse por el jefe de área (hasta 50 SMMLV) y aprobarse por Gerencia Administrativa si supera dicho umbral.",
  "error_diagnostic": null,
  "sources": [
    {
      "document_title": "Manual Corporativo de Compras y Aprobaciones",
      "scope": "ACCOUNT",
      "section": "Flujo de Aprobación de Órdenes de Compra"
    }
  ]
}
```

#### B. Petición Enriquecida Opcional (`user`, `context`, `logs`, `extras`):

```bash
curl -X POST "http://localhost:8000/api/v1/chat/query" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <SESSION_TOKEN_AQUI>" \
  -d '{
    "query": "Al cargar el archivo de órdenes me rechaza la fila 12 por el campo 6",
    "logs": "Fila: 12 | Campo: 6 | Variable '\''Centro_Costo'\'' fuera de catálogo. Error CE_CAMPO_006_INVAL",
    "user": {
      "id": "ana.martinez",
      "role": "ANALISTA_COMPRAS",
      "organization": "División Operativa Central",
      "unit_code": "CORP-01"
    },
    "context": {
      "url": "https://portal.empresa.com/compras/ordenes",
      "view": "APROBACION_ORDENES",
      "module": "COMPRAS",
      "file_format": "ORDEN_COMPRA_CSV",
      "status": "CON_ERRORES"
    },
    "extras": {
      "departamento": "compras"
    },
    "conversation_history": []
  }'
```

#### C. Ejemplo Cliente SIGIRES (con alias `/api/v1/diagnostic/query`):

```bash
curl -X POST "http://localhost:8000/api/v1/diagnostic/query" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <SESSION_TOKEN_SIGIRES>" \
  -d '{
    "query": "¿Cuál es la regla de la variable 14?",
    "logs": "Fila: 142 | Campo: 14 | Variable '\''Condicion_Usuaria'\'' incompatible con sexo reportado. Error CE_VAR_014_INVAL",
    "user": {
      "id": "dr.juan.perez",
      "role": "PERFIL_IPS_RADICADOR",
      "organization": "EPS_SURA",
      "unit_code": "631300040301"
    },
    "context": {
      "url": "https://sigires.procex.co/carga-archivos/resolucion-202",
      "view": "CARGA_ARCHIVOS_202",
      "module": "CARGA_ARCHIVOS",
      "file_format": "RESOLUCION_202_2021_ZIP",
      "status": "CON_ERRORES"
    }
  }'
```

Cuando la consulta incluye logs técnicos, `error_diagnostic` retorna el objeto estructurado:

```json
{
  "response": "...",
  "error_diagnostic": {
    "detected_code": "CE_VAR_014_INVAL",
    "error_phase": "FASE_2_CE",
    "affected_variable_number": 14,
    "affected_variable_name": "Condicion_Usuaria",
    "affected_row": 142,
    "severity": "BLOCKING",
    "category": "CALIDAD_ESTRUCTURA_CAMPOS"
  },
  "sources": [
    {
      "document_title": "Anexo Técnico Normativo - Reglas de Coherencia por Sexo y Condición",
      "scope": "GLOBAL",
      "section": "Validación de Campo Condición de la Usuaria / Gestante (Campo 14)"
    }
  ]
}
```

---

# PARTE 3: Para Administradores y Monitoreo (Observabilidad)

El panel administrativo permite consultar consumo de tokens, costos en USD, trazas de mensajes sanitizados y eventos de seguridad con aislamiento por `client_id`.

### 3.1 Login y Gestión de Administradores (`auth-service`)

- **Nota de Seguridad / Bootstrap:** Al iniciar `auth-service` con una base de datos vacía, el primer `SUPERADMIN` (`BOOTSTRAP_ADMIN_USERNAME`, por defecto `superadmin`) se siembra usando la contraseña configurada en `BOOTSTRAP_ADMIN_PASSWORD` dentro de `codigo/auth-service/.env` (`AdminPassword2026!` en `.env.example`, o el valor configurado en su entorno; si se deja vacío, se genera una contraseña aleatoria en los logs de arranque).
- Los usuarios `CLIENT_ADMIN` (restringidos a un `client_id` específico, como `otra_empresa` o `sigires`) **no se siembran automáticamente**; un `SUPERADMIN` debe crearlos mediante `POST /api/v1/admin/users`.

#### A. Login como `SUPERADMIN` (Acceso Global a todos los clientes):

```bash
curl -X POST "http://localhost:8002/api/v1/admin/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "superadmin",
    "password": "AdminPassword2026!"
  }'
```

#### Respuesta esperada (HTTP 200 OK):

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in_seconds": 3600,
  "admin_id": "c1f7b889-1234-4b8a-9f12-9876543210ab",
  "username": "superadmin",
  "role": "SUPERADMIN",
  "client_id": null
}
```

#### B. Crear un Administrador de Cliente (`CLIENT_ADMIN`) con `SUPERADMIN`:

```bash
curl -X POST "http://localhost:8002/api/v1/admin/users" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <SUPERADMIN_ACCESS_TOKEN>" \
  -d '{
    "username": "empresa_admin",
    "password": "ClientAdminPass2026!",
    "role": "CLIENT_ADMIN",
    "client_id": "otra_empresa",
    "full_name": "Administrador Entidad Corporativa"
  }'
```

#### C. Login como `CLIENT_ADMIN` (Acceso restringido a su `client_id`):

```bash
curl -X POST "http://localhost:8002/api/v1/admin/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "empresa_admin",
    "password": "ClientAdminPass2026!"
  }'
```

---

### 3.2 Consulta de Métricas de Uso y Costos (`back-chat`)

- **Método:** `GET`
- **URL:** `http://localhost:8000/api/v1/admin/usage/summary`
- **Cabecera:** `Authorization: Bearer <ADMIN_ACCESS_TOKEN>`

```bash
curl -X GET "http://localhost:8000/api/v1/admin/usage/summary" \
  -H "Authorization: Bearer <ADMIN_ACCESS_TOKEN>"
```

También están disponibles los desgloses por usuario (`/usage/by-user`), rol (`/usage/by-role`), modelo (`/usage/by-model`) y tenant (`/usage/by-tenant`).

---

### 3.3 Consulta de Logs de Seguridad y Guardrails (`back-chat`)

Permite auditar bloqueos por inyección de prompts, consultas fuera de dominio y fallos de autenticación:

- **Método:** `GET`
- **URL:** `http://localhost:8000/api/v1/admin/logs/security?limit=50`
- **Cabecera:** `Authorization: Bearer <ADMIN_ACCESS_TOKEN>`

```bash
curl -X GET "http://localhost:8000/api/v1/admin/logs/security?limit=50" \
  -H "Authorization: Bearer <ADMIN_ACCESS_TOKEN>"
```

---

### 3.4 Consulta de Trazas de Mensajes Sanitizados (`back-chat`)

Permite auditar las consultas realizadas, verificando que los datos PII hayan sido anonimizados:

- **Método:** `GET`
- **URL:** `http://localhost:8000/api/v1/admin/logs/messages?limit=50`
- **Cabecera:** `Authorization: Bearer <ADMIN_ACCESS_TOKEN>`

```bash
curl -X GET "http://localhost:8000/api/v1/admin/logs/messages?limit=50" \
  -H "Authorization: Bearer <ADMIN_ACCESS_TOKEN>"
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
