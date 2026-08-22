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
│  - API Backend Core (Java 21 + Spring Boot 3.x)        │
│  - Motor RAG Multi-Nivel y Búsqueda Híbrida (pgvector) │
│  - Ingesta de Normativas, Excels Complejos y Logs      │
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
        └── Tenants (16 IPSs / Clínicas / Sedes Clientes)
              ├── Nivel 3: Documentación Local y Parametrizaciones de Sede
              └── Usuarios Finales (Médicos Especialistas, Auditores, Radicadores)
```

---

## Componentes del Sistema

| Componente | Responsable | Funcionalidad Principal | Stack Tecnológico |
|---|---|---|---|
| **API Backend Core & RAG** | Nuestro Equipo | Ingesta multinivel, parsing de PDFs normativos y Excels de 300+ campos, recuperación jerárquica y diagnóstico con logs. | Java 21 LTS, Spring Boot 3.x, PostgreSQL 16 + `pgvector`, Virtual Threads |
| **Consola Account Admin** | Nuestro Equipo | Gestión de los 16 Tenants, gestor documental con estados de ingesta, playground de pruebas RAG y métricas de tokens. | React 18, TypeScript, Vite, Tailwind CSS, shadcn/ui, TanStack Query |
| **Consola Super-Admin** | Nuestro Equipo | Visión global de Accounts, cuotas de tokens, salud del sistema y control de infraestructura. | React 18, TypeScript (mismo codebase de consolas) |
| **Widget Embebible & Host App** | Equipo Partner | Interfaz de chat integrada en la web clínica, captura de logs de error y contexto de botones/rutas. | JS/React del cliente consumiendo nuestro API |

---

## Casos de Uso Destacados

1. **Cargue de Documentos de Alto Costo (ej. Cáncer Tipo 2):** Guía al usuario en el diligenciamiento de formularios de más de 300 campos, validando reglas normativas antes de la radicación.
2. **Diagnóstico Técnico-Médico de Logs:** Recibe trazas de error del sistema y las traduce a explicaciones claras indicando qué campo corregir y en qué pantalla.
3. **Mapeo de UI y Botones:** Resuelve consultas operativas guiando al usuario exactamente sobre qué botón presionar según el flujo activo.

---

## Documentación del Proyecto

1. [especificacion-sistema-completa.md](file:///d:/Git/SaaS/especificacion-sistema-completa.md) — Visión integral del sistema, glosario, modelo de negocio y arquitectura funcional.
2. [plan-backend-saas-rag.md](file:///d:/Git/SaaS/plan-backend-saas-rag.md) — Arquitectura técnica en Java 21, esquema SQL multinivel en `pgvector`, RLS y pipeline RAG.
3. [plan-frontend-consolas.md](file:///d:/Git/SaaS/plan-frontend-consolas.md) — Arquitectura de las consolas de administración, gestor documental y playground de diagnóstico.
4. [especificacion-api-integracion-widget.md](file:///d:/Git/SaaS/especificacion-api-integracion-widget.md) — Contrato formal de API REST/SSE y guía de integración para el equipo frontend del partner.
