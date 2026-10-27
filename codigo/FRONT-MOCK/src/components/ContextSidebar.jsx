import React, { useState } from 'react';
import { 
  Key, 
  Settings, 
  Layers, 
  UserCheck, 
  FileText, 
  Sparkles, 
  CheckCircle2, 
  AlertCircle, 
  RefreshCw,
  ChevronDown,
  ChevronUp
} from 'lucide-react';

export const TENANT_PRESETS = {
  sura: {
    client_id: 'sigires',
    client_name: 'SIGIRES (Procex Software S.A.S)',
    eps_id: 'eps_sura_01',
    eps_nombre: 'EPS Sura - Regional Nor-Occidente',
    api_key: 'pk_live_sigires_8f9a2b1c3d4e5f6a',
    ips_code: '631300040301',
    ips_nombre: 'Clínica Las Américas',
    eps_code: 'EPS_SURA',
  },
  sanitas: {
    client_id: 'sigires',
    client_name: 'SIGIRES (Procex Software S.A.S)',
    eps_id: 'eps_sanitas_01',
    eps_nombre: 'EPS Sanitas - IPS San Rafael',
    api_key: 'pk_live_sigires_sanitas_7c9d1e2f3a4b',
    ips_code: '110010999901',
    ips_nombre: 'Clínica Reina Sofía',
    eps_code: 'EPS_SANITAS',
  },
  nuevaeps: {
    client_id: 'sigires',
    client_name: 'SIGIRES (Procex Software S.A.S)',
    eps_id: 'eps_nueva_01',
    eps_nombre: 'Nueva EPS - Consorcio Salud',
    api_key: 'pk_live_sigires_nuevaeps_9e8d7c6b5a4f',
    ips_code: '050010001201',
    ips_nombre: 'Hospital Universitario San Vicente',
    eps_code: 'EPS_NUEVA',
  },
  otra_empresa: {
    client_id: 'otra_empresa',
    client_name: 'Entidad Corporativa Externa',
    eps_id: 'corp_div_01',
    eps_nombre: 'División Operativa Central',
    api_key: 'pk_live_otraempresa_1a2b3c4d5e6f7a8b',
    ips_code: 'CORP99999999',
    ips_nombre: 'Sede Central Corporativa',
    eps_code: 'CORP_EXT',
  },
};

export const SCENARIO_PRESETS = [
  {
    id: 'form_enfermeria',
    name: 'Enfermería: Signos Vitales (CSV)',
    query: 'Al subir el formulario de enfermería me rechaza el registro de signos vitales',
    system_logs: "Fila: 18 | Campo: 6 | Variable 'Presion_Arterial' fuera de formato esperado. Error CE_CAMPO_006_FMT",
    formato_archivo: 'FORMULARIO_CLINICO_CSV',
    pagina_actual: 'REGISTRO_ENFERMERIA',
    modulo: 'FORMULARIOS_CLINICOS',
    estado_cargue_actual: 'CON_ERRORES',
    active_button_id: 'btn_validar_formulario',
    field_in_focus: 'campo_presion_arterial',
  },
  {
    id: 'formato_fecha',
    name: 'Médico: Fecha en Reporte (XML)',
    query: 'El sistema me rechaza la fecha de atención al validar el formulario médico',
    system_logs: "Fila: 45 | Campo: 9 | Variable 'Fecha_Atencion' posterior al corte permitido. Error CA_VAR_009_DATE",
    formato_archivo: 'REPORTE_MEDICO_XML',
    pagina_actual: 'VALIDACION_REPORTES',
    modulo: 'CARGA_ARCHIVOS',
    estado_cargue_actual: 'RECHAZADO',
    active_button_id: 'btn_procesar_archivo',
    field_in_focus: 'campo_009_fecha',
  },
  {
    id: 'coherencia_campo',
    name: 'Coherencia entre Campos (TXT/ZIP)',
    query: '¿Por qué me aparece rechazo por incoherencia entre sexo y condición de la usuaria?',
    system_logs: "Fila: 12 | Columna: 14 | Variable 'Condicion_Usuaria' incompatible con sexo reportado. Error CE_VAR_014_INVAL",
    formato_archivo: 'ANEXO_TECNICO_ZIP',
    pagina_actual: 'CARGA_ARCHIVOS_NORMATIVOS',
    modulo: 'CARGA_ARCHIVOS',
    estado_cargue_actual: 'CON_ERRORES',
    active_button_id: 'btn_validar_archivo',
    field_in_focus: 'campo_014_condicion',
  },
  {
    id: 'rips',
    name: 'Soporte RIPS / Facturación (JSON)',
    query: '¿Cómo subsano el error de coherencia entre prestación y diagnóstico en el archivo RIPS?',
    system_logs: 'Fila: 88 | Campo: 15 | Error RIPS_CT_INVAL: Inconsistencia entre código de prestación y CIE-10',
    formato_archivo: 'RIPS_SOPORTE_JSON',
    pagina_actual: 'FACTURACION_RIPS',
    modulo: 'INFORMES',
    estado_cargue_actual: 'CON_ERRORES',
    active_button_id: 'btn_generar_rips',
    field_in_focus: 'rips_codigo_consulta',
  },
  {
    id: 'saludo',
    name: 'Saludo Rápido (Fast-Path)',
    query: '¡Hola! Buenos días, ¿en qué me puedes ayudar hoy?',
    system_logs: '',
    formato_archivo: 'FORMULARIO_CLINICO_CSV',
    pagina_actual: 'DASHBOARD_PRINCIPAL',
    modulo: 'INICIO',
    estado_cargue_actual: 'NO_APLICA',
    active_button_id: null,
    field_in_focus: null,
  },
  {
    id: 'guardrail',
    name: 'Guardrail: Fuera de Dominio',
    query: '¿Cuál es la mejor receta para preparar un pastel de chocolate?',
    system_logs: '',
    formato_archivo: 'NO_APLICA',
    pagina_actual: 'GENERAL',
    modulo: 'GENERAL',
    estado_cargue_actual: 'NO_APLICA',
    active_button_id: null,
    field_in_focus: null,
  }
];

