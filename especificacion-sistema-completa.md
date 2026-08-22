# Especificación del Sistema — SaaS B2B de Asistencia Inteligente Multi-Tenant

> **Nota para quien lea este documento**: este texto es autocontenido. No asume que el lector (persona o agente de IA) tenga contexto previo de conversaciones anteriores. Todo lo necesario para entender el proyecto está aquí. Donde una decisión aún no está tomada, se marca explícitamente como **[PENDIENTE]** con una recomendación, no se asume nada.

---

## 1. Resumen ejecutivo

Se está desarrollando un **SaaS B2B** llamado provisionalmente **[NOMBRE_PRODUCTO]** (nombre de marca aún no definido — usar este placeholder en todo material hasta que se confirme).

El producto es un **asistente conversacional inteligente embebible** (chatbot con RAG — Retrieval-Augmented Generation) que las empresas pueden integrar en sus propias aplicaciones web mediante un widget. El asistente:
- Guía a los usuarios finales en la navegación de aplicaciones complejas.
- Traduce errores técnicos en explicaciones claras.
- Se nutre de la documentación específica de cada empresa cliente (manuales, formatos, mapas de errores, instrucciones de formularios, etc.).

El modelo de negocio es **multi-tenant de dos niveles de reventa**: el dueño de la plataforma no vende directamente a los usuarios finales de cada empresa, sino a una **empresa revendedora** que a su vez gestiona a sus propios clientes.

---

## 2. Glosario (términos usados en todo el proyecto)

| Término | Significado |
|---|---|
| **Platform** | La plataforma SaaS en sí. Tiene un único dueño/operador. |
| **Super-Admin** | Rol del dueño de la Platform. Ve todo el sistema, todos los Accounts. |
| **Account** | Una empresa que contrata la Platform como revendedor. Gestiona múltiples Tenants propios. En el caso actual, hay **un solo Account** contratado. |
| **Account Admin** | Rol del administrador del Account (el revendedor). Gestiona sus Tenants, API keys, y ve el consumo de estos. |
| **Tenant** | Cada empresa cliente final del Account. Tiene su propia base de conocimiento aislada, su propio widget, sus propias API keys. En el caso actual, el Account tiene **16 Tenants**. |
| **Widget** | Componente de chat embebible que el Tenant instala en su propia página web, para que sus usuarios finales interactúen con el asistente. |
| **RAG (Retrieval-Augmented Generation)** | Técnica que combina búsqueda semántica sobre una base de conocimiento con un modelo de lenguaje (LLM), para generar respuestas basadas en documentos específicos en vez de solo el conocimiento general del modelo. |
| **Chunk** | Fragmento pequeño de un documento, resultado de dividir (trocear) el contenido para poder indexarlo y buscarlo eficientemente. |
| **Embedding** | Representación numérica (vector) de un texto, usada para medir similitud semántica entre una pregunta y los documentos indexados. |
| **Vector DB / Vector Store** | Base de datos especializada en almacenar y buscar embeddings por similitud. |
| **RLS (Row Level Security)** | Mecanismo de PostgreSQL que restringe qué filas puede ver una consulta según el contexto de quien consulta — usado aquí para garantizar que un Tenant nunca vea datos de otro. |

**Jerarquía completa:**

```
Platform (1, el dueño del negocio)
  └── Account (revendedor — actualmente 1 contratado)
        └── Tenant (empresa cliente del revendedor — actualmente 16)
              └── Usuarios finales (empleados/clientes del Tenant que usan el widget)
```

---

## 3. Contexto de negocio

### 3.1 Modelo de venta

- El dueño de la Platform (Super-Admin) vende el servicio completo a **un Account** (empresa revendedora).
- Ese Account ya tiene **16 empresas clientes propias**, que se convierten en los **16 Tenants** dentro del sistema.
- El Account administra esos 16 Tenants de forma **self-service** (los crea, configura y gestiona él mismo desde su propio panel, sin intervención manual del Super-Admin).
- El Super-Admin (dueño de la Platform) **no gestiona los Tenants directamente** — solo supervisa el sistema a nivel global y ve cuánto consume el Account en total.

### 3.2 Modelo de precios (hacia el Account)

- **Cobro fijo**: una tarifa base mensual, relativamente pequeña, por el servicio.
- **Cobro variable**: adicional, basado en:
  - Consumo de infraestructura/servidores.
  - Consumo de tokens de las APIs de modelos de IA (embeddings + generación de respuestas).
- Esto significa que el sistema **debe trackear consumo real y atribuible** desde el primer día (ver sección 6, tracking de uso) — es la base para poder facturar correctamente la parte variable.
- **[PENDIENTE]**: no se ha definido el mecanismo de facturación (manual vs. automatizado/integración con pasarela de pago). Recomendación: para el MVP (3 meses), calcular y mostrar el consumo en el dashboard, pero facturar manualmente fuera del sistema; automatizar facturación en una fase posterior.

