# SaaS Core Chat & RAG Gateway Multi-Cliente

**Desarrollado por:** Juan Camilo Avendaño, Fran Sneider Quincha, Adriana Moreno  

Plataforma SaaS de asistencia virtual e inteligencia artificial basada en arquitectura de microservicios (**FastAPI + React/Vite**), diseñada para integrarse en **múltiples empresas y plataformas cliente** (portales corporativos, bases de conocimiento internas, mesas de ayuda y sistemas especializados como **SIGIRES**), conectando cada consulta con su servicio de búsqueda **RAG (`back-busqueda`)**.

---

## 🏛️ Principios de Arquitectura

1. **Contrato Genérico y Petición Mínima (Multi-Cliente):**
   - El handshake de sesión (`POST /api/v1/widget/session`) funciona con únicamente `X-Widget-Key`, `Origin` y body `{}` (admitiendo `metadata` opcional o compatibilidad legacy con `eps_id` / `ips_code`).
   - Los endpoints principales de chat (`POST /api/v1/chat/stream` y `POST /api/v1/chat/query`) operan con solo `{"query": "..."}` y aceptan opcionalmente `user`, `context`, `logs`, `extras` y `conversation_history`.
   - Se mantienen los alias `POST /api/v1/diagnostic/stream` y `POST /api/v1/diagnostic/query` para compatibilidad retroactiva con integraciones existentes.
2. **System Prompt Desacoplado + Contexto 100% Guiado por Búsqueda (`back-busqueda` / RAG):**
   - El System Prompt define el rol del asistente virtual adaptado al cliente (`client_name`) sin quemar reglas ni catálogos de un negocio puntual en el código.
   - Los documentos, manuales, políticas, definiciones de campos y reglamentos provienen dinámicamente del servicio `back-busqueda` correspondiente a cada `client_id`.
   - El extractor técnico de logs solo puebla `error_diagnostic` cuando se adjuntan trazas (`logs`) o señales técnicas explícitas; en consultas generales retorna `error_diagnostic: null`.
3. **Aislamiento de Microservicios, Seguridad y Auditoría (Ley 1581 de 2012):**
   - Sanitización obligatoria de datos personales/sensibles (PII/PHI) antes de consultar al buscador o al LLM.
   - Guardrails pre-LLM con respuesta rápida (`0` tokens) para saludos/cortesías, bloqueo de Prompt Injection e intercepción fuera de dominio.
   - Contabilidad detallada de tokens, costos y latencia por `client_id`, `tenant_id`, `usuario`, `rol` y `model` en `llm-gateway`.

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
    ├── auth-service/                          # Puerto 8002: Autenticación JWT, API Keys SHA-256 y Admins (bcrypt)
    ├── back-chat/                             # Puerto 8000: Orquestador chat multi-cliente, Guardrails, PII Sanitizer y RAG
    │   ├── README.md                          # Documentación del orquestador back-chat
    │   ├── FLUJO_INFORMACION_Y_BUSQUEDA.md    # Detalle del flujo entre System Prompt, Logs/Extras y back-busqueda
    │   └── prueba.py                          # Script de prueba rápida end-to-end (handshake + chat/stream)
    ├── llm-gateway/                           # Puerto 8003: Gateway de inferencia LLM y Ledger de tokens/costos
    └── FRONT-MOCK/                            # Puerto 5173: Simulador interactivo del Widget y Panel Admin
        └── README.md                          # Guía del simulador frontend
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
| **`auth-service`** | `8002` | Handshake de sesiones de widget (`X-Widget-Key`) y login/gestión de administradores (`SUPERADMIN` / `CLIENT_ADMIN`). |
| **`llm-gateway`** | `8003` | Proxy de inferencia hacia LM Studio, Ollama u OpenAI y contabilidad de tokens por cliente/tenant/usuario/rol. |
| **`back-chat`** | `8000` | Orquestador de chat multi-cliente (`POST /api/v1/chat/stream`, `POST /api/v1/chat/query`), conexión con `back-busqueda` (:8001) y SSE. |
| **`FRONT-MOCK`** | `5173` | Consola web interactiva para simular peticiones mínimas o enriquecidas entre múltiples clientes y panel de observabilidad. |

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
