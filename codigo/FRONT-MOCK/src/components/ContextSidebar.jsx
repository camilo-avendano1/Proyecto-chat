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
  ChevronUp,
  Sliders,
  Braces
} from 'lucide-react';

export const TENANT_PRESETS = {
  otra_empresa: {
    client_id: 'otra_empresa',
    client_name: 'Empresa Corporativa (Genérica)',
    api_key: 'pk_live_otraempresa_1a2b3c4d5e6f7a8b',
    organization: 'División Operativa Central',
    unit_code: 'CORP-01',
    default_user: 'ana.martinez',
    default_role: 'ANALISTA_OPERACIONES',
    default_url: 'https://portal.empresa.com/operaciones',
    default_view: 'PORTAL_OPERATIVO',
    default_module: 'OPERACIONES',
  },
  sura: {
    client_id: 'sigires',
    client_name: 'SIGIRES (Procex Software S.A.S)',
    eps_id: 'eps_sura_01',
    eps_nombre: 'EPS Sura - Regional Nor-Occidente',
    api_key: 'pk_live_sigires_8f9a2b1c3d4e5f6a',
    ips_code: '631300040301',
    ips_nombre: 'Clínica Las Américas',
    eps_code: 'EPS_SURA',
    organization: 'EPS_SURA',
    unit_code: '631300040301',
    default_user: 'dr.juan.perez',
    default_role: 'PERFIL_IPS_MEDICO',
    default_url: 'https://sigires.procex.co/formularios/validacion',
    default_view: 'REGISTRO_FORMULARIOS',
    default_module: 'FORMULARIOS_CLINICOS',
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
    organization: 'EPS_SANITAS',
    unit_code: '110010999901',
    default_user: 'dr.juan.perez',
    default_role: 'PERFIL_IPS_MEDICO',
    default_url: 'https://sigires.procex.co/formularios/validacion',
    default_view: 'REGISTRO_FORMULARIOS',
    default_module: 'FORMULARIOS_CLINICOS',
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
    organization: 'EPS_NUEVA',
    unit_code: '050010001201',
    default_user: 'dr.juan.perez',
    default_role: 'PERFIL_IPS_MEDICO',
    default_url: 'https://sigires.procex.co/formularios/validacion',
    default_view: 'REGISTRO_FORMULARIOS',
    default_module: 'FORMULARIOS_CLINICOS',
  },
};

