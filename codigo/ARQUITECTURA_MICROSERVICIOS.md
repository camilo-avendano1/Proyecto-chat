# Arquitectura de Microservicios y Separación de Dependencias

**Desarrollado por:** Juan Camilo Avendaño, Fran Sneider Quincha, Adriana Moreno.  
**Fecha:** Octubre 2026  
**Ecosistema:** SaaS Core Chat & Diagnóstico en Tiempo Real

---

## 1. Visión General de la Separación de Servicios

Para garantizar alta disponibilidad, aislamiento de fallos, auditoría estricta y control de costos de inteligencia artificial, se separaron las dependencias del monolito en tres microservicios FastAPI dedicados, respaldados por un sistema de logs centralizado y un frontend de prueba interactivo:

```mermaid
graph TD
    FM["FRONT-MOCK (React + Vite :5173)"] -->|1. Widget Session Handshake| AS["auth-service (:8002)"]
    FM -->|2. Admin Login (bcrypt + JWT)| AS
    FM -->|3. SSE Chat / Diagnóstico RAG| BC["back-chat (:8000)"]
    FM -->|4. Panel de Observabilidad Admin| BC

    BC -->|X-Internal-Key + Contexto de Atribución| LG["llm-gateway (:8003)"]
    BC -->|Búsqueda RAG Normativa| BB["back-busqueda (:8001)"]

    LG -->|Inferencia OpenAI / LM Studio / Ollama| LLM["Modelos Locales / Cloud"]
    LG -->|Contabilidad de Tokens & Costos| LDB["llm-gateway/data/ledger.db"]

    AS -->|Persistencia JSON / SQLite| LOGS[("Base Central de Logs: data/saas_logs.db")]
    LG -->|Persistencia JSON / SQLite| LOGS
    BC -->|Persistencia JSON / SQLite| LOGS
```

---

## 2. Mapa de Puertos y Responsabilidades

| Microservicio | Puerto | Repositorio / Ruta | Responsabilidades Principales |
|---|---|---|---|
| **`auth-service`** | **8002** | `codigo/auth-service` | • Autenticación de sesiones de widgets (`POST /api/v1/widget/session`).<br>• Registro de empresas/clientes y tenants con hashing SHA-256 de API Keys.<br>• Autenticación de administradores con contraseñas seguras (`bcrypt`).<br>• Control de roles (`SUPERADMIN` vs `CLIENT_ADMIN`), bloqueo temporal tras 5 intentos fallidos (15 min). |
| **`llm-gateway`** | **8003** | `codigo/llm-gateway` | • Aislamiento completo de llamadas a modelos (LM Studio, Ollama, OpenAI).<br>• Segmentación de atribución de llamadas: `client_id`, `tenant_id`, `usuario`, `rol`, `operacion`, `model`.<br>• Medición de tokens reales (`tiktoken`/API) y estimación de costos en USD.<br>• Registro de eventos fast-path (0 tokens consumidos).<br>• Protegido mediante token interno de servicio `X-Internal-Key`. |
| **`back-chat`** | **8000** | `codigo/back-chat` | • Orquestador de asistencia técnica para formularios, formatos y reglamentos.<br>• **System Prompt desacoplado:** define únicamente el rol de asistente técnico para médicos, enfermeros, radicadores y auditores en múltiples formatos (CSV, TXT, XML, JSON, ZIP, formularios web).<br>• **Contexto 100% guiado por Búsqueda (RAG):** las situaciones, documentos y reglamentos provienen de `back-busqueda` (:8001) para darle contexto al LLM en el momento de preguntar.<br>• Anonimización PII / PHI obligatoria (Ley Estatutaria 1581 de 2012 de Habeas Data).<br>• Guardrails de seguridad contra inyecciones de prompt y consultas fuera de dominio.<br>• Extractor genérico de metadatos de logs (fila, campo/variable, código de error, fase CA/CE/CD).<br>• Emisión Server-Sent Events (SSE) con chunks en tiempo real.<br>• Proxy y consulta de logs centrales para panel administrativo. |
| **`FRONT-MOCK`** | **5173** | `codigo/FRONT-MOCK` | • Simulador de widget de chat asistencial.<br>• Autenticación interactiva de administradores.<br>• Panel de observabilidad en vivo: desglose por usuario, rol, tenant, modelo y auditoría de seguridad. |

