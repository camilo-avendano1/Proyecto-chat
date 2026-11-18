# Arquitectura de Microservicios y Separación de Dependencias

**Desarrollado por:** Juan Camilo Avendaño, Fran Sneider Quincha, Adriana Moreno.  
**Fecha:** Octubre 2026  
**Ecosistema:** SaaS Core Chat & RAG Gateway Multi-Cliente

---

## 1. Visión General de la Separación de Servicios

Para garantizar alta disponibilidad, aislamiento de fallos, auditoría estricta y control de costos de inteligencia artificial entre múltiples clientes y tenants, se separaron las dependencias en tres microservicios FastAPI dedicados, respaldados por una base central de auditoría y un frontend simulador interactivo:

```mermaid
graph TD
    FM["FRONT-MOCK (React + Vite :5173)"] -->|1. Widget Session Handshake| AS["auth-service (:8002)"]
    FM -->|2. Admin Login (bcrypt + JWT)| AS
    FM -->|3. POST /api/v1/chat/stream o /query| BC["back-chat (:8000)"]
    FM -->|4. Panel de Observabilidad Admin| BC

    BC -->|X-Internal-Key + Atribución Multi-Cliente| LG["llm-gateway (:8003)"]
    BC -->|POST /api/v1/search + extras| BB["back-busqueda (:8001)"]

    LG -->|Inferencia OpenAI / LM Studio / Ollama| LLM["Modelos Locales / Cloud"]
    LG -->|Contabilidad de Tokens & Costos| LDB["llm-gateway/data/ledger.db"]

    AS -->|Persistencia JSON / SQLite| LOGS[("Base Central de Logs: data/saas_logs.db")]
    LG -->|Persistencia JSON / SQLite| LOGS
    BC -->|Persistencia JSON / SQLite| LOGS
```

---

## 2. Mapa de Puertos y Responsabilidades

| Microservicio | Puerto | Ruta | Responsabilidades Principales |
|---|---|---|---|
| **`auth-service`** | **8002** | `codigo/auth-service` | • Handshake mínimo de widgets (`POST /api/v1/widget/session`, acepta `{}` u `origin` + `metadata` opcional, además de campos legacy `eps_id`/`ips_code`).<br>• Registro de clientes y tenants con hashing SHA-256 de API Keys.<br>• Autenticación de administradores (`bcrypt`) y gestión vía `POST /api/v1/admin/users`.<br>• Control de roles (`SUPERADMIN` vs `CLIENT_ADMIN`) y bloqueo temporal tras 5 intentos fallidos (15 min). |
| **`llm-gateway`** | **8003** | `codigo/llm-gateway` | • Aislamiento completo de llamadas a modelos (LM Studio, Ollama, OpenAI).<br>• Segmentación de atribución: `client_id`, `tenant_id`, `usuario`, `rol`, `operacion`, `model`.<br>• Medición de tokens reales (`tiktoken`/API) y estimación de costos en USD.<br>• Registro de eventos fast-path (`0` tokens consumidos).<br>• Protegido mediante token interno `X-Internal-Key`. |
| **`back-chat`** | **8000** | `codigo/back-chat` | • Orquestador genérico multi-cliente en `POST /api/v1/chat/stream` y `POST /api/v1/chat/query` (y alias `/api/v1/diagnostic/*` por compatibilidad).<br>• Acepta peticiones mínimas (`{"query": "..."}`) u opcionalmente enriquecidas (`user`, `context`, `logs`, `extras`, `conversation_history`).<br>• **System Prompt desacoplado:** adapta el asistente al cliente sin quemar reglas de negocio.<br>• **Contexto 100% guiado por Búsqueda (RAG):** consulta `back-busqueda` (:8001) enrutando según el `client_id` del JWT.<br>• Anonimización PII / PHI obligatoria (Ley Estatutaria 1581 de 2012) y guardrails pre-LLM.<br>• Extracción condicional de metadatos cuando hay `logs` técnicos (`error_diagnostic: null` si no aplica).<br>• Emisión Server-Sent Events (SSE) y proxy de logs/métricas para administradores. |
| **`FRONT-MOCK`** | **5173** | `codigo/FRONT-MOCK` | • Simulador de widget multi-cliente con cliente genérico por defecto (`otra_empresa`) y ejemplos de clientes específicos (`sigires`).<br>• Soporte de **Modo Petición Mínima** y modo enriquecido (`user`, `context`, `logs`, `extras`).<br>• Inspector SSE en tiempo real y modal administrativo de observabilidad. |

---

## 3. Sistema Centralizado de Logs y Auditoría

Cada microservicio implementa el motor común `src/core/logging_system.py`:
1. **Logs en Archivos Rotativos JSON Lines:**
   - Ubicación: `<microservicio>/logs/<servicio>.jsonl`
   - Tamaño máximo: 10 MB por archivo, 10 copias de seguridad rotativas.
   - Formato estructurado: `timestamp`, `level`, `service`, `request_id`, `logger`, `message`, `audit_data`.
2. **Base de Datos Centralizada de Auditoría:**
   - Archivo compartido: `codigo/data/saas_logs.db` (SQLite en modo WAL; configurable hacia PostgreSQL mediante `LOGS_DATABASE_URL`).
   - Tablas principales:
     - `security_events`: Bloqueos por inyección de prompts, fallos de autenticación, violaciones de origen y consultas fuera de dominio.
     - `message_logs`: Entrada y salida de mensajes sanitizados con tokens, latencia en ms, usuario y rol.
     - `system_errors`: Trazas de excepciones con Request ID correlacionado.

