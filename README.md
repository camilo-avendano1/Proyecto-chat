# SaaS Core Chat, Diagnóstico Técnico & Gateway Multi-Cliente

**Desarrollado por:** Juan Camilo Avendaño, Fran Sneider Quincha, Adriana Moreno  

Plataforma SaaS de asistencia técnica e inteligencia artificial basada en arquitectura de microservicios (**FastAPI + React/Vite**), diseñada para orientar a **médicos, enfermeros, radicadores, auditores y analistas** en el diligenciamiento, validación y cargue de **diferentes formularios y archivos en múltiples formatos** (`CSV`, `TXT`, `XML`, `JSON`, `ZIP`, formularios web) conforme a sus reglamentos técnicos.

---

## 🏛️ Principios de Arquitectura

1. **System Prompt Desacoplado (Rol de Asistente Técnico):**
   - El System Prompt define exclusivamente el rol del asistente como soporte técnico para el diligenciamiento y validación de formularios en distintos formatos.
   - No contiene reglamentos ni catálogos de variables quemados en el código.
2. **Contexto Normativo 100% Guiado por Búsqueda (`back-busqueda` / RAG):**
   - Las situaciones específicas, definiciones de campos/variables, manuales operativos y reglamentos provienen dinámicamente del servicio de búsqueda (`back-busqueda`) para darle contexto preciso al LLM en el momento de preguntar.
3. **Aislamiento de Microservicios, Seguridad y Auditoría (Ley 1581 de 2012):**
   - Sanitización obligatoria de datos personales/clínicos (PII/PHI) antes de consultar al buscador o al LLM.
   - Guardrails pre-LLM con respuesta rápida (0 tokens) para saludos/cortesías y bloqueo de Prompt Injection.
   - Contabilidad detallada de tokens, costos y latencia por cliente, tenant, usuario, rol y modelo.

---

## 📂 Estructura del Repositorio

Todo el código fuente de los microservicios y la documentación técnica se encuentra organizado dentro del directorio [`codigo/`](codigo/):

```text
Proyecto-chat/
├── .gitignore
├── README.md                                  # Descripción general del repositorio
└── codigo/
    ├── ARQUITECTURA_MICROSERVICIOS.md         # Arquitectura detallada, puertos y diagramas
    ├── GUIA_PETICIONES_CURL.md                # Colección de peticiones cURL y contratos REST/SSE
    ├── iniciar-servicios.ps1                  # Script PowerShell para levantar todos los servicios
    ├── auth-service/                          # Puerto 8002: Autenticación JWT, API Keys SHA-256 y Admins (bcrypt)
    ├── back-chat/                             # Puerto 8000: Orquestador técnico, Guardrails, PII Sanitizer y RAG
    │   ├── README.md                          # Documentación del orquestador back-chat
    │   └── FLUJO_INFORMACION_Y_BUSQUEDA.md    # Detalle del flujo entre System Prompt, Logs y back-busqueda
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
| **`auth-service`** | `8002` | Handshake de sesiones de widget (`X-Widget-Key`) y login administrativo (`SUPERADMIN` / `CLIENT_ADMIN`). |
| **`llm-gateway`** | `8003` | Proxy de inferencia hacia LM Studio, Ollama u OpenAI y contabilidad de tokens por usuario/rol/tenant. |
| **`back-chat`** | `8000` | Orquestador de asistencia técnica de formularios, conexión con `back-busqueda` (:8001) y streaming SSE. |
| **`FRONT-MOCK`** | `5173` | Consola web interactiva para simular escenarios de formularios, formatos, perfiles y observabilidad. |

### 2. Ejecutar Pruebas Automatizadas (`pytest`)

```powershell
# 1. Auth Service (11 pruebas)
cd codigo/auth-service
$env:DISABLE_SQLALCHEMY_CEXT="1"; pytest -v

# 2. LLM Gateway (10 pruebas)
cd ../llm-gateway
$env:DISABLE_SQLALCHEMY_CEXT="1"; pytest -v

# 3. Back Central Chat (41 pruebas)
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
