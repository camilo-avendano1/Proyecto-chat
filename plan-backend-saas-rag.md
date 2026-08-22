# Plan de Desarrollo — Backend (Java)
## SaaS B2B de Asistencia Inteligente Multi-Tenant (RAG)

> **Contexto del proyecto (para agentes o lectores sin contexto previo)**
> Producto SaaS B2B llamado provisionalmente **[NOMBRE_PRODUCTO]**: un asistente conversacional embebible (widget de chat con RAG) que empresas ("Tenants") integran en sus propias páginas web para guiar navegación y explicar errores técnicos, usando su propia documentación indexada.
> Jerarquía: **Platform** (dueño de la plataforma, rol `super_admin`) → **Account** (empresa revendedora que compra la plataforma; en este proyecto hay un solo Account) → **Tenant** (cada empresa cliente del Account; actualmente 16). Modelo de roles "Opción A": el `account_admin` gestiona directamente sus 16 Tenants y las API keys de estos, sin login propio por Tenant.
> El asistente responde solo en español. Plazo objetivo de desarrollo: 3 meses, en paralelo con el frontend (ver `plan-frontend-consolas.md`).
> Para el contexto de negocio completo (modelo de precios, decisiones pendientes de cloud/IA, cronograma detallado), ver `especificacion-sistema-completa.md` — ese documento es la fuente de verdad sobre el *qué* y el *por qué*; este documento es la fuente de verdad sobre el *cómo* técnico del backend.

---

## 1. Objetivo del backend

Construir el core de microservicios que soporta:
- Jerarquía Platform → Account → Tenant (roles: `super_admin`, `account_admin`)
- RAG aislado por tenant (ingesta + retrieval)
- API pública para el widget embebible
- Tracking de consumo/costos con roll-up jerárquico
- Aprovisionamiento self-service de tenants por parte del Account admin

---

## 2. Arquitectura general

### 2.1 Estilo arquitectónico

Se recomienda **Arquitectura Hexagonal (Ports & Adapters) + principios de Clean Architecture**, organizada como **monolito modular** al inicio (no microservicios desde el día 1).

**Por qué monolito modular y no microservicios desde ya:**
- Con 1 cliente revendedor y 16 tenants, el tráfico no justifica la complejidad operativa de microservicios (orquestación, service discovery, tracing distribuido).
- Un monolito modular con **límites de módulo estrictos** (paquetes que no se pueden importar entre sí libremente) te da el mismo beneficio de organización y te deja **extraer servicios reales más adelante** sin reescribir lógica de negocio — solo mueves el módulo a su propio deployable.
- La lógica de negocio (dominio) queda desacoplada de frameworks desde el inicio, que es lo que realmente facilita esa futura extracción.

Cuando el volumen lo justifique (más de un Account revendedor, tráfico alto, necesidad de escalar el pipeline de ingesta independiente del API de queries), separas primero el **módulo de ingesta/RAG** como servicio aparte — es el candidato más natural porque tiene un patrón de carga distinto (bursty) al resto.

### 2.2 Capas (por módulo)

```
com.tuempresa.plataforma
│
├── domain/              ← Entidades, value objects, reglas de negocio puras
│                           NO depende de Spring, JPA, ni ningún framework
│
├── application/         ← Casos de uso (use cases / services de aplicación)
│                           Orquesta el dominio. Define "puertos" (interfaces)
│                           que necesita hacia afuera (ej. VectorStorePort,
│                           EmbeddingProviderPort, TenantRepositoryPort)
│
├── infrastructure/       ← Adaptadores concretos: implementaciones JPA,
│                           clientes HTTP a APIs externas (Voyage/Claude),
│                           implementación de pgvector, colas (RabbitMQ/SQS)
│
└── api/                  ← Controllers REST, DTOs, mappers, seguridad,
                            manejo de excepciones HTTP
```

**Regla de dependencia (la más importante de Clean Architecture):**
`api` → `application` → `domain`
`infrastructure` → `application` (implementa los puertos que `application` define)

El dominio nunca sabe que existe Spring, JPA o una API REST. Esto es lo que te permite testear reglas de negocio sin levantar contexto de Spring ni base de datos.

### 2.3 Módulos funcionales (dentro del monolito modular)

```
platform-core/       → gestión de Accounts, Tenants, usuarios, roles
knowledge-ingestion/ → parsing, chunking, embeddings, escritura a vector store
knowledge-retrieval/ → búsqueda semántica + generación (RAG query time)
widget-gateway/      → API pública que consume el widget (auth, contexto, chat)
usage-tracking/      → logging y agregación de consumo/costos
```

Cada módulo con su propio paquete raíz, su propio `domain`/`application`/`infrastructure`. Un módulo solo se comunica con otro a través de interfaces publicadas explícitamente (no accediendo directo a sus repositorios internos) — esto es lo que preserva la posibilidad de separarlos en servicios reales después.

---

## 3. Stack tecnológico recomendado

