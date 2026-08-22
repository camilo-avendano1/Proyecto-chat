# Plan de Desarrollo — Frontend de Consolas de Administración (React)
## SaaS B2B de Asistencia Inteligente y Diagnóstico RAG Multi-Nivel (Sector Salud)

> **Contexto del proyecto (para agentes o lectores sin contexto previo)**
> Producto SaaS B2B llamado provisionalmente **[NOMBRE_PRODUCTO]**: un Core Backend y Motor RAG Multi-Nivel para el sector salud.
> 
> **División de Responsabilidades:**
> - **Equipo Cliente / Partner:** Se encarga del frontend de sus aplicaciones clínicas y del desarrollo/integración del widget embebible para los usuarios finales (médicos, auditores).
> - **Nuestro Equipo:** Desarrolla las **Consolas de Administración y Gestión de Conocimiento (Account Admin y Super-Admin)** en React + TypeScript, las cuales consumen la API REST expuesta por nuestro backend en Java (ver [plan-backend-saas-rag.md](file:///d:/Git/SaaS/plan-backend-saas-rag.md)).
> 
> Para el contexto de negocio completo y casos de uso, ver [especificacion-sistema-completa.md](file:///d:/Git/SaaS/especificacion-sistema-completa.md).

---

## 1. Alcance de las Consolas

El frontend a cargo de nuestro equipo comprende una sola aplicación web SPA modular que renderiza vistas y permisos según el rol del usuario autenticado:

1. **Consola de Account Admin (Para la empresa prestadora / cliente B2B):**
   - **Gestión de Jerarquía y Tenants:** Administración de sus 16 entidades clientes (IPSs, clínicas, sedes), códigos institucionales y dominios permitidos.
   - **Gestor de Base de Conocimiento Multi-Nivel:** Carga y monitoreo de parseo de normativas de salud (PDF), guías de cargue masivo (Excel de 300+ campos como Cáncer Tipo 2), catálogos de error y mapas de botones/UI.
   - **Playground de Pruebas y Diagnóstico:** Simulador interactivo para probar consultas RAG inyectando logs de error y contexto de pantalla antes de pasarlos a producción.
   - **Administración de API Keys:** Generación, rotación y revocación de credenciales para el widget del partner.
   - **Métricas de Consumo y Ledger de Tokens:** Visualización de tokens consumidos, desglose por IPS y tipos de consultas asistenciales.

2. **Consola de Super-Admin (Para el dueño de la Platform):**
   - Visión consolidada de todos los Accounts del SaaS.
   - Control de cuotas globales (máximo de tokens/mes, número de Tenants por Account).
   - Monitoreo de salud del sistema, latencias de modelos de IA y costos de infraestructura.

---

## 2. Stack Tecnológico

| Componente | Elección | Justificación Técnica |
|---|---|---|
| **Framework & Lenguaje** | React 18 + TypeScript | Tipado estricto alineado con los DTOs y schemas OpenAPI del backend en Java. |
| **Build Tool** | Vite | Desarrollo rápido, Hot Module Replacement (HMR) instantáneo y builds optimizados. |
| **Enrutamiento** | React Router v6 | Enrutamiento declarativo con protección de rutas por rol (`super_admin` vs `account_admin`). |
| **Estado del Servidor** | TanStack Query (React Query v5) | Cache inteligente, sincronización automática de estado de ingesta de documentos y refetch optimizado. |
| **Estado Local de UI** | Zustand | Estado ligero para navegación, filtros de jerarquía y estado del simulador RAG. |
| **Componentes & Estilos** | Tailwind CSS + shadcn/ui (Radix UI) | Interfaz visual moderna, accesible, profesional y rápida de construir. |
| **Formularios & Validación** | React Hook Form + Zod | Validación de esquemas en tiempo de ejecución para carga de metadatos de documentos y configuración de Tenants. |
| **Visualización de Datos** | Recharts | Gráficas interactivas para análisis de consumo de tokens y tendencias de errores diagnosticados. |
| **Cliente HTTP** | Axios con Interceptors | Manejo centralizado de tokens JWT, inyección de encabezados de sesión y renovación automática. |

---

## 3. Arquitectura del Proyecto Frontend

```
src/
├── app/                         ← Router raíz, Providers de React Query y Layouts protegidos
├── shared/                      ← Componentes de UI compartidos (Button, Dialog, Badge, Table), cliente HTTP
├── features/
│   ├── auth/                    ← Login, manejo de token JWT y rol de usuario
│   ├── tenants/                 ← Gestión de las 16 IPSs/Tenants y sus dominios
│   ├── knowledge-base/          ← Subida de normativas, guías Excel y visualizador de estado de chunks
│   ├── diagnostic-playground/   ← Simulador de RAG con inyección de logs médicos y contexto de pantalla
│   ├── api-keys/                ← Gestión de API Keys públicas y secretas para el widget del partner
│   ├── usage-metrics/           ← Dashboard de consumo de tokens y análisis de costos por IPS
│   └── super-admin/             ← Vistas exclusivas de Super-Admin (todos los Accounts y límites)
└── types/                      ← Interfaces TypeScript generadas desde el contrato OpenAPI
```

---

## 4. Módulos y Pantallas Clave

### 4.1 Gestor de Base de Conocimiento Multi-Nivel (`/knowledge-base`)
- **Filtro por Ámbito:** Visualización segmentada por Nivel 1 (Normativas Globales), Nivel 2 (Directrices del Account) y Nivel 3 (Documentos locales de cada IPS).
- **Subida Especializada:**
  - Carga de PDFs normativos con asignación de categoría (Resolución Ministerial, Guía Clínica).
  - Carga de archivos Excel con mapeo de formularios (ej. Plantilla Cáncer Tipo 2 de 300+ variables).
  - Carga de archivos JSON con mapeo de botones, rutas y catálogos de error.
- **Visualizador de Estado de Ingesta:** Barra de progreso en tiempo real que indica: `PENDIENTE` $\rightarrow$ `PARSANDO_EXCEL` $\rightarrow$ `GENERANDO_EMBEDDINGS` $\rightarrow$ `INDEXADO_PGVECTOR` (o `ERROR_EN_FILA_X`).

### 4.2 Playground de Pruebas y Diagnóstico RAG (`/playground`)
- Interfaz interactiva diseñada para que los administradores y auditores del Account verifiquen la precisión del asistente antes de liberar documentación:
  - **Panel de Entrada:** Campo para consulta del usuario + Textarea para pegar snippets de logs de error + Selectores de Pantalla y Botón activo + Selector de IPS/Tenant.
  - **Panel de Respuesta:** Muestra la respuesta generada por el LLM en lenguaje médico, destacando el código de error detectado, los pasos de remediación sugeridos y la lista de chunks/citas normativas utilizadas para la respuesta.

### 4.3 Gestión de Tenants y Jerarquía (`/tenants`)
- Tabla interactiva con las 16 IPSs/Tenants clientes:
  - Nombre de la institución y Código de Habilitación de Salud.
  - Cantidad de documentos específicos cargados.
  - Estado operativo (`ACTIVO`, `EN_PROCESO`, `SUSPENDIDO`).
  - Consumo acumulado de tokens en el mes.
  - Configuración de dominios permitidos (CORS whitelist).

### 4.4 Dashboard de Métricas y Ledger de Consumo (`/metrics`)
- Gráficas de consumo histórico de tokens (últimos 30/60/90 días).
- Desglose de tokens por tipo de operación: Ingesta vectorial vs. Consultas de diagnóstico en vivo.
- Distribución de consultas por patología o módulo (ej. % de consultas asociadas a Cáncer Tipo 2 vs. Cuentas Médicas).

---

## 5. Fases de Desarrollo del Frontend (3 Meses)

```
Mes 1: Fundaciones y Gestión de Jerarquía
├── Sem 1-2: Setup Vite, Tailwind, Layout base, Auth JWT y control de rutas por rol
└── Sem 3-4: Módulo de Tenants (CRUD de IPSs, configuración de dominios) y gestión de API Keys

Mes 2: Gestor Documental y Playground RAG
├── Sem 5-6: Módulo de Base de Conocimiento con estados de ingesta en tiempo real
└── Sem 7-8: Playground de Diagnóstico (simulador de consultas + logs + inspección de citas)

Mes 3: Dashboards de Consumo, Super-Admin y Pulido
├── Sem 9-10: Dashboard de métricas de tokens, costos por IPS y gráficos de uso
└── Sem 11-12: Consola Super-Admin (límites globales), pruebas de integración y entrega
```