---

## 4. Segmentación de Quienes Hacen Consultas a los Modelos

En el **`llm-gateway`** (:8003), cada petición al endpoint `/internal/v1/chat` registra el contexto de atribución:
- **`client_id`**: Identificador de la empresa cliente (ej. `otra_empresa`, `sigires`).
- **`tenant_id`**: Identificador del tenant o división (ej. `e55f6a7b-8c9d-0e1f-2a3b-4c5d6e7f8a9b`).
- **`usuario`**: Identificador del usuario final (ej. `ana.martinez`, `dr.juan.perez`, o `anonimo` si no se envía `user`).
- **`rol`**: Rol del usuario (`ANALISTA_OPERACIONES`, `ANALISTA_COMPRAS`, `PERFIL_IPS_MEDICO`, `usuario`, etc.).
- **`model`**: Modelo de lenguaje utilizado (`local-model`, `gpt-4o-mini`, etc.).
- **`operacion`**: Tipo de consulta (`CHAT_QUERY`, `CHAT_STREAM`, `FAST_RESPONSE_GREETING`, `SECURITY_BLOCKED`, `OUT_OF_DOMAIN`, etc.).
- **`is_llm_call`**: Booleano que diferencia si hubo inferencia en el modelo o si fue respondido por guardrails/fast-path con `0` tokens.

Endpoints de consulta administrativa en `llm-gateway` (expuestos vía proxy en `back-chat` `/api/v1/admin/usage/*`):
- `GET /api/v1/usage`: Resumen consolidado.
- `GET /api/v1/usage/by-user`: Consumo agrupado por usuario.
- `GET /api/v1/usage/by-role`: Consumo agrupado por rol.
- `GET /api/v1/usage/by-model`: Rendimiento, llamadas y latencia agrupado por modelo.
- `GET /api/v1/usage/by-tenant`: Facturación y volumen por división/tenant.
- `GET /api/v1/usage/records`: Paginación detallada de transacciones.

---

## 5. Credenciales y Clientes Sembrados de Prueba

### Administradores (`auth-service` :8002):
| Usuario | Contraseña Inicial | Rol | Notas |
|---|---|---|---|
| `superadmin` | Valor de `BOOTSTRAP_ADMIN_PASSWORD` en `.env` (`AdminPassword2026!` en `.env.example`) | `SUPERADMIN` | Se crea automáticamente si la tabla de admins está vacía. Acceso global a todas las empresas, métricas y logs. |
| *(Opcional)* `CLIENT_ADMIN` | Definida al crear el usuario | `CLIENT_ADMIN` | No se siembra por defecto; un `SUPERADMIN` puede crearlo vía `POST /api/v1/admin/users` asignándole `client_id` (ej. `otra_empresa` o `sigires`). |

### API Keys de Widgets para Clientes (`auth-service/src/db/seed.py`):
| Empresa / Cliente | Tenant | API Key Pública | Orígenes Permitidos |
|---|---|---|---|
| `otra_empresa` (Entidad Corporativa Externa) | `División Operativa Central` | `pk_live_otraempresa_1a2b3c4d5e6f7a8b` | `*` |
| `sigires` (Procex Software S.A.S) | `EPS Sura - Regional Nor-Occidente` | `pk_live_sigires_8f9a2b1c3d4e5f6a` | `https://sigires.procex.co`, `http://localhost:3000`, `http://localhost:5173` |
| `sigires` (Procex Software S.A.S) | `EPS Sanitas - IPS San Rafael` | `pk_live_sigires_sanitas_7c9d1e2f3a4b` | `https://sigires.procex.co`, `http://localhost:3000`, `http://localhost:5173` |
| `sigires` (Procex Software S.A.S) | `Nueva EPS - Consorcio Salud` | `pk_live_sigires_nuevaeps_9e8d7c6b5a4f` | `https://sigires.procex.co`, `http://localhost:3000`, `http://localhost:5173` |

---

## 6. Instrucciones de Ejecución

Para iniciar todos los servicios simultáneamente en ventanas de terminal independientes:

```powershell
cd d:\Git\SaaS\codigo
.\iniciar-servicios.ps1
```

O para iniciar individualmente:

```powershell
# 1. Auth Service
cd d:\Git\SaaS\codigo\auth-service
$env:DISABLE_SQLALCHEMY_CEXT="1"; uvicorn src.main:app --port 8002 --reload

# 2. LLM Gateway
cd d:\Git\SaaS\codigo\llm-gateway
$env:DISABLE_SQLALCHEMY_CEXT="1"; uvicorn src.main:app --port 8003 --reload

# 3. Back Central Chat
cd d:\Git\SaaS\codigo\back-chat
$env:DISABLE_SQLALCHEMY_CEXT="1"; uvicorn src.main:app --port 8000 --reload

# 4. Frontend Mock
cd d:\Git\SaaS\codigo\FRONT-MOCK
npm run dev
```

### Ejecutar Pruebas Automatizadas:
```powershell
pytest -v d:\Git\SaaS\codigo\auth-service\tests
pytest -v d:\Git\SaaS\codigo\llm-gateway\tests
pytest -v d:\Git\SaaS\codigo\back-chat\tests
```