export const SCENARIO_PRESETS = [
  {
    id: 'consulta_minima',
    name: 'Genérico: Consulta Mínima (Solo Query)',
    minimalMode: true,
    query: '¿Cómo se aprueba una orden de compra?',
    system_logs: '',
    extras_json: '',
  },
  {
    id: 'corporativo_contexto',
    name: 'Corporativo: Con Contexto y Extras',
    minimalMode: false,
    target_tenant: 'otra_empresa',
    query: '¿Cuál es el límite de aprobación para compras de tecnología?',
    system_logs: '',
    extras_json: JSON.stringify(
      { departamento: 'compras', nivel_aprobacion: 'gerencia', moneda: 'COP' },
      null,
      2
    ),
    context: {
      url: 'https://portal.empresa.com/compras/ordenes',
      view: 'APROBACION_ORDENES',
      module: 'COMPRAS',
      status: 'EN_REVISION',
      file_format: 'ORDEN_COMPRA_WEB',
      active_button_id: 'btn_aprobar_orden',
      field_in_focus: 'monto_total',
    },
    user: {
      id: 'ana.martinez',
      organization: 'División Operativa Central',
      unit_code: 'CORP-01',
      role: 'ANALISTA_COMPRAS',
    },
  },
  {
    id: 'sigires_enfermeria',
    name: 'Cliente SIGIRES: Formulario + Log',
    minimalMode: false,
    target_tenant_group: 'sigires',
    query: 'Al subir el formulario de enfermería me rechaza el registro de signos vitales',
    system_logs:
      "Fila: 18 | Campo: 6 | Variable 'Presion_Arterial' fuera de formato esperado. Error CE_CAMPO_006_FMT",
    extras_json: JSON.stringify(
      { formato: 'FORMULARIO_CLINICO_CSV', proceso: 'enfermeria' },
      null,
      2
    ),
    context: {
      url: 'https://sigires.procex.co/formularios/enfermeria',
      view: 'REGISTRO_ENFERMERIA',
      module: 'FORMULARIOS_CLINICOS',
      status: 'CON_ERRORES',
      file_format: 'FORMULARIO_CLINICO_CSV',
      active_button_id: 'btn_validar_formulario',
      field_in_focus: 'campo_presion_arterial',
    },
    user: {
      id: 'enf.laura.gomez',
      organization: 'EPS_SURA',
      unit_code: '631300040301',
      role: 'PERFIL_IPS_ENFERMERO',
    },
  },
  {
    id: 'sigires_delimitador',
    name: 'Cliente SIGIRES: Error Formato Fase 1',
    minimalMode: false,
    target_tenant_group: 'sigires',
    query: 'El validador rechaza el archivo plano en Fase 1 por delimitador y columnas',
    system_logs:
      'FASE 1 (CA) - Error CA_FILE_001_DELIM: Fila 3 tiene 19 columnas delimitadas por pipe (|) y la estructura exige 22.',
    extras_json: JSON.stringify(
      { fase: 'FASE_1_CA', formato: 'ANEXO_TECNICO_TXT' },
      null,
      2
    ),
    context: {
      url: 'https://sigires.procex.co/carga-archivos/validador',
      view: 'CARGA_ARCHIVOS_NORMATIVOS',
      module: 'CARGA_ARCHIVOS',
      status: 'RECHAZADO',
      file_format: 'ANEXO_TECNICO_TXT',
      active_button_id: 'btn_validar_archivo',
      field_in_focus: 'archivo_plano_txt',
    },
    user: {
      id: 'rad.carlos.mendez',
      organization: 'EPS_SURA',
      unit_code: '631300040301',
      role: 'PERFIL_IPS_RADICADOR',
    },
  },
  {
    id: 'saludo',
    name: 'Saludo Rápido (Fast-Path 0 Tokens)',
    minimalMode: true,
    query: '¡Hola! Buenos días, ¿en qué me puedes ayudar hoy?',
    system_logs: '',
    extras_json: '',
  },
  {
    id: 'guardrail',
    name: 'Guardrail: Fuera de Dominio',
    minimalMode: true,
    query: '¿Cuál es la mejor receta para preparar un pastel de chocolate?',
    system_logs: '',
    extras_json: '',
  },
];

