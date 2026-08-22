# [NOMBRE_PRODUCTO] — SaaS B2B de Asistencia Inteligente Multi-Tenant

## ¿Qué es?

Un asistente conversacional (chatbot con RAG) que las empresas integran como **widget embebible** en sus propias páginas web, para guiar a sus usuarios en la navegación de aplicaciones complejas y traducir errores técnicos en explicaciones claras, usando la documentación propia de cada empresa.

## Modelo de negocio

Venta en dos niveles:

```
Platform (dueño del SaaS)
  └── Account (empresa revendedora — compra la plataforma)
        └── Tenant (cliente final del Account — su propia base de conocimiento aislada)
```

En este proyecto: **1 Account con 16 Tenants**. El Account administra sus 16 Tenants de forma self-service, sin intervención del dueño de la plataforma.

Cobro al Account: tarifa fija pequeña + variable por consumo de infraestructura y tokens de IA.

## Sistemas que se construyen

| Sistema | Qué hace | Stack |
|---|---|---|
| **Widget embebible** | Script de una línea que el Tenant instala en su web; abre el chat, captura contexto del usuario logueado, se autentica y conversa con el asistente | JS/Preact, Shadow DOM, CDN |
| **Backend / Core RAG** | API que gestiona Accounts/Tenants/roles, procesa la documentación de cada Tenant (ingesta → chunking → embeddings), responde las consultas del widget con RAG, y trackea consumo/costos | Java 21 + Spring Boot, PostgreSQL + pgvector |
| **Consola Account Admin** | Dashboard donde el Account gestiona sus 16 Tenants, sube documentación, administra API keys y ve métricas de consumo | React + TypeScript |
| **Consola Super-Admin** | Vista global del dueño de la plataforma: consumo por Account, límites, suspensión | React + TypeScript (mismo codebase que la consola anterior) |

## Idioma

El asistente responde únicamente en español.

## Cronograma

3 meses, backend y frontend en paralelo. Mayor riesgo identificado: parsing de Excel de formularios (hasta 300 campos) y PDFs — se valida desde el primer mes.

## Decisiones aún abiertas

- **Cloud**: GCP o AWS (recomendación preliminar: GCP + Cloud Run por el patrón de tráfico intermitente).
- **Proveedor de IA**: OpenAI, Claude o DeepSeek — el backend se diseña para poder cambiar de proveedor por configuración.

## Documentación relacionada

- `especificacion-sistema-completa.md` — especificación completa (glosario, negocio, decisiones, cronograma detallado)
- `plan-backend-saas-rag.md` — arquitectura y plan de desarrollo del backend
- `plan-frontend-consolas.md` — arquitectura y plan de desarrollo del frontend
