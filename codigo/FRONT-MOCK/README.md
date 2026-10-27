# FRONT-MOCK: Simulador y Consola Interactiva del Asistente Técnico de Formularios

Este frontend interactivo desarrollado en **React + Vite** simula el widget embebido en distintas plataformas clientes (como **SIGIRES** u otras entidades de salud/corporativas) y permite probar en vivo el flujo completo entre **`auth-service` (:8002)**, **`back-chat` (:8000)**, **`back-busqueda` (:8001)** y **`llm-gateway` (:8003)**.

---

## 🚀 Arquitectura y Enfoque Funcional

1. **Rol General del Asistente y Búsqueda Dinámica (RAG):**
   - El asistente está diseñado para orientar a **médicos, enfermeros, radicadores y auditores** cuando diligencian o suben diferentes **formularios y archivos en múltiples formatos** (`CSV`, `TXT`, `XML`, `JSON`, `ZIP`, formularios web).
   - El **System Prompt** únicamente define su rol como asistente técnico de formularios, mientras que las **situaciones, documentos y reglamentos** provienen dinámicamente de la búsqueda (`back-busqueda`) para darle contexto al LLM en el momento de preguntar.

2. **Gestión y Handshake de Sesión Multi-Cliente (`POST /api/v1/widget/session`):**
   - Selector dinámico de Tenant y Empresa (`EPS Sura`, `EPS Sanitas`, `Nueva EPS`, `Entidad Corporativa Externa`).
   - Emisión y validación automática del token JWT con visualización de expiración y alcance.

3. **Simulador de Contexto de Formulario y Profesional:**
   - **`ui_context`:** URL activa, vista/formulario (`REGISTRO_FORMULARIOS`, `REGISTRO_ENFERMERIA`, `VALIDACION_REPORTES`, `FACTURACION_RIPS`), módulo, estado de validación (`CON_ERRORES`, `RECHAZADO`, `EXITOSO`), formato (`FORMULARIO_CLINICO_CSV`, `REPORTE_MEDICO_XML`, `RIPS_SOPORTE_JSON`, `ANEXO_TECNICO_ZIP`), botón activo y campo en foco.
   - **`user_context`:** Profesional autenticado (`PERFIL_IPS_MEDICO`, `PERFIL_IPS_ENFERMERO`, `PERFIL_IPS_RADICADOR`, `PERFIL_EPS_AUDITOR`), entidad/aseguradora y código de institución.
   - **`system_logs`:** Trazas de error del validador para extracción genérica de fila, campo/variable, código de error y fase (`FASE_1_CA`, `FASE_2_CE`, `FASE_3_CD`).

4. **Escenarios Preconfigurados en 1 Clic:**
   - **Enfermería: Signos Vitales (CSV):** Validación de rangos y formato en formulario clínico de enfermería.
   - **Médico: Fecha en Reporte (XML):** Validación de fechas de atención frente al corte permitido.
   - **Coherencia entre Campos (TXT/ZIP):** Validación de cruces lógicos según anexo técnico recuperado en la búsqueda.
   - **Soporte RIPS / Facturación (JSON):** Coherencia entre código de prestación y diagnóstico CIE-10.
   - **Saludo Rápido (Fast-Path):** Respuesta inmediata con 0 tokens consumidos en el LLM.
   - **Guardrail Fuera de Dominio:** Intercepción de consultas ajenas a la validación de formularios y reglamentos.

5. **Inspector SSE y Panel de Observabilidad:**
   - Visualización en tiempo real de los eventos `event: chunk`, `event: error_diagnostic`, `event: sources` y `event: done`.
   - Modal administrativo con métricas de consumo de tokens por usuario, rol, modelo, tenant y auditoría de seguridad (Ley 1581 de 2012).

---

## 🛠️ Cómo Ejecutar

```bash
cd codigo/FRONT-MOCK
npm run dev
```
La interfaz estará disponible en: `http://localhost:5173`