---

## 3. Sistema Centralizado de Logs y Auditoría

Cada microservicio implementa el motor común `src/core/logging_system.py`:
1. **Logs en Archivos Rotativos JSON Lines:**
   - Ubicación: `<microservicio>/logs/<servicio>.jsonl`
   - Tamaño máximo: 10 MB por archivo, 10 copias de seguridad rotativas.
   - Formato estructurado: `timestamp`, `level`, `service`, `request_id`, `logger`, `message`, `audit_data`.
2. **Base de Datos Centralizada de Auditoría:**
   - Archivo compartido: `codigo/data/saas_logs.db` (SQLite en modo WAL de alto rendimiento y concurrencia sin bloqueos; configurable hacia PostgreSQL mediante `LOGS_DATABASE_URL`).
   - Tablas principales:
     - `security_events`: Bloqueos por inyección de prompts, fallos de autenticación, violaciones de origen, orígenes cruzados.
     - `message_logs`: Entrada y salida de mensajes sanitizados con tokens, latencia en ms, usuario y rol.
     - `system_errors`: Trazas de excepciones con Request ID correlacionado.

---

## 4. Segmentación de Quienes Hacen Consultas a los Modelos

En el **`llm-gateway`** (:8003), cada petición al endpoint `/internal/v1/chat` requiere y registra:
- **`client_id`**: Identificador de la empresa (ej. `sigires`, `otra_empresa`).
- **`tenant_id`**: Identificador de la división o EPS (ej. `eps_sura_01`).
- **`usuario`**: Nombre de usuario del profesional de salud o auditor (ej. `dr.juan.perez`).
- **`rol`**: Perfil de permisos del usuario (`medico`, `auditor`, `radicador`, `superadmin`).
- **`model`**: Modelo de lenguaje utilizado (`local-model`, `gpt-4o-mini`, etc.).
- **`operacion`**: Tipo de consulta (`DIAGNOSTIC_QUERY`, `DIAGNOSTIC_STREAM`, `GREETING_FAST_PATH`, `SECURITY_BLOCKED`).
- **`is_llm_call`**: Booleano que diferencia si se consumió inferencia en el modelo o si fue respondido directamente por los guardrails con 0 tokens.

Endpoints de consulta administrativa en el gateway:
- `GET /api/v1/usage`: Resumen consolidado.
- `GET /api/v1/usage/by-user`: Consumo agrupado por usuario.
- `GET /api/v1/usage/by-role`: Consumo agrupado por rol del llamador.
- `GET /api/v1/usage/by-model`: Rendimiento, llamadas y latencia agrupado por modelo.
- `GET /api/v1/usage/by-tenant`: Facturación y volumen por división/tenant.
- `GET /api/v1/usage/records`: Paginación detallada de transacciones.

---

## 5. Credenciales Sembradas de Prueba

### Administradores (`auth-service` :8002):
| Usuario | Contraseña | Rol | Alcance de Datos |
|---|---|---|---|
| `superadmin` | `AdminSuperSecret2025!` | `SUPERADMIN` | Acceso global a todas las empresas, métricas y logs. |
| `sigires_admin` | `AdminSigires2025!` | `CLIENT_ADMIN` | Acotado estrictamente a la empresa `sigires`. |

### API Keys de Widgets para Clientes:
| Empresa / Cliente | API Key Pública | Orígenes Permitidos |
|---|---|---|
| `sigires` (Procex Software S.A.S) | `pk_live_sigires_8f9a2b1c3d4e5f6a` | `https://sigires.procex.co`, `http://localhost:5173` |
| `otra_empresa` | `pk_live_otra_1a2b3c4d5e6f7a8b` | `https://otra.ejemplo.co`, `http://localhost:5173` |

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
# Suite Auth Service (11 pruebas)
pytest -v d:\Git\SaaS\codigo\auth-service\tests

# Suite LLM Gateway (10 pruebas)
pytest -v d:\Git\SaaS\codigo\llm-gateway\tests

# Suite Back Central Chat (41 pruebas)
pytest -v d:\Git\SaaS\codigo\back-chat\tests
```
**Total de pruebas superadas:** 62 / 62 (100% de éxito).
