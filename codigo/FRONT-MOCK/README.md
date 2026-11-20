# Atenta — Simulador Interactivo del Widget (`FRONT-MOCK`)

Este frontend interactivo de **Atenta** desarrollado en **React + Vite** simula el widget embebido en distintas plataformas clientes (iniciando por defecto con la organización genérica **`otra_empresa`** e incluyendo presets de ejemplo por sector: salud **`sigires`**, retail y automotriz) y permite probar en vivo el flujo completo entre **`auth-service` (:8002)**, **`back-chat` (:8000)**, **`back-busqueda` (:8001)** y **`llm-gateway` (:8003)**.

---

## 🚀 Capacidades y Enfoque Funcional

1. **Organización Genérica por Defecto + Multi-Sede:**
   - Selector de organización/sede encabezado por **`otra_empresa` (`Organización Demo Central` — `Sede Operativa Central`)**, junto con ejemplos sectoriales como **`sigires`** (IPS de salud), tiendas y talleres.
   - Handshake mínimo contra `POST /api/v1/widget/session` enviando `origin` y adjuntando `org_id`, `site_code` y `metadata` únicamente cuando están definidos.
   - Visualización en tarjeta de sesión de `org_name`, `org_id`, `site_name`, `site_label` y vista previa del `session_token` JWT.

2. **Modo Petición Mínima vs. Modo Enriquecido (`POST /api/v1/chat/stream` y `/query`):**
   - Toggle **"Modo Petición Mínima (solo query)"** (activo por defecto): envía únicamente `{"query": "..."}` (y `conversation_history` si existen mensajes previos).
   - Al desactivarlo, adjunta únicamente los campos no vacíos de **`user`** (`id`, `organization`, `unit_code`, `role`), **`context`** (`url`, `view`, `module`, `status`, `file_format`, `active_button_id`, `field_in_focus`), **`logs`** y **`extras`** (editor JSON validado en **"Extras JSON para Búsqueda"**).

3. **Escenarios Preconfigurados en 1 Clic:**
   - **Genérico: Consulta Mínima (Solo Query):** Activa `minimalMode=true` con `"¿Cómo se aprueba una orden de compra?"`.
   - **Corporativo: Con Contexto y Extras:** Activa `minimalMode=false` con `user`, `context` y `extras` JSON corporativos.
   - **SIGIRES: Formulario + Log:** Ejemplo clínico con trazas de error en enfermería y cambio automático a una sede de `sigires` si estaba en genérico.
   - **SIGIRES: Error Formato Fase 1:** Ejemplo de rechazo por delimitador/columnas en archivo plano.
   - **Saludo Rápido (Respuestas directas sin costo — 0 Tokens):** Demuestra respuesta inmediata sin consumo LLM.
   - **Guardrail: Fuera de Dominio:** Demuestra intercepción segura ante consultas fuera del alcance del asistente.

4. **Inspector SSE y Modal de Observabilidad:**
   - Visualización en tiempo real de eventos desde `POST /api/v1/chat/stream` (`chunk`, `error_diagnostic`, `sources`, `done`).
   - Modal administrativo (`ObservabilityModal`) con autenticación contra `auth-service` (`GLOBAL_ADMIN` / `ORG_ADMIN`), métricas segmentadas de tokens/costos (por usuario, rol, modelo y sede) y auditoría de seguridad (Ley 1581 de 2012).

---

## 🛠️ Cómo Ejecutar y Construir

```bash
cd codigo/FRONT-MOCK
npm install
npm run dev
```

La interfaz estará disponible en: `http://localhost:5173`

Para validar la compilación de producción:

```bash
npm run build
```