| Componente | Elección | Motivo |
|---|---|---|
| Lenguaje/Framework | Java 21 LTS + Spring Boot 3.x | Ecosistema maduro, virtual threads (Java 21) ayudan con I/O concurrente (llamadas a APIs de IA) |
| Persistencia | Spring Data JPA + PostgreSQL 16 + pgvector | Un solo motor para datos relacionales y vectoriales, RLS nativo |
| Migraciones DB | Flyway | Versionado de esquema auditable, clave con RLS |
| Cola de mensajes | RabbitMQ (o SQS si despliegas en AWS) | Desacopla ingesta pesada del request HTTP |
| Seguridad | Spring Security + JWT (para consolas) + API Keys custom (para widget) | Dos mecanismos de auth distintos, ver sección 5 |
| Cliente HTTP a IA | Spring WebClient (reactivo, no bloqueante) | Llamadas a Claude/Voyage sin bloquear threads |
| Documentación API | springdoc-openapi (Swagger) | Insumo directo para el plan de frontend/consumo de API |
| Testing | JUnit 5 + Mockito + Testcontainers (Postgres real en tests de integración) | Testcontainers es clave para probar RLS de verdad, no con H2 |
| Observabilidad | Micrometer + Prometheus/Grafana, logs estructurados (JSON) con `tenant_id`/`account_id` en cada log | Indispensable para depurar por tenant y para el panel de super-admin |

---

## 4. Modelo de datos (núcleo)

```sql
-- Nivel Platform/Account/Tenant
accounts (account_id PK, nombre, plan, max_tenants, max_tokens_mes, status, created_at)
tenants  (tenant_id PK, account_id FK, nombre, dominios_permitidos[], status, created_at)
users    (user_id PK, account_id FK NULL, rol ENUM('super_admin','account_admin'), email, password_hash)
         -- account_id NULL para super_admin (no pertenece a ningún account)

-- Auth del widget
api_keys (key_id PK, tenant_id FK, key_hash, created_at, revoked_at)

-- RAG
documents (document_id PK, tenant_id FK, nombre_archivo, tipo, estado_procesamiento, uploaded_at)
chunks    (chunk_id PK, document_id FK, tenant_id FK, contenido, embedding VECTOR(1536), metadata JSONB)

-- Consumo
ai_usage_log (log_id PK, account_id, tenant_id, tipo_operacion, tokens_input, tokens_output, costo_estimado, timestamp)
```

**Row Level Security (aplicar desde la primera migración, no después):**

```sql
ALTER TABLE tenants ENABLE ROW LEVEL SECURITY;
ALTER TABLE chunks ENABLE ROW LEVEL SECURITY;
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;

-- Ejemplo de policy: un tenant solo ve sus propios chunks
CREATE POLICY tenant_isolation ON chunks
  USING (tenant_id = current_setting('app.current_tenant_id')::uuid);
```

La app setea `app.current_tenant_id` al inicio de cada transacción (vía `SET LOCAL` en un interceptor/aspect de Spring), derivado siempre del token/API key validado — nunca de un parámetro que mande el cliente.

---

## 5. Validación del widget (detalle completo)

Esta es la pieza más sensible de seguridad del sistema, porque el widget corre en un dominio de terceros y es público (cualquiera puede ver el request en las DevTools del navegador).

### 5.1 Qué NO debe pasar

- La API key **nunca** debe quedar expuesta en el HTML/JS público de forma que permita abusarla desde otro dominio o hacer scraping masivo del RAG del tenant.
- El `tenant_id` **nunca** debe venir como parámetro confiable del frontend — siempre se deriva server-side.

### 5.2 Flujo de autenticación recomendado (API Key + validación de origen)

```
1. El tenant instala en su página:
   <script src="https://cdn.tuplataforma.com/widget.js" 
           data-key="pk_live_xxxxxxxxxxxx"></script>

2. El widget, al cargar, hace un request inicial:
   POST /api/widget/session
   Headers: X-Widget-Key: pk_live_xxxxxxxxxxxx
   Body: { origin: window.location.origin }

3. Backend valida:
   a. La key existe y no está revocada (hash comparado, nunca texto plano en DB)
   b. El `origin` del request coincide con `dominios_permitidos` configurados
      para ese tenant (whitelist configurada desde el dashboard)
   c. Header `Referer`/`Origin` del request HTTP también se valida en el
      API Gateway/CORS config — doble capa (CORS a nivel infra + validación
      lógica a nivel aplicación)

4. Si todo válido: backend genera un JWT de sesión de corta duración
   (ej. 15-30 min, renovable) — este es el token que el widget usa para
   las siguientes llamadas de chat, NO la API key directamente.

5. Todas las llamadas siguientes (POST /api/widget/chat) usan ese JWT
   de sesión, no la API key pública — así aunque alguien capture el JWT
   desde DevTools, expira rápido y solo sirve para ese origen/sesión.
```