### 3.3 Idioma

- El asistente conversacional (widget) responde **únicamente en español**. No se requiere soporte multi-idioma en esta fase.
- Las consolas de administración (dashboards) se asumen también en español, salvo indicación contraria.

### 3.4 Roles del sistema (modelo elegido: "Opción A")

Dos roles activos en el MVP:

| Rol | Quién lo tiene | Qué puede hacer |
|---|---|---|
| `super_admin` | El dueño de la Platform (una sola persona/cuenta en el MVP) | Ver todos los Accounts, su consumo agregado, configurar límites por Account, suspender Accounts |
| `account_admin` | El Account (empresa revendedora) | Crear/editar/suspender sus propios Tenants, gestionar API keys de cada Tenant, subir/gestionar la base de conocimiento de cada Tenant, ver métricas de consumo de sus 16 Tenants |

No existe un tercer rol por Tenant individual en esta fase — cada una de las 16 empresas no tiene login propio en el sistema; es el `account_admin` quien las administra a todas.

### 3.5 Fuera de alcance en esta fase (explícito, para evitar sobre-construcción)

- Login/rol individual por cada una de las 16 empresas Tenant.
- Soporte multi-idioma del asistente.
- Facturación automatizada/integración con pasarela de pago.
- Múltiples Accounts (el sistema se diseña para soportarlo a futuro, pero el MVP opera con uno solo).
- Conectores de fuentes de conocimiento más allá de carga manual de archivos (URL scraping, Confluence, Notion, Drive quedan para una fase posterior — ver plan de backend, sección de conectores).

---

## 4. Alcance funcional (qué se construye)

### 4.1 Widget embebible (frontend del Tenant)
- Script único que cualquier Tenant integra con una línea de `<script>` en su página, sin build tools.
- Se renderiza aislado (Shadow DOM) para no chocar con los estilos de la página host.
- Captura contexto del usuario logueado del Tenant (vía función `identify()`) para personalizar respuestas según rol/página.
- Se autentica mediante API key pública del Tenant + validación de dominio de origen, obteniendo un JWT de sesión de corta duración para las conversaciones reales (detalle completo de este flujo en el documento de backend, sección 5).

### 4.2 Portal de Administración (consola Account Admin)
- Gestión de los 16 Tenants: crear, ver, suspender, configurar dominios permitidos.
- Gestión de API keys por Tenant: generar, revocar.
- Carga y administración de la base de conocimiento por Tenant (Excel, PDF — incluyendo formularios de hasta 300 campos).
- Visualización de métricas de consumo y costos, por Tenant individual y agregadas de los 16.

### 4.3 Panel de Super-Admin
- Vista global de todos los Accounts (en el MVP, uno solo, pero el modelo de datos soporta más).
- Consumo agregado por Account (costos de infraestructura + IA).
- Configuración de límites por Account (máx. de Tenants, máx. de tokens/mes).
- Suspensión de Accounts.

### 4.4 Core RAG (motor de conocimiento)
- Ingesta: carga de archivos → parsing (Excel/PDF) → chunking → generación de embeddings → almacenamiento vectorial, todo aislado por Tenant.
- Retrieval: ante una pregunta del usuario final (vía widget), búsqueda semántica sobre los documentos del Tenant correspondiente, combinada con generación de respuesta vía LLM.
- Aislamiento estricto de datos entre Tenants garantizado a nivel de base de datos (RLS), no solo en código de aplicación.

### 4.5 Tracking de consumo/costos
- Registro de cada operación con costo asociado (embeddings, llamadas al LLM, uso de infraestructura estimado), atribuido a `account_id` y `tenant_id`.
- Es la base tanto para el panel de Super-Admin (consumo por Account) como para la futura facturación variable.

---

## 5. Decisiones técnicas ya tomadas

| Área | Decisión |
|---|---|
| Backend | Java 21 + Spring Boot 3.x, arquitectura hexagonal/clean, monolito modular (no microservicios desde el día 1) |
| Base de datos | PostgreSQL + extensión pgvector (datos relacionales y vectoriales en un solo motor), aislamiento multi-tenant vía Row Level Security |
| Frontend (consolas) | React 18 + TypeScript, Vite, TanStack Query, Tailwind + shadcn/ui |
| Widget | JavaScript vanilla/Preact, bundle propio servido desde CDN, aislado vía Shadow DOM |
| Autenticación consolas | JWT + rol embebido (`super_admin` / `account_admin`) |
| Autenticación widget | API key pública del Tenant (validación de origen) → JWT de sesión de corta duración |
| Cola de procesamiento | RabbitMQ o equivalente gestionado del cloud elegido, para desacoplar la ingesta pesada del request HTTP |

## 6. Decisiones técnicas pendientes (con recomendación)

### 6.1 Proveedor cloud — **[PENDIENTE]**
Preferencia expresada: GCP o AWS, priorizando el más económico. No se ha decidido cuál.

