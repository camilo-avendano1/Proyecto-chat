# FRONT-MOCK: Simulador y Consola Interactiva del Asistente Virtual SaaS Multi-Cliente

Este frontend interactivo desarrollado en **React + Vite** simula el widget embebido en distintas plataformas clientes (iniciando por defecto con la entidad genérica **`otra_empresa`** e incluyendo presets de ejemplo para **`sigires`**) y permite probar en vivo el flujo completo entre **`auth-service` (:8002)**, **`back-chat` (:8000)**, **`back-busqueda` (:8001)** y **`llm-gateway` (:8003)**.

---

## 🚀 Capacidades y Enfoque Funcional

1. **Cliente Genérico por Defecto + Multi-Tenancy:**
   - Selector de entidad/tenant encabezado por **`otra_empresa` (`Empresa Corporativa (Genérica)`)**, junto con ejemplos del cliente **`sigires`** (`EPS Sura`, `EPS Sanitas`, `Nueva EPS`).
   - Handshake mínimo contra `POST /api/v1/widget/session` enviando `origin` y adjuntando `client_id`, `metadata`, `eps_id` e `ips_code` únicamente cuando están definidos.
   - Visualización en tarjeta de sesión de `client_name`, `client_id`, `tenant_name` y vista previa del `session_token` JWT.

2. **Modo Petición Mínima vs. Modo Enriquecido (`POST /api/v1/chat/stream` y `/query`):**
   - Toggle **"Modo Petición Mínima (solo query)"** (activo por defecto): envía únicamente `{"query": "..."}` (y `conversation_history` si existen mensajes previos).
   - Al desactivarlo, adjunta únicamente los campos no vacíos de **`user`** (`id`, `organization`, `unit_code`, `role`), **`context`** (`url`, `view`, `module`, `status`, `file_format`, `active_button_id`, `field_in_focus`), **`logs`** y **`extras`** (editor JSON validado en **"Extras JSON para Búsqueda"**).

3. **6 Escenarios Preconfigurados en 1 Clic:**
   - **Genérico: Consulta Mínima (Solo Query):** Activa `minimalMode=true` con `"¿Cómo se aprueba una orden de compra?"`.
   - **Corporativo: Con Contexto y Extras:** Activa `minimalMode=false` con `user`, `context` y `extras` JSON corporativos.
   - **Cliente SIGIRES: Formulario + Log:** Ejemplo clínico con trazas de error en enfermería y cambio automático a tenant SIGIRES si estaba en genérico.
   - **Cliente SIGIRES: Error Formato Fase 1:** Ejemplo de rechazo por delimitador/columnas en archivo plano.
   - **Saludo Rápido (Fast-Path 0 Tokens):** Demuestra respuesta inmediata sin consumo LLM.
   - **Guardrail: Fuera de Dominio:** Demuestra intercepción segura ante consultas fuera del alcance del asistente.

4. **Inspector SSE y Modal de Observabilidad:**
   - Visualización en tiempo real de eventos desde `POST /api/v1/chat/stream` (`chunk`, `error_diagnostic`, `sources`, `done`).
   - Modal administrativo (`ObservabilityModal`) con autenticación contra `auth-service`, métricas segmentadas de tokens/costos (por usuario, rol, modelo y tenant) y auditoría de seguridad (Ley 1581 de 2012).

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