**Por qué separar "API key pública" de "JWT de sesión":**
- La API key es de "baja seguridad" (vive en HTML público, como un `pk_` de Stripe) pero solo sirve para *iniciar sesión* desde un origen autorizado — no para hacer queries directas al RAG.
- El JWT de sesión es lo que realmente autoriza a consultar el RAG, tiene vida corta, y queda atado a `tenant_id` + `origin` validados.
- Esto es exactamente el patrón que usan Stripe, Intercom y la mayoría de widgets embebibles B2B — separan key "publicable" de token de sesión.

### 5.3 Rate limiting (obligatorio, por tenant)

- Rate limit por `tenant_id` (ej. Bucket4j + Redis) a nivel de `POST /api/widget/chat` — evita que un tenant (o un actor malicioso desde su dominio) sature costos de IA.
- Rate limit adicional por IP/origen como capa extra contra abuso desde fuera del dominio autorizado.

### 5.4 CORS

```java
// Configuración dinámica de CORS: el allowlist de orígenes 
// se resuelve consultando `dominios_permitidos` del tenant,
// no un allowlist estático global — cada tenant tiene el suyo.
```

Esto requiere un `CorsConfigurationSource` custom en Spring Security en vez del `@CrossOrigin` estático, porque el origen permitido depende de qué tenant es dueño de la API key que llega en el request.

---

## 6. Aprovisionamiento self-service de tenants (Opción A)

Endpoint típico, disponible solo para rol `account_admin`:

```
POST /api/admin/tenants
Body: { nombre, dominios_permitidos: [...] }
Auth: JWT de sesión de consola, rol=account_admin

Backend:
1. Valida límite `max_tenants` del account (rechaza si ya llegó al límite)
2. Crea fila en `tenants` (status=provisioning)
3. Publica evento a la cola (ej. `tenant.created`) 
4. Worker asíncrono: no hay infraestructura física que crear (RLS ya
   cubre el aislamiento), solo inicializa estructuras vacías si aplica
   (ej. carpeta en storage de documentos) y marca status=active
5. Genera automáticamente la primera API key del tenant
6. Responde al dashboard (o notifica vía WebSocket/polling) que ya está listo
```

Como no hay infraestructura física por tenant que aprovisionar (todo vive en el mismo Postgres con RLS), este flujo es prácticamente síncrono en la práctica — el "provisioning" asíncrono es más por consistencia de patrón que por necesidad real a este volumen.

---

## 7. Buenas prácticas de clean code a aplicar desde el inicio

- **Casos de uso explícitos**: una clase por caso de uso (`CreateTenantUseCase`, `IngestDocumentUseCase`, `AnswerWidgetQueryUseCase`) en vez de "services" gigantes con 20 métodos. Facilita testear y entender qué hace cada flujo de negocio.
- **DTOs distintos por capa**: nunca exponer entidades JPA directamente en los controllers REST. Mappers explícitos (MapStruct) entre `domain` ↔ `api`.
- **Excepciones de dominio propias**: `TenantLimitExceededException`, `InvalidWidgetOriginException`, etc. — capturadas en un `@ControllerAdvice` centralizado que traduce a códigos HTTP apropiados, nunca lanzar excepciones genéricas de framework hacia el cliente.
- **Puertos (interfaces) para todo lo externo**: `EmbeddingProviderPort`, `LlmProviderPort`, `VectorStorePort` — así cambiar de Voyage a OpenAI, o de Claude a otro modelo, es cambiar un adaptador, no tocar lógica de negocio.
- **Tests por capa**: unit tests puros para `domain` (sin mocks de infraestructura), tests de integración con Testcontainers para verificar que el RLS realmente aísla tenants (este test en particular es no-negociable dado lo crítico del aislamiento).
- **Convención de nombres consistente**: value objects para conceptos de negocio (`TenantId`, `AccountId` como wrappers de UUID, no UUID crudo pasado por todos lados) — evita bugs de "pasé el account_id donde iba el tenant_id" por error de tipos.

---

## 8. Fases de desarrollo sugeridas

**Fase 1 — Fundaciones**
- Modelo de datos + migraciones Flyway + RLS
- Módulo `platform-core`: Accounts, Tenants, Users, roles, JWT de consola
- Tests de aislamiento RLS (crítico, hacerlo primero)

**Fase 2 — RAG (ingesta)**
- Módulo `knowledge-ingestion`: upload, cola, parsing (Excel/PDF), chunking, embeddings, escritura a pgvector

**Fase 3 — RAG (retrieval) + Widget Gateway**
- Módulo `knowledge-retrieval`: búsqueda semántica + prompt a Claude
- Módulo `widget-gateway`: flujo de autenticación completo (sección 5), endpoint de chat

**Fase 4 — Usage tracking + panel de super-admin (API)**
- Logging de consumo, endpoints de agregación por account/tenant

**Fase 5 — Aprovisionamiento self-service + hardening**
- Endpoint de creación de tenants, límites, rate limiting, CORS dinámico

Cada fase es desplegable y demostrable de forma independiente — no es necesario esperar a tener todo el sistema para empezar a validar con el cliente.

---

*Documento preparado como base para el desarrollo del backend. El plan de frontend (consolas en React) se entrega como documento aparte.*