export default function ContextSidebar({
  tenantKey,
  setTenantKey,
  sessionData,
  onInitSession,
  isSessionLoading,
  uiContext,
  setUiContext,
  userContext,
  setUserContext,
  systemLogs,
  setSystemLogs,
  onSelectScenario,
  activeScenarioId,
}) {
  const [showAdvancedUi, setShowAdvancedUi] = useState(false);
  const [showAdvancedUser, setShowAdvancedUser] = useState(false);

  const handleTenantChange = (key) => {
    setTenantKey(key);
    const preset = TENANT_PRESETS[key];
    if (preset) {
      setUserContext((prev) => ({
        ...prev,
        eps: preset.eps_code,
        ips_code: preset.ips_code,
        ips_nombre: preset.ips_nombre,
        filial: preset.eps_nombre,
      }));
    }
  };

  return (
    <aside className="context-panel">
      {/* 1. Header */}
      <div className="panel-header">
        <div className="panel-title">
          <Settings size={18} style={{ color: '#10b981' }} />
          <span>Configuración & Contexto</span>
        </div>
      </div>

      {/* 2. Tenant / Client Selector */}
      <div className="panel-section">
        <div className="section-label">
          <span>Cliente & Tenant (Empresa)</span>
          <Key size={13} />
        </div>

        <div className="form-group">
          <label className="form-label">Entidad / Cliente Solicitante</label>
          <select 
            className="form-select"
            value={tenantKey}
            onChange={(e) => handleTenantChange(e.target.value)}
          >
            <option value="sura">SIGIRES - EPS Sura (Regional Nor-Occidente)</option>
            <option value="sanitas">SIGIRES - EPS Sanitas (IPS San Rafael)</option>
            <option value="nuevaeps">SIGIRES - Nueva EPS (Consorcio Salud)</option>
            <option value="otra_empresa">Otra Empresa (Entidad Corporativa Externa)</option>
          </select>
        </div>

        {/* Handshake Session Box */}
        <div className="session-card" style={{ marginTop: '10px' }}>
          <div className="session-row">
            <span className="session-key">Estado de Sesión:</span>
            <span className="session-val" style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
              {sessionData ? (
                <>
                  <CheckCircle2 size={13} style={{ color: '#10b981' }} />
                  <span style={{ color: '#34d399' }}>JWT Autenticado</span>
                </>
              ) : (
                <>
                  <AlertCircle size={13} style={{ color: '#f59e0b' }} />
                  <span style={{ color: '#fbbf24' }}>Sin Sesión</span>
                </>
              )}
            </span>
          </div>

          {sessionData && (
            <>
              <div className="session-row">
                <span className="session-key">Tenant Name:</span>
                <span className="session-val" title={sessionData.tenant_name}>
                  {sessionData.tenant_name}
                </span>
              </div>
              <div className="session-row">
                <span className="session-key">Token JWT:</span>
                <span className="session-val" title={sessionData.session_token}>
                  {sessionData.session_token.slice(0, 18)}...
                </span>
              </div>
            </>
          )}

          <button 
            className="btn-primary" 
            style={{ width: '100%', marginTop: '10px', padding: '7px 12px' }}
            onClick={onInitSession}
            disabled={isSessionLoading}
          >
            <RefreshCw size={13} className={isSessionLoading ? 'spin' : ''} />
            {sessionData ? 'Renovar Sesión (Handshake)' : 'Inicializar Sesión (Handshake)'}
          </button>
        </div>
      </div>

      {/* 3. Escenarios de Prueba Clínicos Preconfigurados */}
      <div className="panel-section">
        <div className="section-label">
          <span>Escenarios Preconfigurados</span>
          <Sparkles size={13} style={{ color: '#10b981' }} />
        </div>
        <p style={{ fontSize: '0.74rem', color: 'var(--text-muted)', marginBottom: '8px' }}>
          Carga en 1 clic escenarios de diferentes formularios, formatos y perfiles (Médicos, Enfermeros, Radicadores):
        </p>
        <div className="preset-chips">
          {SCENARIO_PRESETS.map((scenario) => (
            <button
              key={scenario.id}
              className={`chip-btn ${activeScenarioId === scenario.id ? 'active' : ''}`}
              onClick={() => onSelectScenario(scenario)}
            >
              {scenario.name}
            </button>
          ))}
        </div>
      </div>

      {/* 4. System Logs Input */}
      <div className="panel-section">
        <div className="section-label">
          <span>Trazas / Logs del Sistema</span>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            {systemLogs && (
              <button 
                className="chip-btn" 
                style={{ fontSize: '0.68rem', padding: '1px 6px' }}
                onClick={() => setSystemLogs('')}
                title="Limpiar trazas"
              >
                Limpiar
              </button>
            )}
            <FileText size={13} />
          </div>
        </div>
        <div className="form-group">
          <label className="form-label">
            Logs de Error descargados (El Back los clasificará en CA/CE/CD):
          </label>
          <textarea
            className="form-textarea"
            placeholder="Fila: 12 | Columna: 14 | Error CE_VAR_014_INVAL..."
            value={systemLogs}
            onChange={(e) => setSystemLogs(e.target.value)}
          />
        </div>
      </div>

      {/* 5. UI Context Simulator */}
      <div className="panel-section">
        <div 
          className="section-label" 
          style={{ cursor: 'pointer', marginBottom: showAdvancedUi ? '12px' : '0' }}
          onClick={() => setShowAdvancedUi(!showAdvancedUi)}
        >
          <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Layers size={13} />
            Contexto de UI (Pantalla Activa)
          </span>
          {showAdvancedUi ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
        </div>

        {showAdvancedUi && (
          <div style={{ marginTop: '8px' }}>
            <div className="form-group">
              <label className="form-label">URL Activa en SIGIRES</label>
              <input
                type="text"
                className="form-input"
                value={uiContext.url}
                onChange={(e) => setUiContext({ ...uiContext, url: e.target.value })}
              />
            </div>

            <div className="grid-2col">
              <div className="form-group">
                <label className="form-label">Página Actual</label>
                <input
                  type="text"
                  className="form-input"
                  value={uiContext.pagina_actual}
                  onChange={(e) => setUiContext({ ...uiContext, pagina_actual: e.target.value })}
                />
              </div>
              <div className="form-group">
                <label className="form-label">Módulo</label>
                <input
                  type="text"
                  className="form-input"
                  value={uiContext.modulo}
                  onChange={(e) => setUiContext({ ...uiContext, modulo: e.target.value })}
                />
              </div>
            </div>

            <div className="grid-2col">
              <div className="form-group">
                <label className="form-label">Estado Cargue</label>
                <select
                  className="form-select"
                  value={uiContext.estado_cargue_actual}
                  onChange={(e) => setUiContext({ ...uiContext, estado_cargue_actual: e.target.value })}
                >
                  <option value="CON_ERRORES">CON_ERRORES</option>
                  <option value="RECHAZADO">RECHAZADO</option>
                  <option value="EXITOSO">EXITOSO</option>
                  <option value="NO_APLICA">NO_APLICA</option>
                </select>
              </div>

              <div className="form-group">
                <label className="form-label">Formato Formulario / Archivo</label>
                <select
                  className="form-select"
                  value={uiContext.formato_archivo}
                  onChange={(e) => setUiContext({ ...uiContext, formato_archivo: e.target.value })}
                >
                  <option value="FORMULARIO_CLINICO_CSV">Formulario Clínico / Enfermería (CSV)</option>
                  <option value="REPORTE_MEDICO_XML">Reporte Médico (XML)</option>
                  <option value="RIPS_SOPORTE_JSON">Soporte RIPS / Facturación (JSON)</option>
                  <option value="ANEXO_TECNICO_ZIP">Anexo Técnico Plano (TXT/ZIP)</option>
                  <option value="NO_APLICA">No aplica</option>
                </select>
              </div>
            </div>

            <div className="grid-2col">
              <div className="form-group">
                <label className="form-label">Botón Activo</label>
                <input
                  type="text"
                  className="form-input"
                  value={uiContext.active_button_id || ''}
                  onChange={(e) => setUiContext({ ...uiContext, active_button_id: e.target.value })}
                />
              </div>
              <div className="form-group">
                <label className="form-label">Campo en Foco</label>
                <input
                  type="text"
                  className="form-input"
                  value={uiContext.field_in_focus || ''}
                  onChange={(e) => setUiContext({ ...uiContext, field_in_focus: e.target.value })}
                />
              </div>
            </div>
          </div>
        )}
      </div>

      {/* 6. User Context Simulator */}
      <div className="panel-section">
        <div 
          className="section-label" 
          style={{ cursor: 'pointer', marginBottom: showAdvancedUser ? '12px' : '0' }}
          onClick={() => setShowAdvancedUser(!showAdvancedUser)}
        >
          <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <UserCheck size={13} />
            Contexto de Usuario & Permisos
          </span>
          {showAdvancedUser ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
        </div>

        {showAdvancedUser && (
          <div style={{ marginTop: '8px' }}>
            <div className="grid-2col">
              <div className="form-group">
                <label className="form-label">Usuario</label>
                <input
                  type="text"
                  className="form-input"
                  value={userContext.usuario}
                  onChange={(e) => setUserContext({ ...userContext, usuario: e.target.value })}
                />
              </div>
              <div className="form-group">
                <label className="form-label">EPS</label>
                <input
                  type="text"
                  className="form-input"
                  value={userContext.eps}
                  onChange={(e) => setUserContext({ ...userContext, eps: e.target.value })}
                />
              </div>
            </div>

            <div className="grid-2col">
              <div className="form-group">
                <label className="form-label">Código Habilitación IPS</label>
                <input
                  type="text"
                  className="form-input"
                  value={userContext.ips_code}
                  onChange={(e) => setUserContext({ ...userContext, ips_code: e.target.value })}
                />
              </div>
              <div className="form-group">
                <label className="form-label">Nombre IPS</label>
                <input
                  type="text"
                  className="form-input"
                  value={userContext.ips_nombre || ''}
                  onChange={(e) => setUserContext({ ...userContext, ips_nombre: e.target.value })}
                />
              </div>
            </div>

            <div className="form-group">
              <label className="form-label">Rol / Perfil del Profesional</label>
              <select
                className="form-select"
                value={userContext.permisos}
                onChange={(e) => setUserContext({ ...userContext, permisos: e.target.value })}
              >
                <option value="PERFIL_IPS_MEDICO">PERFIL_IPS_MEDICO (Médico)</option>
                <option value="PERFIL_IPS_ENFERMERO">PERFIL_IPS_ENFERMERO (Enfermero/a)</option>
                <option value="PERFIL_IPS_RADICADOR">PERFIL_IPS_RADICADOR (Radicador)</option>
                <option value="PERFIL_EPS_AUDITOR">PERFIL_EPS_AUDITOR (Auditor)</option>
              </select>
            </div>
          </div>
        )}
      </div>
    </aside>
  );
}
