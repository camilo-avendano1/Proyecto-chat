# SaaS Core Chat & RAG Gateway Multi-Organización

**Desarrollado por:** Juan Camilo Avendaño, Fran Sneider Quincha, Adriana Moreno  

Plataforma SaaS de asistencia virtual e inteligencia artificial basada en arquitectura de microservicios (**FastAPI + React/Vite**), diseñada para integrarse en **múltiples organizaciones y sectores** (portales corporativos, comercios/tiendas, talleres mecánicos, sucursales, clínicas/IPS, mesas de ayuda y sistemas especializados como **SIGIRES**), conectando cada consulta con su servicio de búsqueda **RAG (`back-busqueda`)**.

---

## 🏛️ Principios de Arquitectura

1. **Contrato Genérico y Petición Mínima (Multi-Organización y Multi-Sede):**
   - El handshake de sesión (`POST /api/v1/widget/session`) funciona con únicamente `X-Widget-Key`, `Origin` y body `{}` (admitiendo `org_id`, `site_code` o `metadata` opcional).
   - Los endpoints principales de chat (`POST /api/v1/chat/stream` y `POST /api/v1/chat/query`) operan con solo `{"query": "..."}` y aceptan opcionalmente `user`, `context`, `logs`, `extras` y `conversation_history`.
   - Se mantienen los alias `POST /api/v1/diagnostic/stream` y `POST /api/v1/diagnostic/query` para compatibilidad retroactiva con integraciones existentes.
2. **System Prompt Desacoplado + Contexto 100% Guiado por Búsqueda (`back-busqueda` / RAG):**
   - El System Prompt define el rol del asistente virtual adaptado a la organización (`org_name`) sin quemar reglas ni catálogos de un negocio puntual en el código.
   - Los documentos, manuales, políticas, definiciones de campos y reglamentos provienen dinámicamente del servicio `back-busqueda` correspondiente a cada `org_id` (con aislamiento adicional por `site_id` y alcance `SITE`, `ORGANIZATION` o `GLOBAL`).
   - El extractor técnico de logs solo puebla `error_diagnostic` cuando se adjuntan trazas (`logs`) o señales técnicas explícitas; en consultas generales retorna `error_diagnostic: null`.
3. **Aislamiento de Microservicios, Seguridad y Auditoría (Ley 1581 de 2012):**
   - Sanitización obligatoria de datos personales/sensibles (PII/PHI) antes de consultar al buscador o al LLM.
   - Guardrails pre-LLM con respuestas directas sin costo (`0` tokens) para saludos/cortesías, bloqueo de Prompt Injection e intercepción fuera de dominio.
   - Contabilidad detallada de tokens, costos y latencia por `org_id`, `site_id`, `site_code`, `usuario`, `rol` y `model` en `llm-gateway`.

---

## 📂 Estructura del Repositorio

Todo el código fuente de los microservicios y la documentación técnica se encuentra organizado dentro del directorio [`codigo/`](codigo/):

```text
SaaS/
├── .gitignore
├── README.md                                  # Descripción general del repositorio
└── codigo/
    ├── ARQUITECTURA_MICROSERVICIOS.md         # Arquitectura detallada, puertos y diagramas
    ├── GUIA_PETICIONES_CURL.md                # Colección de peticiones cURL y contratos REST/SSE
    ├── iniciar-servicios.ps1                  # Script PowerShell para levantar todos los servicios
    ├── auth-service/                          # Puerto 8002: Autenticación JWT, Claves de conexión SHA-256 y Admins (bcrypt)
    ├── back-chat/                             # Puerto 8000: Orquestador chat multi-organización, Guardrails, PII Sanitizer y RAG
    │   ├── README.md                          # Documentación del orquestador back-chat
    │   ├── FLUJO_INFORMACION_Y_BUSQUEDA.md    # Detalle del flujo entre System Prompt, Logs/Extras y back-busqueda
    │   └── prueba.py                          # Script de prueba rápida end-to-end (handshake + chat/stream)
    ├── llm-gateway/                           # Puerto 8003: Gateway de inferencia LLM y Ledger de tokens/costos
    ├── FRONT-MOCK/                            # Puerto 5173: Simulador interactivo del Widget y Observabilidad básica
    │   └── README.md                          # Guía del simulador frontend
    └── front-admin/                           # Puerto 5174: Consola Administrativa multi-organización, Sedes y Documentos
        └── README.md                          # Guía de la consola administrativa
```

---

## 🚀 Inicio Rápido

### 1. Levantar todos los servicios (Windows PowerShell)

```powershell
cd codigo
.\iniciar-servicios.ps1
```

| Servicio | Puerto | Descripción |
|---|---|---|
| **`auth-service`** | `8002` | Handshake de sesiones de widget (`X-Widget-Key`), organizaciones con terminología personalizable (`site_label`/`site_label_plural`), sedes y admins (`GLOBAL_ADMIN` / `ORG_ADMIN`). |
| **`llm-gateway`** | `8003` | Proxy de inferencia hacia LM Studio, Ollama u OpenAI y contabilidad de tokens por organización/sede/usuario/rol. |
| **`back-chat`** | `8000` | Orquestador de chat (`POST /api/v1/chat/stream`, `POST /api/v1/chat/query`), conexión con `back-busqueda` (:8001) y documentos del asistente. |
| **`FRONT-MOCK`** | `5173` | Consola web interactiva para simular peticiones mínimas o enriquecidas entre múltiples organizaciones/sedes y observabilidad básica. |
| **`front-admin`** | `5174` | Consola administrativa (`GLOBAL_ADMIN` / `ORG_ADMIN`) con nomenclatura adaptable (`Sedes`, `Tiendas`, `Talleres`, `IPS`, `Sucursales`), métricas, reportes CSV/JSON, claves de conexión y documentos. |

### 2. Verificación Rápida End-to-End (`prueba.py`)

```bash
cd codigo/back-chat
python prueba.py
```

### 3. Ejecutar Pruebas Automatizadas (`pytest`)

```powershell
# 1. Auth Service
cd codigo/auth-service
$env:DISABLE_SQLALCHEMY_CEXT="1"; pytest -v

# 2. LLM Gateway
cd ../llm-gateway
$env:DISABLE_SQLALCHEMY_CEXT="1"; pytest -v

# 3. Back Central Chat
cd ../back-chat
$env:DISABLE_SQLALCHEMY_CEXT="1"; pytest -v
```

---

## 📖 Documentación Técnica Detallada

- **[Arquitectura de Microservicios](codigo/ARQUITECTURA_MICROSERVICIOS.md)**
- **[Flujo de Información, System Prompt y Búsqueda RAG](codigo/back-chat/FLUJO_INFORMACION_Y_BUSQUEDA.md)**
- **[Guía de Peticiones cURL y Contratos de Integración](codigo/GUIA_PETICIONES_CURL.md)**
- **[Documentación de `back-chat`](codigo/back-chat/README.md)**
- **[Documentación de `FRONT-MOCK`](codigo/FRONT-MOCK/README.md)**
- **[Documentación de `front-admin`](codigo/front-admin/README.md)**
