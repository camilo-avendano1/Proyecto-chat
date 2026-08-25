# [NOMBRE_PRODUCTO] — SaaS B2B de Asistencia Inteligente y Diagnóstico RAG Multi-Nivel (Sector Salud)

## ¿Qué es?

Un **Core Backend y Motor RAG (Retrieval-Augmented Generation) Multi-Nivel** de alta precisión diseñado para plataformas del sector salud. El sistema asiste a médicos, auditores y personal administrativo en la resolución de errores de cargue masivo de datos (ej. patologías de alto costo como Cáncer Tipo 2, formularios de más de 300 variables), traducción de logs de error de sistema y orientación sobre normativas médicas vigentes.

---

## División de Responsabilidades entre Equipos

```
┌────────────────────────────────────────────────────────┐
│  Equipo del Cliente / Partner                           │
│  - Frontend de la plataforma web clínica               │
│  - Desarrollo e integración del Widget Embebible       │
│  - Captura de contexto UI y envío de logs de error     │
└──────────────────────────┬─────────────────────────────┘
                           │ Consumo vía REST / SSE API
┌──────────────────────────▼─────────────────────────────┐
│  Nuestro Equipo                                         │
│  - API Backend Core (Python 3.12+ / FastAPI / AsyncIO) │
│  - Motor RAG Multi-Nivel y Búsqueda Híbrida (pgvector) │
│  - Ingesta de Normativas, Excels, FTP y Logs (Workers) │
│  - Consolas de Administración y Observabilidad (React) │
└────────────────────────────────────────────────────────┘
```

---

## Jerarquía de Conocimiento Multi-Nivel

```
Platform (Dueño del SaaS - Super Admin)
  └── Account (Empresa Prestadora de Salud / Revendedor)
        ├── Nivel 1: Normativas Globales de Salud & Revistas Médicas (Heredado)
        ├── Nivel 2: Directrices y Procesos Operativos del Account
        └── Tenants (14+ IPSs / Clínicas / Sedes Clientes como Sura, Sanitas)
              ├── Nivel 3: Documentación Local y Parametrizaciones de Sede
              └── Usuarios Finales (Médicos Especialistas, Auditores, Radicadores)
```

---

## Componentes del Sistema

| Componente | Responsable | Funcionalidad Principal | Stack Tecnológico |
|---|---|---|---|
| **API Backend Core & RAG** | Nuestro Equipo | Ingesta multinivel, parsing de PDFs normativos, Excels de 300+ campos, FTP sync con hashing SHA-256, recuperación jerárquica y diagnóstico con logs. | Python 3.12+, FastAPI, Pydantic v2, SQLAlchemy 2.0 Async, PostgreSQL 16 + `pgvector`, Clean Architecture |
| **Consola Account Admin** | Nuestro Equipo | Gestión de los Tenants, gestor documental con estados de ingesta, playground de pruebas RAG y métricas de tokens. | React 18, TypeScript, Vite, Tailwind CSS, shadcn/ui, TanStack Query |
| **Consola Super-Admin** | Nuestro Equipo | Visión global de Accounts, cuotas de tokens, salud del sistema y control de infraestructura. | React 18, TypeScript (mismo codebase de consolas) |
| **Widget Embebible & Host App** | Equipo Partner | Interfaz de chat integrada en la web clínica, captura de logs de error y contexto de botones/rutas. | JS/React del cliente consumiendo nuestro API vía SSE/REST |

---

## Casos de Uso Destacados

1. **Cargue de Documentos de Alto Costo (ej. Cáncer Tipo 2):** Guía al usuario en el diligenciamiento de formularios de más de 300 campos, validando reglas normativas antes de la radicación.
2. **Diagnóstico Técnico-Médico de Logs:** Recibe trazas de error del sistema y las traduce a explicaciones claras indicando qué campo corregir y en qué pantalla.
3. **Mapeo de UI, Botones y FTP Sync:** Sincroniza instructivos desde bases de datos de botones de ayuda y archivos FTP, deduplicando por hash de contenido.

---

## Documentación del Proyecto

1. [arquitectura-y-retos-tecnicos-python.md](file:///d:/Git/SaaS/arquitectura-y-retos-tecnicos-python.md) — **Arquitectura Integral en Python, Retos Técnicos, Deduplicación por Hashing, FTP Sync y Despliegue Local / GCP.**
2. [especificacion-sistema-completa.md](file:///d:/Git/SaaS/especificacion-sistema-completa.md) — Visión integral del sistema, glosario, modelo de negocio y arquitectura funcional.
3. [plan-backend-saas-rag.md](file:///d:/Git/SaaS/plan-backend-saas-rag.md) — Arquitectura técnica en Python 3.12+ (Clean Architecture), esquema SQL multinivel en `pgvector`, RLS y pipeline RAG.
4. [plan-frontend-consolas.md](file:///d:/Git/SaaS/plan-frontend-consolas.md) — Arquitectura de las consolas de administración, gestor documental y playground de diagnóstico.
5. [especificacion-api-integracion-widget.md](file:///d:/Git/SaaS/especificacion-api-integracion-widget.md) — Contrato formal de API REST/SSE y guía de integración para el equipo frontend del partner.