**Recomendación**: a la escala actual (1 Account, 16 Tenants, tráfico bajo), ambos son viables y el costo es comparable si se eligen los servicios equivalentes correctos:
- **GCP**: Cloud Run (backend serverless, escala a cero — atractivo dado el patrón de tráfico bursty descrito), Cloud SQL para Postgres, Pub/Sub como cola. Suele salir más económico en cargas bajas/intermitentes precisamente por el escalado a cero de Cloud Run.
- **AWS**: Fargate o EC2 pequeño, RDS Postgres, SQS. Ecosistema más grande si en el futuro se necesitan más servicios gestionados (ej. Bedrock si se quisiera evaluar modelos alojados en AWS).
- Sugerencia concreta: dado el patrón de tráfico bajo/intermitente descrito para este proyecto, **GCP con Cloud Run tiende a ser más barato** por el escalado a cero real (no pagas cómputo cuando no hay tráfico). Confirmar con una cotización específica antes de comprometerse, los precios cambian.

### 6.2 Proveedor de modelos de IA — **[PENDIENTE]**
Preferencia expresada: OpenAI, Claude o DeepSeek — abierto entre los tres.

**Recomendación**: el backend debe implementar el modelo de IA (tanto LLM de generación como embeddings) detrás de una interfaz/puerto (`LlmProviderPort`, `EmbeddingProviderPort` — ya contemplado en el plan de backend), de forma que **cambiar de proveedor sea un cambio de configuración, no una reescritura**. Esto permite decidir el proveedor definitivo más adelante, o incluso comparar costo/calidad en paralelo durante el desarrollo sin bloquear el trabajo de las demás capas. Criterios sugeridos para decidir: costo por token (DeepSeek suele ser más económico), calidad de respuesta en español (verificar con pruebas reales sobre los documentos del Tenant), y facilidad de integración con Java (SDKs oficiales disponibles para los tres).

### 6.3 Región de datos — resuelto
Es indiferente dónde se alojen los datos (no hay requisito regulatorio de residencia en Colombia/LatAm). Se puede elegir la región más económica o de menor latencia disponible del proveedor cloud elegido.

### 6.4 SLA de disponibilidad — resuelto (no crítico por ahora)
No se ha definido un compromiso de disponibilidad (ej. 99.5% uptime) con el Account. No es un requisito crítico en esta fase. Recomendación: no sobre-invertir en alta disponibilidad compleja (multi-región, failover automático) en el MVP; monitoreo básico y alertas son suficientes por ahora. Revisar si el Account llega a exigir un SLA contractual más adelante.

---

## 7. Cronograma objetivo: 3 meses

El desarrollo de backend (Java) y frontend (React) avanza en **paralelo**, con el backend exponiendo endpoints incrementalmente por fase para que el frontend consuma contra API real lo antes posible.

| Mes | Backend | Frontend | Widget |
|---|---|---|---|
| **Mes 1** | Fundaciones: modelo de datos, RLS, módulo `platform-core` (Accounts/Tenants/Users/roles), auth JWT de consolas | Auth + layout base + control de rutas por rol | Diseño del flujo de autenticación (API key + JWT de sesión) |
| **Mes 2** | Módulo de ingesta RAG (parsing Excel/PDF, chunking, embeddings, pgvector) + módulo de retrieval (búsqueda + generación) | Consola Account Admin: gestión de Tenants, API keys, carga de base de conocimiento con estado de procesamiento | Construcción del bundle del widget (Shadow DOM, `init`/`identify`), integración con endpoint de sesión |
| **Mes 3** | Módulo `widget-gateway` completo (auth del widget, endpoint de chat), `usage-tracking`, aprovisionamiento self-service de Tenants, hardening (rate limiting, CORS dinámico) | Consola Account Admin: métricas de consumo; Consola Super-Admin completa | Integración end-to-end del widget con el flujo de chat real, pruebas con Tenants piloto |

**Nota de riesgo**: el parsing robusto de Excel con formularios de hasta 300 campos y PDFs con distintos formatos es, según el análisis previo, la pieza de mayor incertidumbre de esfuerzo — se recomienda validarla con archivos reales del Account **lo antes posible dentro del Mes 1**, no dejarla para el Mes 2, para detectar temprano si se necesita más tiempo de ingeniería en el parser.

---

## 8. Documentos relacionados

Este documento es el punto de entrada. Para el detalle técnico de implementación, ver:
- `plan-backend-saas-rag.md` — arquitectura, modelo de datos, seguridad del widget, fases de backend en Java.
- `plan-frontend-consolas.md` — arquitectura React, consumo de API, pantallas, fases de frontend.

Ambos documentos comparten el mismo modelo de roles, jerarquía de datos y decisiones descritas aquí. Si hay alguna discrepancia aparente entre este documento y los otros dos, este documento (la especificación) es la fuente de verdad sobre el *qué* y el *por qué*; los otros dos son la fuente de verdad sobre el *cómo* técnico específico de cada capa.