export default function ContextSidebar({
  tenantKey,
  setTenantKey,
  minimalMode,
  setMinimalMode,
  sessionData,
  onInitSession,
  isSessionLoading,
  uiContext,
  setUiContext,
  userContext,
  setUserContext,
  systemLogs,
  setSystemLogs,
  extrasText,
  setExtrasText,
  extrasError,
  setExtrasError,
  onSelectScenario,
  activeScenarioId,
}) {
  const [showAdvancedUi, setShowAdvancedUi] = useState(false);
  const [showAdvancedUser, setShowAdvancedUser] = useState(false);
  const [showExtras, setShowExtras] = useState(true);

  const handleTenantChange = (key) => {
    setTenantKey(key);
    const preset = TENANT_PRESETS[key];
    if (preset) {
      setUserContext({
        id: preset.default_user,
        organization: preset.organization,
        unit_code: preset.unit_code,
        role: preset.default_role,
      });
      setUiContext((prev) => ({
        ...prev,
        url: preset.default_url,
        view: preset.default_view,
        module: preset.default_module,
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
            <option value="otra_empresa">otra_empresa - Empresa Corporativa (Genérica)</option>
            <option value="sura">SIGIRES - EPS Sura (Regional Nor-Occidente)</option>
            <option value="sanitas">SIGIRES - EPS Sanitas (IPS San Rafael)</option>
            <option value="nuevaeps">SIGIRES - Nueva EPS (Consorcio Salud)</option>
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
                <span className="session-key">Cliente:</span>
                <span
                  className="session-val"
                  title={`${sessionData.client_name || ''} (${sessionData.client_id || ''})`}
                >
                  {sessionData.client_name
                    ? `${sessionData.client_name} (${sessionData.client_id})`
                    : sessionData.client_id}
                </span>
              </div>
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

      {/* 3. Escenarios Preconfigurados */}
      <div className="panel-section">
        <div className="section-label">
          <span>Escenarios Preconfigurados</span>
          <Sparkles size={13} style={{ color: '#10b981' }} />
        </div>
        <p style={{ fontSize: '0.74rem', color: 'var(--text-muted)', marginBottom: '8px' }}>
          Carga en 1 clic escenarios mínimos genéricos, corporativos enriquecidos o de clientes específicos (ej. SIGIRES):
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

      {/* 4. Minimal Mode Toggle */}
      <div className="panel-section">
        <div className="section-label" style={{ marginBottom: '8px' }}>
          <span>Payload de Petición</span>
          <Sliders size={13} />
        </div>
        <label
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: '10px',
            padding: '8px 10px',
            borderRadius: '8px',
            background: minimalMode ? 'rgba(16, 185, 129, 0.12)' : 'rgba(255, 255, 255, 0.04)',
            border: minimalMode ? '1px solid rgba(16, 185, 129, 0.35)' : '1px solid var(--border-subtle)',
            cursor: 'pointer',
            fontSize: '0.78rem',
            color: 'var(--text-main)',
          }}
        >
          <span>Modo Petición Mínima (solo query)</span>
          <input
            type="checkbox"
            checked={minimalMode}
            onChange={(e) => setMinimalMode(e.target.checked)}
            style={{ accentColor: '#10b981', width: '16px', height: '16px', cursor: 'pointer' }}
          />
        </label>
        <p style={{ fontSize: '0.7rem', color: 'var(--text-dim)', marginTop: '6px', lineHeight: '1.35' }}>
          {minimalMode
            ? 'Activo: envía únicamente {"query"} (y conversation_history si existe).'
            : 'Enriquecido: adjunta user, context, logs y extras no vacíos junto con query.'}
        </p>
      </div>

      {/* 5. System Logs Input */}
      <div className="panel-section" style={{ opacity: minimalMode ? 0.55 : 1 }}>
        <div className="section-label">
          <span>Trazas / Logs (logs)</span>
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
            Trazas de error opcionales (si se adjuntan, el backend extrae código y fase):
          </label>
          <textarea
            className="form-textarea"
            placeholder="Ej: Fila: 18 | Campo: 6 | Error CE_CAMPO_006_FMT..."
            value={systemLogs}
            onChange={(e) => setSystemLogs(e.target.value)}
          />
        </div>
      </div>

      {/* 6. UI / Screen Context Simulator */}
      <div className="panel-section" style={{ opacity: minimalMode ? 0.55 : 1 }}>
        <div
          className="section-label"
          style={{ cursor: 'pointer', marginBottom: showAdvancedUi ? '12px' : '0' }}
          onClick={() => setShowAdvancedUi(!showAdvancedUi)}
        >
          <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Layers size={13} />
            Contexto de Pantalla (context)
          </span>
          {showAdvancedUi ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
        </div>

        {showAdvancedUi && (
          <div style={{ marginTop: '8px' }}>
            <div className="form-group">
              <label className="form-label">URL / Vista Activa</label>
              <input
                type="text"
                className="form-input"
                value={uiContext.url || ''}
                onChange={(e) => setUiContext({ ...uiContext, url: e.target.value })}
              />
            </div>

            <div className="grid-2col">
              <div className="form-group">
                <label className="form-label">Vista / Página</label>
                <input
                  type="text"
                  className="form-input"
                  value={uiContext.view || ''}
                  onChange={(e) => setUiContext({ ...uiContext, view: e.target.value })}
                />
              </div>
              <div className="form-group">
                <label className="form-label">Módulo</label>
                <input
                  type="text"
                  className="form-input"
                  value={uiContext.module || ''}
                  onChange={(e) => setUiContext({ ...uiContext, module: e.target.value })}
                />
              </div>
            </div>

            <div className="grid-2col">
              <div className="form-group">
                <label className="form-label">Estado</label>
                <input
                  type="text"
                  className="form-input"
                  list="status-suggestions"
                  placeholder="Opcional"
                  value={uiContext.status || ''}
                  onChange={(e) => setUiContext({ ...uiContext, status: e.target.value })}
                />
                <datalist id="status-suggestions">
                  <option value="EN_REVISION" />
                  <option value="CON_ERRORES" />
                  <option value="RECHAZADO" />
                  <option value="EXITOSO" />
                </datalist>
              </div>

              <div className="form-group">
                <label className="form-label">Formato / Tipo</label>
                <input
                  type="text"
                  className="form-input"
                  list="format-suggestions"
                  placeholder="Opcional (CSV, JSON...)"
                  value={uiContext.file_format || ''}
                  onChange={(e) => setUiContext({ ...uiContext, file_format: e.target.value })}
                />
                <datalist id="format-suggestions">
                  <option value="ORDEN_COMPRA_WEB" />
                  <option value="FORMULARIO_CLINICO_CSV" />
                  <option value="REPORTE_MEDICO_XML" />
                  <option value="RIPS_SOPORTE_JSON" />
                  <option value="ANEXO_TECNICO_TXT" />
                </datalist>
              </div>
            </div>

            <div className="grid-2col">
              <div className="form-group">
                <label className="form-label">Acción / Botón Activo</label>
                <input
                  type="text"
                  className="form-input"
                  placeholder="Opcional"
                  value={uiContext.active_button_id || ''}
                  onChange={(e) => setUiContext({ ...uiContext, active_button_id: e.target.value })}
                />
              </div>
              <div className="form-group">
                <label className="form-label">Campo en Foco</label>
                <input
                  type="text"
                  className="form-input"
                  placeholder="Opcional"
                  value={uiContext.field_in_focus || ''}
                  onChange={(e) => setUiContext({ ...uiContext, field_in_focus: e.target.value })}
                />
              </div>
            </div>
          </div>
        )}
      </div>

      {/* 7. User Context Simulator */}
      <div className="panel-section" style={{ opacity: minimalMode ? 0.55 : 1 }}>
        <div
          className="section-label"
          style={{ cursor: 'pointer', marginBottom: showAdvancedUser ? '12px' : '0' }}
          onClick={() => setShowAdvancedUser(!showAdvancedUser)}
        >
          <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <UserCheck size={13} />
            Contexto de Usuario (user)
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
                  value={userContext.id || ''}
                  onChange={(e) => setUserContext({ ...userContext, id: e.target.value })}
                />
              </div>
              <div className="form-group">
                <label className="form-label">Organización / División</label>
                <input
                  type="text"
                  className="form-input"
                  value={userContext.organization || ''}
                  onChange={(e) => setUserContext({ ...userContext, organization: e.target.value })}
                />
              </div>
            </div>

            <div className="grid-2col">
              <div className="form-group">
                <label className="form-label">Código de Sede / Unidad</label>
                <input
                  type="text"
                  className="form-input"
                  value={userContext.unit_code || ''}
                  onChange={(e) => setUserContext({ ...userContext, unit_code: e.target.value })}
                />
              </div>
              <div className="form-group">
                <label className="form-label">Rol del Usuario</label>
                <input
                  type="text"
                  className="form-input"
                  list="role-suggestions"
                  value={userContext.role || ''}
                  onChange={(e) => setUserContext({ ...userContext, role: e.target.value })}
                />
                <datalist id="role-suggestions">
                  <option value="ANALISTA_OPERACIONES" />
                  <option value="ANALISTA_COMPRAS" />
                  <option value="COLABORADOR" />
                  <option value="SUPERVISOR" />
                  <option value="PERFIL_IPS_MEDICO" />
                  <option value="PERFIL_IPS_ENFERMERO" />
                  <option value="PERFIL_IPS_RADICADOR" />
                  <option value="PERFIL_EPS_AUDITOR" />
                </datalist>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* 8. Search Extras JSON Simulator */}
      <div className="panel-section" style={{ opacity: minimalMode ? 0.55 : 1 }}>
        <div
          className="section-label"
          style={{ cursor: 'pointer', marginBottom: showExtras ? '10px' : '0' }}
          onClick={() => setShowExtras(!showExtras)}
        >
          <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Braces size={13} />
            Extras JSON para Búsqueda
          </span>
          {showExtras ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
        </div>

        {showExtras && (
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
              <label className="form-label" style={{ marginBottom: 0 }}>
                Metadatos opcionales (snake_case, escalares):
              </label>
              {extrasText && (
                <button
                  className="chip-btn"
                  style={{ fontSize: '0.68rem', padding: '1px 6px' }}
                  onClick={() => {
                    setExtrasText('');
                    setExtrasError('');
                  }}
                >
                  Limpiar
                </button>
              )}
            </div>
            <textarea
              className="form-textarea"
              placeholder='{"departamento": "compras", "moneda": "COP"}'
              value={extrasText}
              onChange={(e) => {
                setExtrasText(e.target.value);
                if (extrasError) setExtrasError('');
              }}
            />
            {extrasError && (
              <p style={{ color: '#f87171', fontSize: '0.72rem', marginTop: '4px' }}>
                {extrasError}
              </p>
            )}
          </div>
        )}
      </div>
    </aside>
  );
}
