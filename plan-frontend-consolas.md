# Plan de Desarrollo — Frontend de Consolas (React)
## SaaS B2B de Asistencia Inteligente Multi-Tenant (RAG)

> **Contexto del proyecto (para agentes o lectores sin contexto previo)**
> Producto SaaS B2B llamado provisionalmente **[NOMBRE_PRODUCTO]**: un asistente conversacional embebible (widget de chat con RAG) que empresas ("Tenants") integran en sus propias páginas web para guiar navegación y explicar errores técnicos, usando su propia documentación indexada.
> Jerarquía: **Platform** (dueño de la plataforma, rol `super_admin`) → **Account** (empresa revendedora que compra la plataforma; en este proyecto hay un solo Account) → **Tenant** (cada empresa cliente del Account; actualmente 16). Modelo de roles "Opción A": el `account_admin` gestiona directamente sus 16 Tenants y las API keys de estos, sin login propio por Tenant. Este documento cubre las **consolas** de administración (Account Admin y Super-Admin) — no el widget que consume el usuario final.
> Las consolas consumen la API REST expuesta por el backend en Java (ver `plan-backend-saas-rag.md`). Plazo objetivo de desarrollo: 3 meses, en paralelo con el backend.
> Para el contexto de negocio completo (modelo de precios, decisiones pendientes de cloud/IA, cronograma detallado), ver `especificacion-sistema-completa.md` — ese documento es la fuente de verdad sobre el *qué* y el *por qué*; este documento es la fuente de verdad sobre el *cómo* técnico del frontend.

---

## 1. Alcance

Dos consolas distintas, mismo codebase, rutas y permisos separados por rol:

- **Consola de Super-Admin** (solo tú): visibilidad global de todos los Accounts, consumo agregado, salud del sistema.
- **Consola de Account Admin** (tu cliente): gestión de sus tenants, subida de documentación, API keys, métricas de uso — corresponde al "Portal de Administración B2B" del diseño original.

No hay una tercera consola para las 16 empresas finales (se definió Opción A: el Account admin las gestiona directamente).

---

## 2. Stack tecnológico

| Componente | Elección | Motivo |
|---|---|---|
| Framework | React 18 + TypeScript | Tipado fuerte reduce bugs de integración con la API Java |
| Build tool | Vite | Arranque y HMR mucho más rápido que CRA |
| Routing | React Router v6 | Estándar de facto, soporta rutas anidadas por rol |
| Server state | TanStack Query (React Query) | Maneja cache, refetch, loading/error states de las llamadas a la API — evita reinventar esto a mano |
| Client state (UI) | Zustand | Ligero, para estado de UI que no viene del servidor (ej. sidebar abierto/cerrado) |
| Formularios | React Hook Form + Zod | Validación tipada, coincide con los DTOs del backend |
| Estilos/componentes | Tailwind CSS + shadcn/ui | Rápido de construir, consistente, fácil de mantener sin CSS custom disperso |
| Gráficas (métricas de consumo) | Recharts | Suficiente para dashboards de consumo/costos |
| Auth | JWT en memoria (no localStorage) + refresh token en cookie httpOnly | Mitiga XSS robando el token de sesión |
| Testing | Vitest + React Testing Library | Estándar del ecosistema Vite |

---

## 3. Arquitectura del proyecto

```
src/
├── app/                    ← configuración raíz: router, providers, layout
├── shared/                 ← componentes UI reutilizables, hooks genéricos,
│                              cliente HTTP base (axios/fetch wrapper con
│                              interceptor de auth), utils
├── features/
│   ├── auth/                ← login, manejo de sesión/rol
│   ├── tenants/              ← CRUD de tenants (crear, listar, suspender)
│   ├── knowledge-base/       ← upload de documentos, estado de procesamiento
│   ├── api-keys/              ← generar/revocar keys por tenant
│   ├── usage-metrics/         ← dashboards de consumo (por tenant y agregado)
│   └── super-admin/           ← vistas exclusivas de super_admin (todos los accounts)
└── types/                   ← tipos TS generados/alineados con los DTOs del backend
```

**Patrón por feature**: cada carpeta en `features/` tiene su propia estructura interna (`components/`, `hooks/`, `api.ts`, `types.ts`) — así cada módulo es autocontenido y fácil de ubicar, en vez de separar por tipo de archivo a nivel global (que dispersa la lógica de una misma funcionalidad en carpetas lejanas).

**Separación de responsabilidades:**
- `api.ts` por feature: solo funciones que llaman al backend (usando el cliente HTTP compartido), sin lógica de UI.
- Hooks de React Query (`useTenants`, `useCreateTenant`) envuelven esas funciones — son el único punto de contacto entre componentes y la API.
- Componentes nunca llaman `fetch`/`axios` directamente — siempre a través de los hooks.

