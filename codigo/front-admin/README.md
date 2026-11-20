# Atenta — Consola Administrativa (`front-admin`)

Consola web en **React + Vite** (puerto **5174**) destinada a las cuentas administradoras (**`GLOBAL_ADMIN`** / *Admin Global* y **`ORG_ADMIN`** / *Administrador*) de **Atenta**, con etiquetas dinámicas por organización (`Sede/Sedes`, `Tienda/Tiendas`, `Taller/Talleres`, `Sucursal/Sucursales`, `Clínica/Clínicas`, `IPS/IPS`).

---

## Funcionalidades Principales

1. **Resumen Ejecutivo y Consumo de Modelos (`Resumen`):**
   - KPIs globales y filtrados por rango temporal (`7d`, `30d`, `90d`, `Todo`), organización y sede.
   - Incluye indicador de **Respuestas directas (sin costo)** para consultas resueltas sin consumo LLM.
   - Serie temporal diaria (`/api/v1/admin/usage/timeseries`) de consultas, tokens e inversión en USD.
   - Desglose de uso por sede (`/api/v1/admin/usage/by-site`), modelo de IA (incluyendo latencia promedio), usuario y rol.

2. **Gestión de Sedes y Claves de Conexión (`Sedes` — o el nombre elegido por la organización):**
   - Creación de nuevas sedes (`POST /api/v1/admin/sites`) con generación inmediata de clave de conexión (`pk_live_*`) para copiado único.
   - Edición de nombre, código de sede (`site_code`), dominios CORS permitidos, estado (`ACTIVE` / `SUSPENDED`) y rotación segura de claves (`PATCH /api/v1/admin/sites/{site_id}`).
   - Personalización rápida de terminología (`site_label` / `site_label_plural` vía `PATCH /api/v1/admin/organizations/{org_id}`) directamente por el `ORG_ADMIN` o `GLOBAL_ADMIN`.

3. **Documentos del Asistente (`Documentos`):**
   - Carga por arrastrar y soltar (*drag & drop*) o texto directo hacia `POST /api/v1/admin/documents`.
   - Formatos soportados: `.pdf`, `.xlsx`, `.csv`, `.docx`, `.txt`, `.md` y `.json` (hasta 15 MB por defecto).
   - Aislamiento estricto por alcance jerárquico:
     - `SITE` (exclusivo de una sede específica; recomendado para catálogos, horarios o guías locales).
     - `ORGANIZATION` (compartido por todas las sedes de un `org_id`).
     - `GLOBAL` (solo `GLOBAL_ADMIN`).
   - Deduplicación por hash SHA-256, inspección de fragmentos generados, resincronización manual hacia `back-busqueda` y eliminación en cascada.

4. **Auditoría de Consultas y Seguridad (`Auditoría`):**
   - Historial paginado de mensajes sanitizados (`/api/v1/admin/logs/messages`), transacciones en el gateway LLM (`/api/v1/admin/usage/records`), eventos de seguridad (`/api/v1/admin/logs/security`) y errores del sistema (`/api/v1/admin/logs/system-errors`).

5. **Reportes Comparativos y Descargas (`Reportes`):**
   - Tabla comparativa de rendimiento entre sedes (consultas, llamadas LLM vs respuestas directas sin costo, eficiencia %, tokens entrada/salida, participación de costo % y latencia promedio).
   - Exportación directa a **CSV (UTF-8 con BOM compatible con Excel)** y **JSON con metadatos** de métricas por sede, modelo, usuario, rol, serie temporal, auditoría e inventario de documentos.

6. **Control Multi-Organización (`Organizaciones y Accesos`) — exclusivo `GLOBAL_ADMIN`:**
   - Registro de nuevas organizaciones (`POST /api/v1/admin/organizations`) con etiqueta de sedes (`site_label`, `site_label_plural`), URL de `back-busqueda` y orígenes permitidos.
   - Creación, activación/suspensión y cambio de rol/contraseña de usuarios `GLOBAL_ADMIN` y `ORG_ADMIN`.

---

## Stack Tecnológico

- **React 18** + **Vite 5**
- **Recharts** (gráficas responsivas de áreas, barras y tortas)
- **Lucide React** (iconografía técnica)

---

## Proxy de Desarrollo y Variables de Entorno

En desarrollo (`npm run dev`), [`vite.config.js`](vite.config.js) redirige las llamadas locales para evitar problemas de CORS:

| Prefijo Frontend | Destino por Defecto | Servicio |
|---|---|---|
| `/api/auth` | `http://localhost:8002` | `auth-service` |
| `/api/chat` | `http://localhost:8000` | `back-chat` |
| `/api/gateway` | `http://localhost:8003` | `llm-gateway` |

Para apuntar a URLs distintas en compilación o despliegue estático (`npm run build`), defina en `.env`:

```env
VITE_AUTH_SERVICE_URL=http://localhost:8002
VITE_BACK_CHAT_URL=http://localhost:8000
VITE_LLM_GATEWAY_URL=http://localhost:8003
```

---

## Ejecución Local

```powershell
cd d:\Git\SaaS\codigo\front-admin
npm install
npm run dev
```

La consola quedará disponible en `http://localhost:5174`.

Para compilar para producción:

```powershell
npm run build
```

---

## Control de Acceso por Rol (RBAC)

- **`GLOBAL_ADMIN` (*Admin Global*)**: Acceso a todas las organizaciones, selector global de organización/sede, vista `Organizaciones y Accesos` y documentos con alcance `GLOBAL`, `ORGANIZATION` y `SITE`.
- **`ORG_ADMIN` (*Administrador*)**: Bloqueado estrictamente a su `org_id` asignado tanto en UI como en backend (`auth-service`, `back-chat` y `llm-gateway`). Puede gestionar sedes, personalizar las etiquetas `site_label`/`site_label_plural` de su organización, consultar métricas, auditoría, reportes y documentos `ORGANIZATION` o `SITE`; las acciones de `GLOBAL_ADMIN` (`POST /api/v1/admin/organizations`, creación de usuarios y documentos `GLOBAL`) retornan HTTP `403`.
