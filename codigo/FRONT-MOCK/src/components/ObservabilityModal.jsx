import React, { useState, useEffect } from 'react';
import { 
  X, 
  BarChart3, 
  ShieldCheck, 
  DollarSign, 
  Cpu, 
  Zap, 
  RefreshCw, 
  Clock, 
  AlertTriangle,
  FileText,
  Lock,
  UserCheck,
  LogOut,
  Layers,
  Database
} from 'lucide-react';
import { 
  adminLogin,
  fetchAdminSecurityLogs,
  fetchAdminMessageLogs,
  fetchAdminUsageSummary,
  fetchAdminUsageByUser,
  fetchAdminUsageByTenant,
  fetchAdminUsageByRole,
  fetchAdminUsageByModel,
  fetchUsageSummary, 
  fetchUsageByUser, 
  fetchSecurityLogs, 
  fetchMessageLogs 
} from '../services/api';

export default function ObservabilityModal({ activeTab, onClose }) {
  // Admin Auth State
  const [adminToken, setAdminToken] = useState(() => sessionStorage.getItem('saas_admin_token') || '');
  const [adminUser, setAdminUser] = useState(() => {
    try {
      return JSON.parse(sessionStorage.getItem('saas_admin_user') || 'null');
    } catch {
      return null;
    }
  });

  // Login Form State
  const [loginUsername, setLoginUsername] = useState('superadmin');
  const [loginPassword, setLoginPassword] = useState('AdminSuperSecret2025!');
  const [loginError, setLoginError] = useState('');
  const [isLoggingIn, setIsLoggingIn] = useState(false);

  // Tab View State: 'usage', 'security', 'messages', 'roles_models'
  const [currentView, setCurrentView] = useState(activeTab === 'security' ? 'security' : 'usage');
  const [subTab, setSubTab] = useState('summary'); // 'summary', 'roles', 'models', 'tenants'

  // Data States
  const [summary, setSummary] = useState(null);
  const [userUsage, setUserUsage] = useState([]);
  const [roleUsage, setRoleUsage] = useState([]);
  const [modelUsage, setModelUsage] = useState([]);
  const [tenantUsage, setTenantUsage] = useState([]);
  const [securityLogs, setSecurityLogs] = useState([]);
  const [messageLogs, setMessageLogs] = useState([]);
  const [loading, setLoading] = useState(false);

  const handleLogin = async (e) => {
    if (e) e.preventDefault();
    setLoginError('');
    setIsLoggingIn(true);
    try {
      const data = await adminLogin({ username: loginUsername, password: loginPassword });
      setAdminToken(data.access_token);
      setAdminUser(data.user);
      sessionStorage.setItem('saas_admin_token', data.access_token);
      sessionStorage.setItem('saas_admin_user', JSON.stringify(data.user));
    } catch (err) {
      setLoginError(err.message || 'Error al autenticar administrador');
    } finally {
      setIsLoggingIn(false);
    }
  };

  const handleLogout = () => {
    setAdminToken('');
    setAdminUser(null);
    sessionStorage.removeItem('saas_admin_token');
    sessionStorage.removeItem('saas_admin_user');
  };

  const loadData = async () => {
    setLoading(true);
    try {
      if (adminToken) {
        // Authenticated Admin Flow (Gateway :8003 and Central Logs DB)
        if (currentView === 'usage') {
          const [sum, users, roles, models, tenants] = await Promise.all([
            fetchAdminUsageSummary({ token: adminToken }).catch(() => null),
            fetchAdminUsageByUser({ token: adminToken }).catch(() => []),
            fetchAdminUsageByRole({ token: adminToken }).catch(() => []),
            fetchAdminUsageByModel({ token: adminToken }).catch(() => []),
            fetchAdminUsageByTenant({ token: adminToken }).catch(() => []),
          ]);
          setSummary(sum);
          setUserUsage(Array.isArray(users) ? users : []);
          setRoleUsage(Array.isArray(roles) ? roles : []);
          setModelUsage(Array.isArray(models) ? models : []);
          setTenantUsage(Array.isArray(tenants) ? tenants : []);
        } else if (currentView === 'security') {
          const sec = await fetchAdminSecurityLogs({ token: adminToken }).catch(() => ({ records: [] }));
          setSecurityLogs(sec.records || []);
        } else if (currentView === 'messages') {
          const msg = await fetchAdminMessageLogs({ token: adminToken }).catch(() => ({ records: [] }));
          setMessageLogs(msg.records || []);
        }
      } else {
        // Unauthenticated Legacy Fallback (Local in-memory buffer)
        if (currentView === 'usage') {
          const [sum, users] = await Promise.all([
            fetchUsageSummary().catch(() => null),
            fetchUsageByUser().catch(() => []),
          ]);
          setSummary(sum);
          setUserUsage(Array.isArray(users) ? users : []);
        } else {
          const [sec, msg] = await Promise.all([
            fetchSecurityLogs().catch(() => []),
            fetchMessageLogs().catch(() => []),
          ]);
          setSecurityLogs(sec);
          setMessageLogs(msg);
        }
      }
    } catch (err) {
      console.error('Error fetching observability data:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [currentView, adminToken]);

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-card" style={{ maxWidth: '1050px', width: '95%' }} onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="modal-header" style={{ flexWrap: 'wrap', gap: '10px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap' }}>
            <div className="nav-tabs" style={{ background: 'rgba(255,255,255,0.06)' }}>
              <button 
                className={`nav-tab-btn ${currentView === 'usage' ? 'active' : ''}`}
                onClick={() => setCurrentView('usage')}
              >
                <BarChart3 size={15} />
                <span>Métricas de Modelos (LLM Gateway)</span>
              </button>
              <button 
                className={`nav-tab-btn ${currentView === 'security' ? 'active' : ''}`}
                onClick={() => setCurrentView('security')}
              >
                <ShieldCheck size={15} />
                <span>Auditoría Central de Seguridad</span>
              </button>
              <button 
                className={`nav-tab-btn ${currentView === 'messages' ? 'active' : ''}`}
                onClick={() => setCurrentView('messages')}
              >
                <FileText size={15} />
                <span>Trazas Centrales de Mensajes</span>
              </button>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            {adminUser && (
              <div style={{ 
                display: 'flex', 
                alignItems: 'center', 
                gap: '8px', 
                background: 'rgba(255,255,255,0.05)', 
                padding: '4px 10px', 
                borderRadius: '6px',
                border: '1px solid var(--border-subtle)',
                fontSize: '0.78rem'
              }}>
                <UserCheck size={14} style={{ color: '#34d399' }} />
                <span><strong>{adminUser.username}</strong></span>
                <span style={{ 
                  background: adminUser.role === 'SUPERADMIN' ? 'rgba(99, 102, 241, 0.25)' : 'rgba(16, 185, 129, 0.25)',
                  color: adminUser.role === 'SUPERADMIN' ? '#a5b4fc' : '#34d399',
                  padding: '2px 6px',
                  borderRadius: '4px',
                  fontWeight: 600,
                  fontSize: '0.7rem'
                }}>
                  {adminUser.role}
                </span>
                <button 
                  onClick={handleLogout} 
                  title="Cerrar sesión de administrador"
                  style={{ background: 'transparent', border: 'none', color: '#f87171', cursor: 'pointer', display: 'flex', alignItems: 'center' }}
                >
                  <LogOut size={13} />
                </button>
              </div>
            )}
            <button className="btn-secondary" onClick={loadData} disabled={loading} title="Actualizar datos">
              <RefreshCw size={14} className={loading ? 'spin' : ''} />
            </button>
            <button className="btn-secondary" onClick={onClose} title="Cerrar ventana">
              <X size={15} />
            </button>
          </div>
        </div>

        {/* Admin Login Prompt (if not logged in) */}
        {!adminToken && (
          <div style={{ 
            background: 'linear-gradient(135deg, rgba(30, 41, 59, 0.95), rgba(15, 23, 42, 0.95))',
            padding: '16px 20px', 
            borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
            display: 'flex',
            flexDirection: 'column',
            gap: '12px'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '8px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Lock size={16} style={{ color: '#f59e0b' }} />
                <span style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-bright)' }}>
                  Inicia sesión de Administrador para ver métricas segmentadas y la base de datos central de auditoría
                </span>
              </div>
              <div style={{ display: 'flex', gap: '6px' }}>
                <button 
                  type="button"
                  className="btn-secondary"
                  style={{ fontSize: '0.74rem', padding: '3px 8px' }}
                  onClick={() => {
                    setLoginUsername('superadmin');
                    setLoginPassword('AdminSuperSecret2025!');
                  }}
                >
                  Preset: Superadmin
                </button>
                <button 
                  type="button"
                  className="btn-secondary"
                  style={{ fontSize: '0.74rem', padding: '3px 8px' }}
                  onClick={() => {
                    setLoginUsername('sigires_admin');
                    setLoginPassword('AdminSigires2025!');
                  }}
                >
                  Preset: Admin SIGIRES
                </button>
              </div>
            </div>

            <form onSubmit={handleLogin} style={{ display: 'flex', gap: '10px', alignItems: 'center', flexWrap: 'wrap' }}>
              <input 
                type="text"
                placeholder="Usuario administrador"
                value={loginUsername}
                onChange={(e) => setLoginUsername(e.target.value)}
                style={{
                  background: 'rgba(0, 0, 0, 0.3)',
                  border: '1px solid var(--border-subtle)',
                  borderRadius: '4px',
                  padding: '6px 10px',
                  color: 'white',
                  fontSize: '0.82rem',
                  minWidth: '160px'
                }}
              />
              <input 
                type="password"
                placeholder="Contraseña"
                value={loginPassword}
                onChange={(e) => setLoginPassword(e.target.value)}
                style={{
                  background: 'rgba(0, 0, 0, 0.3)',
                  border: '1px solid var(--border-subtle)',
                  borderRadius: '4px',
                  padding: '6px 10px',
                  color: 'white',
                  fontSize: '0.82rem',
                  minWidth: '180px'
                }}
              />
              <button 
                type="submit" 
                className="btn-primary" 
                disabled={isLoggingIn}
                style={{ padding: '6px 14px', fontSize: '0.82rem' }}
              >
                {isLoggingIn ? 'Verificando...' : 'Autenticar'}
              </button>
              {loginError && (
                <span style={{ color: '#f87171', fontSize: '0.76rem' }}>{loginError}</span>
              )}
            </form>
          </div>
        )}

        {/* Body */}
        <div className="modal-body">
          {currentView === 'usage' && (
            <div>
              {/* Summary Cards */}
              <div className="metrics-grid">
                <div className="metric-card">
                  <div className="metric-title">Total Tokens Procesados</div>
                  <div className="metric-value">
                    {summary?.total_tokens?.toLocaleString() || 0}
                  </div>
                  <div className="metric-sub">
                    In: {summary?.total_tokens_input || 0} | Out: {summary?.total_tokens_output || 0}
                  </div>
                </div>

                <div className="metric-card">
                  <div className="metric-title">Costo Estimado (USD)</div>
                  <div className="metric-value" style={{ color: '#34d399' }}>
                    ${summary?.total_cost_usd?.toFixed(6) || '0.000000'}
                  </div>
                  <div className="metric-sub">Tarifa multi-tenant ponderada</div>
                </div>

                <div className="metric-card">
                  <div className="metric-title">Ahorro Fast-Path</div>
                  <div className="metric-value" style={{ color: '#60a5fa' }}>
                    {summary?.saved_fast_path_calls || 0}
                  </div>
                  <div className="metric-sub">0 tokens en saludos / guardrails</div>
                </div>

                <div className="metric-card">
                  <div className="metric-title">Peticiones Registradas</div>
                  <div className="metric-value" style={{ color: '#a78bfa' }}>
                    {summary?.total_records || 0}
                  </div>
                  <div className="metric-sub">
                    LLM: {summary?.total_llm_calls ?? '-'} | Direct: {summary?.saved_fast_path_calls ?? '-'}
                  </div>
                </div>
              </div>

              {/* Subtabs for Segmentation */}
              <div style={{ display: 'flex', gap: '8px', marginBottom: '14px', borderBottom: '1px solid var(--border-subtle)', paddingBottom: '8px' }}>
                <button 
                  className={`btn-secondary ${subTab === 'summary' ? 'active' : ''}`}
                  onClick={() => setSubTab('summary')}
                  style={{ fontSize: '0.78rem', background: subTab === 'summary' ? 'var(--primary-color)' : '' }}
                >
                  Por Usuario ({userUsage.length})
                </button>
                <button 
                  className={`btn-secondary ${subTab === 'roles' ? 'active' : ''}`}
                  onClick={() => setSubTab('roles')}
                  style={{ fontSize: '0.78rem', background: subTab === 'roles' ? 'var(--primary-color)' : '' }}
                >
                  Segmentación por Rol ({roleUsage.length})
                </button>
                <button 
                  className={`btn-secondary ${subTab === 'models' ? 'active' : ''}`}
                  onClick={() => setSubTab('models')}
                  style={{ fontSize: '0.78rem', background: subTab === 'models' ? 'var(--primary-color)' : '' }}
                >
                  Modelos & Proveedor ({modelUsage.length})
                </button>
                <button 
                  className={`btn-secondary ${subTab === 'tenants' ? 'active' : ''}`}
                  onClick={() => setSubTab('tenants')}
                  style={{ fontSize: '0.78rem', background: subTab === 'tenants' ? 'var(--primary-color)' : '' }}
                >
                  Por Empresa / División ({tenantUsage.length})
                </button>
              </div>

              {/* Subtab: By User */}
              {subTab === 'summary' && (
                <div style={{ overflowX: 'auto', background: 'rgba(0,0,0,0.25)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-subtle)' }}>
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Usuario</th>
                        <th>Tenant ID</th>
                        <th>Total Req</th>
                        <th>Llamadas LLM</th>
                        <th>Fast-Path</th>
                        <th>Tokens In/Out</th>
                        <th>Costo (USD)</th>
                      </tr>
                    </thead>
                    <tbody>
                      {userUsage.length === 0 ? (
                        <tr>
                          <td colSpan="7" style={{ textAlign: 'center', padding: '24px', color: 'var(--text-dim)' }}>
                            No hay registros de consumo aún.
                          </td>
                        </tr>
                      ) : (
                        userUsage.map((u, i) => (
                          <tr key={i}>
                            <td style={{ fontWeight: 600 }}>{u.usuario}</td>
                            <td style={{ fontFamily: 'var(--font-mono)', fontSize: '0.72rem', color: 'var(--text-dim)' }}>
                              {u.tenant_id ? u.tenant_id.slice(0, 16) + '...' : 'default'}
                            </td>
                            <td>{u.total_requests}</td>
                            <td>{u.llm_requests ?? u.total_requests}</td>
                            <td><span className="badge-fastpath">{u.fast_path_requests || 0}</span></td>
                            <td>{u.total_tokens_input} / {u.total_tokens_output}</td>
                            <td style={{ color: '#34d399', fontWeight: 600 }}>${(u.total_cost_usd || 0).toFixed(6)}</td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
              )}

              {/* Subtab: By Role */}
              {subTab === 'roles' && (
                <div style={{ overflowX: 'auto', background: 'rgba(0,0,0,0.25)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-subtle)' }}>
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Rol Asignado</th>
                        <th>Total Consultas</th>
                        <th>Tokens Entrada</th>
                        <th>Tokens Salida</th>
                        <th>Tokens Totales</th>
                        <th>Costo Total (USD)</th>
                      </tr>
                    </thead>
                    <tbody>
                      {roleUsage.length === 0 ? (
                        <tr>
                          <td colSpan="6" style={{ textAlign: 'center', padding: '24px', color: 'var(--text-dim)' }}>
                            No hay desglose por rol disponible. Autentique un admin para consultar el LLM Gateway.
                          </td>
                        </tr>
                      ) : (
                        roleUsage.map((r, i) => (
                          <tr key={i}>
                            <td style={{ fontWeight: 600, color: '#a5b4fc' }}>{r.rol || 'no_definido'}</td>
                            <td>{r.total_requests}</td>
                            <td>{r.total_tokens_input}</td>
                            <td>{r.total_tokens_output}</td>
                            <td style={{ fontWeight: 600 }}>{r.total_tokens}</td>
                            <td style={{ color: '#34d399', fontWeight: 600 }}>${(r.total_cost_usd || 0).toFixed(6)}</td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
              )}

              {/* Subtab: By Model */}
              {subTab === 'models' && (
                <div style={{ overflowX: 'auto', background: 'rgba(0,0,0,0.25)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-subtle)' }}>
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Modelo Inferencia</th>
                        <th>Proveedor</th>
                        <th>Peticiones</th>
                        <th>Tokens Totales</th>
                        <th>Latencia Promedio</th>
                        <th>Costo (USD)</th>
                      </tr>
                    </thead>
                    <tbody>
                      {modelUsage.length === 0 ? (
                        <tr>
                          <td colSpan="6" style={{ textAlign: 'center', padding: '24px', color: 'var(--text-dim)' }}>
                            No hay desglose por modelo disponible.
                          </td>
                        </tr>
                      ) : (
                        modelUsage.map((m, i) => (
                          <tr key={i}>
                            <td style={{ fontWeight: 600 }}>{m.model || 'sin_modelo'}</td>
                            <td><span style={{ color: '#60a5fa', fontSize: '0.74rem' }}>{m.provider}</span></td>
                            <td>{m.total_requests}</td>
                            <td>{m.total_tokens}</td>
                            <td>{m.avg_latencia_ms ? `${m.avg_latencia_ms}ms` : 'N/A'}</td>
                            <td style={{ color: '#34d399', fontWeight: 600 }}>${(m.total_cost_usd || 0).toFixed(6)}</td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
              )}

              {/* Subtab: By Tenant */}
              {subTab === 'tenants' && (
                <div style={{ overflowX: 'auto', background: 'rgba(0,0,0,0.25)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-subtle)' }}>
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>División / Tenant ID</th>
                        <th>Empresa / Cliente</th>
                        <th>Total Peticiones</th>
                        <th>Tokens Consumidos</th>
                        <th>Costo Acumulado (USD)</th>
                      </tr>
                    </thead>
                    <tbody>
                      {tenantUsage.length === 0 ? (
                        <tr>
                          <td colSpan="5" style={{ textAlign: 'center', padding: '24px', color: 'var(--text-dim)' }}>
                            No hay datos por tenant.
                          </td>
                        </tr>
                      ) : (
                        tenantUsage.map((t, i) => (
                          <tr key={i}>
                            <td style={{ fontFamily: 'var(--font-mono)', fontSize: '0.74rem' }}>{t.tenant_id}</td>
                            <td style={{ fontWeight: 600 }}>{t.client_id}</td>
                            <td>{t.total_requests}</td>
                            <td>{t.total_tokens}</td>
                            <td style={{ color: '#34d399', fontWeight: 600 }}>${(t.total_cost_usd || 0).toFixed(6)}</td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}

          {currentView === 'security' && (
            <div>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '10px' }}>
                <h3 style={{ fontSize: '0.9rem', color: 'var(--text-bright)', margin: 0, display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <ShieldCheck size={16} style={{ color: '#10b981' }} />
                  <span>Auditoría Central de Seguridad (Base de Datos Persistente)</span>
                </h3>
                <span style={{ fontSize: '0.72rem', color: 'var(--text-dim)' }}>
                  {securityLogs.length} eventos recuperados
                </span>
              </div>

              <div style={{ overflowX: 'auto', background: 'rgba(0,0,0,0.25)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-subtle)' }}>
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Fecha / Hora</th>
                      <th>Servicio</th>
                      <th>Tipo de Evento</th>
                      <th>Severidad</th>
                      <th>Usuario</th>
                      <th>Empresa / Tenant</th>
                      <th>Detalles</th>
                    </tr>
                  </thead>
                  <tbody>
                    {securityLogs.length === 0 ? (
                      <tr>
                        <td colSpan="7" style={{ textAlign: 'center', padding: '24px', color: 'var(--text-dim)' }}>
                          No se han detectado incidentes o eventos de seguridad en el sistema central.
                        </td>
                      </tr>
                    ) : (
                      securityLogs.map((log, i) => (
                        <tr key={i}>
                          <td style={{ fontFamily: 'var(--font-mono)', fontSize: '0.72rem', whiteSpace: 'nowrap' }}>
                            {log.created_at ? new Date(log.created_at).toLocaleString() : 'N/A'}
                          </td>
                          <td>
                            <span style={{ fontSize: '0.7rem', color: '#93c5fd', fontWeight: 600 }}>
                              {log.service || 'back-chat'}
                            </span>
                          </td>
                          <td>
                            <span style={{ 
                              padding: '2px 8px', 
                              borderRadius: '4px', 
                              fontSize: '0.72rem',
                              fontWeight: 600,
                              background: log.event_type?.includes('PROMPT') || log.event_type?.includes('INJECTION') || log.event_type?.includes('AUTH')
                                ? 'rgba(239, 68, 68, 0.2)'
                                : 'rgba(16, 185, 129, 0.2)',
                              color: log.event_type?.includes('PROMPT') || log.event_type?.includes('INJECTION') || log.event_type?.includes('AUTH')
                                ? '#ef4444'
                                : '#34d399'
                            }}>
                              {log.event_type}
                            </span>
                          </td>
                          <td>
                            <span style={{ 
                              color: log.severity === 'HIGH' || log.severity === 'CRITICAL' ? '#ef4444' : log.severity === 'MEDIUM' ? '#f59e0b' : '#60a5fa',
                              fontWeight: 600,
                              fontSize: '0.74rem'
                            }}>
                              {log.severity}
                            </span>
                          </td>
                          <td>{log.usuario}</td>
                          <td style={{ fontSize: '0.72rem', color: 'var(--text-dim)' }}>
                            {log.client_id || 'sigires'} / {log.tenant_id ? log.tenant_id.slice(0, 8) : 'default'}
                          </td>
                          <td style={{ fontFamily: 'var(--font-mono)', fontSize: '0.72rem', maxWidth: '300px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={JSON.stringify(log.details)}>
                            {typeof log.details === 'object' ? JSON.stringify(log.details) : log.details}
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {currentView === 'messages' && (
            <div>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '10px' }}>
                <h3 style={{ fontSize: '0.9rem', color: 'var(--text-bright)', margin: 0, display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <FileText size={16} style={{ color: '#60a5fa' }} />
                  <span>Trazas Centrales de Mensajes y Consultas Sanitizadas</span>
                </h3>
                <span style={{ fontSize: '0.72rem', color: 'var(--text-dim)' }}>
                  {messageLogs.length} mensajes auditados
                </span>
              </div>

              <div style={{ overflowX: 'auto', background: 'rgba(0,0,0,0.25)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-subtle)' }}>
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Fecha / Hora</th>
                      <th>Dirección</th>
                      <th>Usuario</th>
                      <th>Rol</th>
                      <th>Tokens</th>
                      <th>Latencia</th>
                      <th>Costo (USD)</th>
                      <th>Contenido Sanitizado</th>
                    </tr>
                  </thead>
                  <tbody>
                    {messageLogs.length === 0 ? (
                      <tr>
                        <td colSpan="8" style={{ textAlign: 'center', padding: '24px', color: 'var(--text-dim)' }}>
                          No hay mensajes auditados registrados en la base central.
                        </td>
                      </tr>
                    ) : (
                      messageLogs.map((m, i) => (
                        <tr key={i}>
                          <td style={{ fontFamily: 'var(--font-mono)', fontSize: '0.72rem', whiteSpace: 'nowrap' }}>
                            {m.created_at ? new Date(m.created_at).toLocaleTimeString() : 'N/A'}
                          </td>
                          <td>
                            <span style={{ 
                              padding: '2px 6px', 
                              borderRadius: '4px',
                              fontSize: '0.7rem',
                              fontWeight: 600,
                              background: m.direction === 'INCOMING' ? 'rgba(59, 130, 246, 0.2)' : 'rgba(16, 185, 129, 0.2)',
                              color: m.direction === 'INCOMING' ? '#60a5fa' : '#34d399'
                            }}>
                              {m.direction}
                            </span>
                          </td>
                          <td style={{ fontWeight: 600 }}>{m.usuario}</td>
                          <td><span style={{ fontSize: '0.72rem', color: '#a5b4fc' }}>{m.rol || 'usuario'}</span></td>
                          <td>{m.tokens}</td>
                          <td>{m.latencia_ms}ms</td>
                          <td>${(m.costo_usd || 0).toFixed(6)}</td>
                          <td style={{ maxWidth: '320px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={m.content}>
                            {m.content}
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