---

## 4. Autenticación y control de acceso por rol

```typescript
// Estructura del JWT que recibes del backend tras login
{
  sub: userId,
  rol: 'super_admin' | 'account_admin',
  accountId: string | null   // null para super_admin
}
```

- El router raíz decide qué layout/rutas montar según `rol` — un `account_admin` nunca puede navegar (ni por URL directa) a rutas de `super-admin/*`, se valida en un `ProtectedRoute` wrapper que redirige si el rol no coincide.
- El `accountId` del JWT nunca se manda manualmente en los requests — el interceptor del cliente HTTP no necesita inyectarlo porque el backend ya lo deriva del token (igual que el `tenant_id` en el widget). Esto evita que el frontend tenga que "confiar" en pasar el ID correcto.

---

## 5. Consumo de la API — patrón recomendado

### 5.1 Cliente HTTP base

```typescript
// shared/api/httpClient.ts
const httpClient = axios.create({ baseURL: import.meta.env.VITE_API_URL });

httpClient.interceptors.request.use((config) => {
  const token = authStore.getAccessToken();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

httpClient.interceptors.response.use(
  (res) => res,
  async (error) => {
    if (error.response?.status === 401) {
      // intenta refrescar token vía cookie httpOnly, si falla → logout
    }
    return Promise.reject(error);
  }
);
```

### 5.2 Ejemplo de feature completo (tenants)

```typescript
// features/tenants/api.ts
export const tenantsApi = {
  list: () => httpClient.get<Tenant[]>('/api/admin/tenants'),
  create: (data: CreateTenantDto) => httpClient.post<Tenant>('/api/admin/tenants', data),
  suspend: (id: string) => httpClient.patch(`/api/admin/tenants/${id}/suspend`),
};

// features/tenants/hooks.ts
export function useTenants() {
  return useQuery({ queryKey: ['tenants'], queryFn: tenantsApi.list });
}

export function useCreateTenant() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: tenantsApi.create,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['tenants'] }),
  });
}
```

Este patrón se repite igual para `knowledge-base`, `api-keys`, `usage-metrics` — consistencia entre features es lo que hace el código predecible para cualquiera que lo mantenga después.

### 5.3 Documentación de contrato

El backend expone OpenAPI/Swagger (definido en el plan de backend) — desde ahí puedes generar automáticamente los tipos TypeScript (`openapi-typescript` o similar) en vez de escribirlos a mano, así el frontend nunca se desincroniza silenciosamente del contrato real de la API.

---

## 6. Pantallas clave

### Consola Account Admin (tu cliente)
1. **Dashboard general**: resumen de sus 16 tenants, consumo total del mes, alertas (tenant cerca del límite)
2. **Listado/gestión de tenants**: crear, ver detalle, suspender, editar dominios permitidos
3. **Base de conocimiento por tenant**: upload de archivos, estado de procesamiento (pendiente/procesando/listo/error), historial de documentos
4. **API Keys por tenant**: generar, revocar, ver última fecha de uso
5. **Métricas de consumo**: por tenant individual y agregado, gráfica de tendencia, breakdown por tipo de operación (ingesta vs queries)

### Consola Super-Admin (tú)
1. **Dashboard global**: todos los Accounts, consumo agregado por account, salud general del sistema
2. **Detalle de Account**: drill-down a sus tenants si necesitas auditar
3. **Configuración de límites**: `max_tenants`, `max_tokens_mes` por Account
4. **Suspensión de Account**: control de facturación/estado

---

## 7. Manejo de estados de carga larga (importante para tu caso)

Como mencionaste que la ingesta inicial puede ser de ~300 archivos, la consola necesita comunicar bien el progreso:

- Vista de "cola de procesamiento" por tenant con estados por archivo (no solo un spinner genérico).
- Polling con React Query (`refetchInterval`) mientras haya documentos en estado `procesando`, o mejor aún, WebSocket/SSE si el backend lo expone, para actualización en tiempo real sin poll constante.

---

## 8. Fases de desarrollo sugeridas

**Fase 1** — Auth + layout base + control de rutas por rol
**Fase 2** — Consola Account Admin: gestión de tenants + API keys
**Fase 3** — Consola Account Admin: base de conocimiento (upload + estado de procesamiento)
**Fase 4** — Consola Account Admin: métricas de consumo
**Fase 5** — Consola Super-Admin completa

Cada fase se puede demostrar de forma independiente a medida que el backend va exponiendo los endpoints correspondientes (alineado con las fases del plan de backend).

---

*Este documento complementa el plan de backend. Ambos comparten el mismo modelo de roles (Opción A) y el mismo contrato de API.*
