# Core SaaS Chat & Diagnostic Gateway (`back-chat`)
## Orquestador de Asistencia Técnica para Formularios, Formatos y Reglamentos Multi-Cliente

> **Equipo de Desarrollo (Autores):**  
> - **Juan Camilo Avendaño**  
> - **Fran Sneider Quincha**  
> - **Adriana Moreno**  
>
> **Enfoque General y Desacoplado:**  
> Este microservicio actúa como el **Asistente Técnico de Formularios y Reglamentos** para profesionales de la salud y analistas (médicos, enfermeros, radicadores, auditores) a través de múltiples clientes (como **SIGIRES** u otras plataformas).  
> - El **System Prompt** únicamente define el **rol** del asistente técnico frente a los diferentes formularios y formatos que deben diligenciar o subir los usuarios.  
> - Las **situaciones, definiciones de campos, manuales y reglamentos** no están quemados en este servicio: provienen dinámicamente de la búsqueda (**`back-busqueda`**) para darle el contexto exacto al LLM al momento de responder cada pregunta.

---

## 1. Diagrama de Flujo y Enrutamiento Multi-Cliente

```
┌───────────────────────────────────────────────┐
│           Clientes Web / Widget Chat          │
│  - Médicos, Enfermeros, Radicadores, Auditores│
│  - Múltiples formatos (CSV, TXT, XML, JSON)   │
└───────────────────────┬───────────────────────┘
                        │ Handshake + Consultas (REST / SSE)
                        ▼
┌────────────────────────────────────────────────────────────────────────┐
│                      SAAS CORE BACK CENTRAL (back-chat)                │
│  (Desarrollado por: Juan Camilo Avendaño, Fran Sneider, Adriana Moreno)│
│                                                                        │
│  1. Identificación del Cliente y Sesión JWT                            │
│  2. Sanitización PII / PHI (Cumplimiento Ley Estatutaria 1581 de 2012) │
│  3. Guardrails Pre-LLM (Saludos 0 tokens, Bloqueo de Inyecciones)      │
│  4. Extracción Genérica de Metadatos del Log (Fila, Campo, Fase, Error)│
│  5. Búsqueda RAG en `back-busqueda`: recupera documentos y reglamentos │
│  6. Ensamblaje: System Prompt (Rol Técnico) + Contexto de Búsqueda     │
│  7. Inferencia vía `llm-gateway` y Emisión SSE en tiempo real          │
└───────────────┬────────────────────────────────────────┬───────────────┘
                │ Búsqueda de reglamentos/documentos     │ Inferencia + Ledger
                ▼                                        ▼
┌──────────────────────────────┐         ┌──────────────────────────────┐
│    back-busqueda (:8001)     │         │      llm-gateway (:8003)     │
│                              │         │                              │
│ - Devuelve situaciones,      │         │ - LOCAL (LM Studio :1234)    │
│   manuales y reglamentos     │         │ - LOCAL (Ollama :11434)      │
│   según cliente y formulario │         │ - CLOUD (OpenAI / DeepSeek)  │
└──────────────────────────────┘         └──────────────────────────────┘
```

---

## 2. Separación entre el System Prompt y la Búsqueda (`back-busqueda`)

1. **System Prompt ([`src/operations/prompt_builder.py`](src/operations/prompt_builder.py)):**
   - Define exclusivamente la identidad del asistente como soporte técnico para el diligenciamiento y validación de formularios en distintos formatos por parte de médicos, enfermeros, radicadores y auditores.
   - Obliga al modelo a basar sus respuestas en los fragmentos normativos recuperados por la búsqueda sin inventar ni asumir reglamentos que no estén en el contexto.
2. **Parser Genérico de Logs ([`src/operations/log_parser_operations.py`](src/operations/log_parser_operations.py)):**
   - Extrae fila/registro, número o nombre explícito del campo/variable, código de error y fase de validación (`FASE_1_CA` Archivo/Formato, `FASE_2_CE` Estructura/Campos, `FASE_3_CD` Datos/Coherencia) sin usar diccionarios quemados de ninguna norma específica.
3. **Búsqueda de Contexto ([`src/infrastructure/external/busqueda_client.py`](src/infrastructure/external/busqueda_client.py)):**
   - Consulta a `back-busqueda` enviando la pregunta del usuario y los metadatos extraídos en `extras` (`category`, `variable_number`, `error_code`).
   - Los documentos y reglamentos retornados por la búsqueda se inyectan en el prompt del usuario para darle contexto preciso al LLM.

---

## 3. Compatibilidad con Modelos de IA: Local (LM Studio) y Producción

### Opción A: Pruebas en Local con LM Studio (Por Defecto)
1. Abra **LM Studio**, cargue el modelo deseado e inicie el **Local Server** en el puerto `1234`.
2. En el archivo `.env` (tanto en `llm-gateway` como en `back-chat`):
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

```
codigo/back-chat/
├── src/
│   ├── main.py                          # Entrada FastAPI, lifespan, CORS, middleware
│   ├── config.py                        # Configuración Pydantic Settings (.env)
│   ├── domain/                          # Entidades y objetos de valor desacoplados
│   │   ├── entities.py                  # ClientCompany, Tenant, WidgetSession, ErrorDiagnostic, KnowledgeSource
│   │   ├── value_objects.py             # ErrorPhase (CA/CE/CD), Severity, KnowledgeScope, UserRole
│   │   └── exceptions.py                # Excepciones de negocio y seguridad
│   ├── operations/                      # Casos de Uso y Lógica de Orquestación
│   │   ├── interfaces.py                # Protocolos DI (SearchService, LLMService, Repos)
│   │   ├── diagnostic_operations.py     # Orquestador del flujo síncrono y streaming SSE
│   │   ├── guardrails.py                # Fast-path de saludos (0 tokens) y defensa contra Prompt Injection
│   │   ├── log_parser_operations.py     # Extractor genérico de metadatos de logs y formularios
│   │   ├── prompt_builder.py            # System Prompt (rol técnico) + inyección de contexto de búsqueda
│   │   ├── sanitizer_operations.py      # Sanitización PII/PHI (Habeas Data - Ley 1581 de 2012)
│   │   └── session_operations.py        # Handshake multi-cliente, lista blanca y JWT
│   ├── infrastructure/                  # Adaptadores hacia servicios externos
│   │   ├── external/
│   │   │   ├── busqueda_client.py       # Cliente HTTP hacia back-busqueda (+ contingencia neutra)
│   │   │   ├── llm_gateway_client.py    # Cliente HTTP hacia llm-gateway (:8003)
│   │   │   └── llm_client.py            # Cliente HTTP directo OpenAI/LM Studio
│   │   ├── security/                    # Verificación JWT y logger de auditoría
│   │   └── repositories/                # Repositorios en memoria de respaldo
│   ├── models/                          # Esquemas Pydantic v2 (Request/Response)
│   └── routers/                         # Endpoints FastAPI (session, diagnostic, health, admin_logs)
└── tests/                               # Suite automatizada con pytest (41 pruebas)
```

---

## 5. Ejecución y Pruebas

```bash
# Iniciar el servidor en desarrollo
uvicorn src.main:app --reload --port 8000

# Ejecutar suite de pruebas
pytest -v
```
