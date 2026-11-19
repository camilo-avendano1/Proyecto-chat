import React, { useEffect, useState, useMemo, useCallback } from 'react';
import {
  MessageSquareText,
  Cpu,
  ShieldAlert,
  Search,
  Download,
  ChevronDown,
  ChevronRight,
  AlertOctagon,
} from 'lucide-react';
import {
  fetchMessageLogs,
  fetchUsageRecords,
  fetchSecurityLogs,
  fetchSystemErrorLogs,
  buildUsageFilterParams,
  extractArray,
} from '../services/api';
import {
  downloadCSV,
  downloadJSON,
  formatCurrency,
  formatDateTime,
  formatNumber,
} from '../utils/export';

const PAGE_SIZE = 50;

function SeverityBadge({ severity }) {
  const s = (severity || 'LOW').toUpperCase();
  const cls =
    s === 'CRITICAL' || s === 'HIGH'
      ? 'badge--rose'
      : s === 'MEDIUM'
      ? 'badge--amber'
      : 'badge--neutral';
  return <span className={`badge ${cls}`}>{s}</span>;
}

export default function QueriesAuditPage({
  filters,
  sites = [],
  siteLabels = { singular: 'Sede', plural: 'Sedes' },
  refreshKey,
  onToast,
}) {
  const [subtab, setSubtab] = useState('messages'); // 'messages' | 'records' | 'security'
  const [securityMode, setSecurityMode] = useState('events'); // 'events' | 'errors'

  // Filter states
  const [localSite, setLocalSite] = useState(filters.siteId || '');
  const [usuarioFilter, setUsuarioFilter] = useState('');
  const [appliedUsuario, setAppliedUsuario] = useState('');
  const [directionFilter, setDirectionFilter] = useState('');
  const [severityFilter, setSeverityFilter] = useState('');
  const [eventTypeFilter, setEventTypeFilter] = useState('');
  const [appliedEventType, setAppliedEventType] = useState('');
  const [localSearch, setLocalSearch] = useState('');
  const [offset, setOffset] = useState(0);

  // Data states
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [records, setRecords] = useState([]);
  const [total, setTotal] = useState(0);
  const [expandedRowId, setExpandedRowId] = useState('');

  useEffect(() => {
    setLocalSite(filters.siteId || '');
    setOffset(0);
  }, [filters.siteId, filters.orgId]);

  const siteNameMap = useMemo(() => {
    const m = {};
    sites.forEach((s) => {
      if (s.site_id) m[s.site_id] = s.nombre || s.site_name || s.site_code || s.site_id;
    });
    return m;
  }, [sites]);

  const scopedSites = useMemo(() => {
    if (!filters.orgId) return sites;
    return sites.filter((s) => s.org_id === filters.orgId);
  }, [sites, filters.orgId]);

  const loadTab = useCallback(async () => {
    setLoading(true);
    setError('');
    setExpandedRowId('');

    try {
      const effectiveSite = localSite || filters.siteId || undefined;
      if (subtab === 'messages') {
        const res = await fetchMessageLogs({
          org_id: filters.orgId || undefined,
          site_id: effectiveSite,
          usuario: appliedUsuario || undefined,
          direction: directionFilter || undefined,
          limit: PAGE_SIZE,
          offset,
        });
        const list = extractArray(res);
        setRecords(list);
        setTotal(Number(res?.total ?? list.length));
      } else if (subtab === 'records') {
        const base = buildUsageFilterParams({
          ...filters,
          siteId: effectiveSite || '',
        });
        const res = await fetchUsageRecords({
          ...base,
          usuario: appliedUsuario || undefined,
          limit: PAGE_SIZE,
          offset,
        });
        const list = extractArray(res);
        setRecords(list);
        setTotal(Number(res?.total ?? list.length));
      } else if (securityMode === 'events') {
        const res = await fetchSecurityLogs({
          org_id: filters.orgId || undefined,
          site_id: effectiveSite,
          usuario: appliedUsuario || undefined,
          event_type: appliedEventType || undefined,
          severity: severityFilter || undefined,
          limit: PAGE_SIZE,
          offset,
        });
        const list = extractArray(res);
        setRecords(list);
        setTotal(Number(res?.total ?? list.length));
      } else {
        const res = await fetchSystemErrorLogs({
          org_id: filters.orgId || undefined,
          site_id: effectiveSite,
          limit: PAGE_SIZE,
          offset,
        });
        const list = extractArray(res);
        setRecords(list);
        setTotal(Number(res?.total ?? list.length));
      }
    } catch (err) {
      setError(err.message || 'No se pudieron consultar los registros.');
      setRecords([]);
    } finally {
      setLoading(false);
    }
  }, [
    subtab,
    securityMode,
    filters,
    localSite,
    appliedUsuario,
    appliedEventType,
    directionFilter,
    severityFilter,
    offset,
  ]);

  useEffect(() => {
    loadTab();
  }, [loadTab, refreshKey]);

  const visibleRecords = useMemo(() => {
    const q = localSearch.trim().toLowerCase();
    if (!q) return records;
    return records.filter((item) => JSON.stringify(item).toLowerCase().includes(q));
  }, [records, localSearch]);

  function getRowKey(row, idx) {
    return (
      row.log_id ||
      row.ledger_id ||
      row.event_id ||
      row.error_id ||
      `${subtab}-${idx}`
    );
  }

  function handleSubtabChange(next) {
    setSubtab(next);
    setOffset(0);
    setExpandedRowId('');
  }

  function handleExportCSV() {
    const stamp = new Date().toISOString().slice(0, 10);
    if (subtab === 'messages') {
      downloadCSV(
        `historial-mensajes-${stamp}.csv`,
        [
          { key: 'created_at', label: 'Fecha' },
          { key: 'org_id', label: 'Organización' },
          { key: 'site_id', label: `${siteLabels.singular} ID` },
          { key: 'site_code', label: 'Código' },
          { key: 'usuario', label: 'Usuario' },
          { key: 'rol', label: 'Rol' },
          { key: 'direction', label: 'Dirección' },
          { key: 'model', label: 'Modelo' },
          { key: 'tokens', label: 'Tokens' },
          { key: 'costo_usd', label: 'Costo USD' },
          { key: 'latencia_ms', label: 'Latencia ms' },
          { key: 'status', label: 'Estado' },
          { key: 'content', label: 'Contenido' },
        ],
        visibleRecords
      );
    } else if (subtab === 'records') {
      downloadCSV(
        `registro-uso-modelo-${stamp}.csv`,
        [
          { key: 'created_at', label: 'Fecha' },
          { key: 'ledger_id', label: 'Registro ID' },
          { key: 'org_id', label: 'Organización' },
          { key: 'site_id', label: `${siteLabels.singular} ID` },
          { key: 'site_code', label: 'Código' },
          { key: 'usuario', label: 'Usuario' },
          { key: 'rol', label: 'Rol' },
          { key: 'operacion', label: 'Operación' },
          { key: 'model', label: 'Modelo' },
          { key: 'provider', label: 'Proveedor' },
          { key: 'tokens_input', label: 'Tokens In' },
          { key: 'tokens_output', label: 'Tokens Out' },
          { key: 'tokens_total', label: 'Tokens Total' },
          { key: 'costo_usd', label: 'Costo USD' },
          { key: 'latencia_ms', label: 'Latencia ms' },
          {
            key: 'is_llm_call',
            label: 'Modo',
            format: (v) => (v ? 'Llamadas al modelo' : 'Respuestas directas'),
          },
          { key: 'token_source', label: 'Origen' },
          { key: 'status', label: 'Estado' },
          { key: 'query_preview', label: 'Vista previa' },
        ],
        visibleRecords
      );
    } else if (securityMode === 'events') {
      downloadCSV(
        `alertas-seguridad-${stamp}.csv`,
        [
          { key: 'created_at', label: 'Fecha' },
          { key: 'event_id', label: 'Evento ID' },
          { key: 'service', label: 'Servicio' },
          { key: 'event_type', label: 'Tipo Evento' },
          { key: 'severity', label: 'Severidad' },
          { key: 'org_id', label: 'Organización' },
          { key: 'site_id', label: `${siteLabels.singular} ID` },
          { key: 'site_code', label: 'Código' },
          { key: 'usuario', label: 'Usuario' },
          { key: 'ip_address', label: 'IP' },
          { key: 'details', label: 'Detalles' },
        ],
        visibleRecords
      );
    } else {
      downloadCSV(
        `errores-sistema-${stamp}.csv`,
        [
          { key: 'created_at', label: 'Fecha' },
          { key: 'error_id', label: 'Error ID' },
          { key: 'service', label: 'Servicio' },
          { key: 'error_type', label: 'Tipo Error' },
          { key: 'org_id', label: 'Organización' },
          { key: 'site_id', label: `${siteLabels.singular} ID` },
          { key: 'site_code', label: 'Código' },
          { key: 'usuario', label: 'Usuario' },
          { key: 'message', label: 'Mensaje' },
        ],
        visibleRecords
      );
    }
    if (onToast) onToast('Vista actual exportada en CSV.', 'success');
  }

  function handleExportJSON() {
    const stamp = new Date().toISOString().slice(0, 10);
    const slug =
      subtab === 'messages'
        ? 'historial-mensajes'
        : subtab === 'records'
        ? 'registro-uso-modelo'
        : securityMode === 'events'
        ? 'alertas-seguridad'
        : 'errores-sistema';
    downloadJSON(`${slug}-${stamp}.json`, visibleRecords, {
      view: subtab,
      security_mode: subtab === 'security' ? securityMode : undefined,
      filters: {
        org_id: filters.orgId || 'ALL',
        site_id: localSite || filters.siteId || 'ALL',
        usuario: appliedUsuario || null,
        direction: directionFilter || null,
        severity: severityFilter || null,
      },
    });
    if (onToast) onToast('Vista actual exportada en JSON.', 'success');
  }

  const lowerSingular = siteLabels.singular.toLowerCase();

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div className="page-header">
        <div>
          <h1 className="page-title">Historial y Seguridad</h1>
          <p className="page-subtitle">
            Trazabilidad de conversaciones, llamadas al modelo, respuestas directas y alertas de seguridad.
          </p>
        </div>
        <div className="page-actions">
          <button
            type="button"
            className="btn"
            onClick={handleExportCSV}
            disabled={visibleRecords.length === 0}
          >
            <Download size={14} />
            <span>CSV</span>
          </button>
          <button
            type="button"
            className="btn btn-primary"
            onClick={handleExportJSON}
            disabled={visibleRecords.length === 0}
          >
            <Download size={14} />
            <span>JSON</span>
          </button>
        </div>
      </div>

      {/* Subtabs */}
      <div className="tabs" role="tablist">
        <button
          type="button"
          role="tab"
          aria-selected={subtab === 'messages'}
          className={`tab-btn ${subtab === 'messages' ? 'tab-btn--active' : ''}`}
          onClick={() => handleSubtabChange('messages')}
        >
          <MessageSquareText size={15} />
          <span>Mensajes y consultas</span>
        </button>

        <button
          type="button"
          role="tab"
          aria-selected={subtab === 'records'}
          className={`tab-btn ${subtab === 'records' ? 'tab-btn--active' : ''}`}
          onClick={() => handleSubtabChange('records')}
        >
          <Cpu size={15} />
          <span>Registro de uso del modelo</span>
        </button>

        <button
          type="button"
          role="tab"
          aria-selected={subtab === 'security'}
          className={`tab-btn ${subtab === 'security' ? 'tab-btn--active' : ''}`}
          onClick={() => handleSubtabChange('security')}
        >
          <ShieldAlert size={15} />
          <span>Alertas de seguridad</span>
        </button>
      </div>

      <section className="card">
        {/* Filters Bar */}
        <form
          onSubmit={(e) => {
            e.preventDefault();
            setOffset(0);
            setAppliedUsuario(usuarioFilter.trim());
            setAppliedEventType(eventTypeFilter.trim());
          }}
          className="table-toolbar"
        >
          <div className="table-toolbar-group">
            <select
              className="select"
              value={localSite}
              onChange={(e) => {
                setLocalSite(e.target.value);
                setOffset(0);
              }}
              style={{ width: 200, height: 34 }}
              aria-label={`Filtrar por ${lowerSingular}`}
            >
              <option value="">Todas las {siteLabels.plural}</option>
              {scopedSites.map((s) => (
                <option key={s.site_id} value={s.site_id}>
                  {s.nombre || s.site_name || s.site_id}
                </option>
              ))}
            </select>

            <input
              type="text"
              className="input"
              placeholder="Usuario exacto..."
              value={usuarioFilter}
              onChange={(e) => setUsuarioFilter(e.target.value)}
              style={{ width: 165, height: 34 }}
            />

            {subtab === 'messages' ? (
              <select
                className="select"
                value={directionFilter}
                onChange={(e) => {
                  setDirectionFilter(e.target.value);
                  setOffset(0);
                }}
                style={{ width: 165, height: 34 }}
                aria-label="Filtrar dirección"
              >
                <option value="">Toda dirección</option>
                <option value="INCOMING">Entrante (Usuario)</option>
                <option value="OUTGOING">Saliente (Asistente)</option>
              </select>
            ) : null}

            {subtab === 'security' ? (
              <>
                <div className="segmented">
                  <button
                    type="button"
                    className={`segmented-btn ${
                      securityMode === 'events' ? 'segmented-btn--active' : ''
                    }`}
                    onClick={() => {
                      setSecurityMode('events');
                      setOffset(0);
                    }}
                  >
                    Alertas de seguridad
                  </button>
                  <button
                    type="button"
                    className={`segmented-btn ${
                      securityMode === 'errors' ? 'segmented-btn--active' : ''
                    }`}
                    onClick={() => {
                      setSecurityMode('errors');
                      setOffset(0);
                    }}
                  >
                    Errores del sistema
                  </button>
                </div>

                {securityMode === 'events' ? (
                  <>
                    <select
                      className="select"
                      value={severityFilter}
                      onChange={(e) => {
                        setSeverityFilter(e.target.value);
                        setOffset(0);
                      }}
                      style={{ width: 145, height: 34 }}
                      aria-label="Filtrar severidad"
                    >
                      <option value="">Toda severidad</option>
                      <option value="LOW">LOW</option>
                      <option value="MEDIUM">MEDIUM</option>
                      <option value="HIGH">HIGH</option>
                      <option value="CRITICAL">CRITICAL</option>
                    </select>
                    <input
                      type="text"
                      className="input mono"
                      placeholder="Tipo de evento..."
                      value={eventTypeFilter}
                      onChange={(e) => setEventTypeFilter(e.target.value)}
                      style={{ width: 165, height: 34 }}
                    />
                  </>
                ) : null}
              </>
            ) : null}

            <button type="submit" className="btn btn-sm" style={{ height: 34 }}>
              Aplicar
            </button>
          </div>

          <div className="table-toolbar-group">
            <div style={{ position: 'relative', minWidth: 210 }}>
              <Search
                size={14}
                style={{
                  position: 'absolute',
                  left: 10,
                  top: '50%',
                  transform: 'translateY(-50%)',
                  color: 'var(--text-muted)',
                }}
              />
              <input
                type="text"
                className="input"
                placeholder="Buscar en vista actual..."
                value={localSearch}
                onChange={(e) => setLocalSearch(e.target.value)}
                style={{ paddingLeft: 30, height: 34 }}
              />
            </div>
            <span className="badge badge--neutral tabular">
              {formatNumber(visibleRecords.length)} filas
            </span>
          </div>
        </form>

        {error ? (
          <div className="card-body">
            <div className="alert alert--error">{error}</div>
          </div>
        ) : null}

        <div className="table-wrap">
          {loading && visibleRecords.length === 0 ? (
            <div className="empty-state">
              <span>Cargando registros...</span>
            </div>
          ) : visibleRecords.length === 0 ? (
            <div className="empty-state">
              <AlertOctagon size={25} />
              <span>Sin registros encontrados con los criterios seleccionados.</span>
            </div>
          ) : subtab === 'messages' ? (
            <table className="table">
              <thead>
                <tr>
                  <th style={{ width: 34 }} />
                  <th>Fecha</th>
                  <th>Dirección</th>
                  <th>{siteLabels.singular} / Usuario</th>
                  <th>Modo / Modelo</th>
                  <th className="text-right">Tokens</th>
                  <th className="text-right">Latencia</th>
                  <th>Contenido</th>
                </tr>
              </thead>
              <tbody>
                {visibleRecords.map((row, idx) => {
                  const key = getRowKey(row, idx);
                  const expanded = expandedRowId === key;
                  const dir = (row.direction || '').toUpperCase();
                  return (
                    <React.Fragment key={key}>
                      <tr
                        style={{ cursor: 'pointer' }}
                        onClick={() => setExpandedRowId(expanded ? '' : key)}
                      >
                        <td>
                          {expanded ? <ChevronDown size={15} /> : <ChevronRight size={15} />}
                        </td>
                        <td style={{ fontSize: 12, whiteSpace: 'nowrap' }}>
                          {formatDateTime(row.created_at)}
                        </td>
                        <td>
                          <span
                            className={`badge ${
                              dir === 'INCOMING' ? 'badge--blue' : 'badge--emerald'
                            }`}
                          >
                            {dir === 'INCOMING'
                              ? 'Entrante'
                              : dir === 'OUTGOING'
                              ? 'Saliente'
                              : dir || '—'}
                          </span>
                        </td>
                        <td>
                          <div style={{ fontWeight: 600 }}>{row.usuario || 'anónimo'}</div>
                          <div style={{ fontSize: 11.5, color: 'var(--text-muted)' }}>
                            {siteNameMap[row.site_id] || row.site_name || row.site_id || '—'}
                            {row.rol ? ` • ${row.rol}` : ''}
                          </div>
                        </td>
                        <td>
                          <span className="mono" style={{ fontSize: 12 }}>
                            {row.model || 'Respuesta directa'}
                          </span>
                        </td>
                        <td className="text-right tabular">{formatNumber(row.tokens ?? 0)}</td>
                        <td className="text-right tabular">
                          {row.latencia_ms ? `${formatNumber(row.latencia_ms)} ms` : '—'}
                        </td>
                        <td className="truncate-cell">{row.content || '—'}</td>
                      </tr>
                      {expanded ? (
                        <tr>
                          <td colSpan={8} className="row-expanded-panel">
                            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, marginBottom: 8, fontSize: 12 }}>
                              <span>
                                Request ID: <code className="mono">{row.request_id || '—'}</code>
                              </span>
                              <span>
                                Estado: <code className="mono">{row.status || '—'}</code>
                              </span>
                              <span>
                                Costo: <code className="mono">{formatCurrency(row.costo_usd, 6)}</code>
                              </span>
                              {row.site_code ? (
                                <span>
                                  Código {siteLabels.singular}: <code className="mono">{row.site_code}</code>
                                </span>
                              ) : null}
                            </div>
                            <pre className="code-block">{row.content || '(Sin contenido)'}</pre>
                          </td>
                        </tr>
                      ) : null}
                    </React.Fragment>
                  );
                })}
              </tbody>
            </table>
          ) : subtab === 'records' ? (
            <table className="table">
              <thead>
                <tr>
                  <th style={{ width: 34 }} />
                  <th>Fecha</th>
                  <th>{siteLabels.singular} / Usuario</th>
                  <th>Operación / Modo</th>
                  <th>Modelo</th>
                  <th className="text-right">Tokens In/Out</th>
                  <th className="text-right">Costo USD</th>
                  <th className="text-right">Latencia</th>
                  <th>Vista previa</th>
                </tr>
              </thead>
              <tbody>
                {visibleRecords.map((row, idx) => {
                  const key = getRowKey(row, idx);
                  const expanded = expandedRowId === key;
                  return (
                    <React.Fragment key={key}>
                      <tr
                        style={{ cursor: 'pointer' }}
                        onClick={() => setExpandedRowId(expanded ? '' : key)}
                      >
                        <td>
                          {expanded ? <ChevronDown size={15} /> : <ChevronRight size={15} />}
                        </td>
                        <td style={{ fontSize: 12, whiteSpace: 'nowrap' }}>
                          {formatDateTime(row.created_at)}
                        </td>
                        <td>
                          <div style={{ fontWeight: 600 }}>{row.usuario || 'anónimo'}</div>
                          <div style={{ fontSize: 11.5, color: 'var(--text-muted)' }}>
                            {siteNameMap[row.site_id] || row.site_name || row.site_id}
                            {row.rol ? ` • ${row.rol}` : ''}
                          </div>
                        </td>
                        <td>
                          <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap' }}>
                            <span
                              className={`badge ${
                                row.is_llm_call ? 'badge--blue' : 'badge--emerald'
                              }`}
                            >
                              {row.is_llm_call ? 'Llamada al modelo' : 'Respuesta directa'}
                            </span>
                            <span className="badge badge--neutral">{row.operacion}</span>
                          </div>
                        </td>
                        <td>
                          <div className="mono" style={{ fontSize: 12 }}>
                            {row.model || '—'}
                          </div>
                          <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                            {row.provider || row.token_source || ''}
                          </div>
                        </td>
                        <td className="text-right tabular">
                          {formatNumber(row.tokens_total)}
                          <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                            {formatNumber(row.tokens_input)} / {formatNumber(row.tokens_output)}
                          </div>
                        </td>
                        <td className="text-right tabular">{formatCurrency(row.costo_usd, 5)}</td>
                        <td className="text-right tabular">{formatNumber(row.latencia_ms)} ms</td>
                        <td className="truncate-cell">{row.query_preview || '—'}</td>
                      </tr>
                      {expanded ? (
                        <tr>
                          <td colSpan={9} className="row-expanded-panel">
                            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 14, marginBottom: 8, fontSize: 12 }}>
                              <span>
                                Registro ID: <code className="mono">{row.ledger_id}</code>
                              </span>
                              <span>
                                Request ID: <code className="mono">{row.request_id || '—'}</code>
                              </span>
                              <span>
                                Origen Tokens: <code className="mono">{row.token_source}</code>
                              </span>
                              <span>
                                Estado: <code className="mono">{row.status}</code>
                              </span>
                              {row.site_code ? (
                                <span>
                                  Código: <code className="mono">{row.site_code}</code>
                                </span>
                              ) : null}
                            </div>
                            <pre className="code-block">
                              {row.query_preview || '(Sin vista previa de consulta)'}
                            </pre>
                          </td>
                        </tr>
                      ) : null}
                    </React.Fragment>
                  );
                })}
              </tbody>
            </table>
          ) : securityMode === 'events' ? (
            <table className="table">
              <thead>
                <tr>
                  <th style={{ width: 34 }} />
                  <th>Fecha</th>
                  <th>Severidad</th>
                  <th>Tipo de Evento</th>
                  <th>Servicio</th>
                  <th>{siteLabels.singular} / Usuario</th>
                  <th>IP</th>
                  <th>Resumen Detalles</th>
                </tr>
              </thead>
              <tbody>
                {visibleRecords.map((row, idx) => {
                  const key = getRowKey(row, idx);
                  const expanded = expandedRowId === key;
                  const detailText =
                    typeof row.details === 'string'
                      ? row.details
                      : JSON.stringify(row.details || {}, null, 2);
                  return (
                    <React.Fragment key={key}>
                      <tr
                        style={{ cursor: 'pointer' }}
                        onClick={() => setExpandedRowId(expanded ? '' : key)}
                      >
                        <td>
                          {expanded ? <ChevronDown size={15} /> : <ChevronRight size={15} />}
                        </td>
                        <td style={{ fontSize: 12, whiteSpace: 'nowrap' }}>
                          {formatDateTime(row.created_at)}
                        </td>
                        <td>
                          <SeverityBadge severity={row.severity} />
                        </td>
                        <td className="mono" style={{ fontWeight: 600, fontSize: 12 }}>
                          {row.event_type}
                        </td>
                        <td>
                          <span className="badge badge--neutral">{row.service}</span>
                        </td>
                        <td>
                          <div>{row.usuario || '—'}</div>
                          <div style={{ fontSize: 11.5, color: 'var(--text-muted)' }}>
                            {siteNameMap[row.site_id] ||
                              row.site_name ||
                              row.site_id ||
                              row.org_name ||
                              row.org_id ||
                              '—'}
                          </div>
                        </td>
                        <td className="mono" style={{ fontSize: 12 }}>
                          {row.ip_address || '—'}
                        </td>
                        <td className="truncate-cell mono" style={{ fontSize: 12 }}>
                          {typeof row.details === 'string'
                            ? row.details
                            : JSON.stringify(row.details || {})}
                        </td>
                      </tr>
                      {expanded ? (
                        <tr>
                          <td colSpan={8} className="row-expanded-panel">
                            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 14, marginBottom: 8, fontSize: 12 }}>
                              <span>
                                Evento ID: <code className="mono">{row.event_id}</code>
                              </span>
                              <span>
                                Request ID: <code className="mono">{row.request_id || '—'}</code>
                              </span>
                              <span>
                                Organización: <code className="mono">{row.org_id || '—'}</code>
                              </span>
                            </div>
                            <pre className="code-block">{detailText}</pre>
                          </td>
                        </tr>
                      ) : null}
                    </React.Fragment>
                  );
                })}
              </tbody>
            </table>
          ) : (
            <table className="table">
              <thead>
                <tr>
                  <th style={{ width: 34 }} />
                  <th>Fecha</th>
                  <th>Servicio</th>
                  <th>Tipo de Error</th>
                  <th>{siteLabels.singular} / Usuario</th>
                  <th>Mensaje</th>
                </tr>
              </thead>
              <tbody>
                {visibleRecords.map((row, idx) => {
                  const key = getRowKey(row, idx);
                  const expanded = expandedRowId === key;
                  return (
                    <React.Fragment key={key}>
                      <tr
                        style={{ cursor: 'pointer' }}
                        onClick={() => setExpandedRowId(expanded ? '' : key)}
                      >
                        <td>
                          {expanded ? <ChevronDown size={15} /> : <ChevronRight size={15} />}
                        </td>
                        <td style={{ fontSize: 12, whiteSpace: 'nowrap' }}>
                          {formatDateTime(row.created_at)}
                        </td>
                        <td>
                          <span className="badge badge--rose">{row.service}</span>
                        </td>
                        <td className="mono" style={{ fontSize: 12, fontWeight: 600 }}>
                          {row.error_type}
                        </td>
                        <td>
                          <div>{row.usuario || '—'}</div>
                          <div style={{ fontSize: 11.5, color: 'var(--text-muted)' }}>
                            {siteNameMap[row.site_id] ||
                              row.site_name ||
                              row.site_id ||
                              row.org_name ||
                              row.org_id ||
                              '—'}
                          </div>
                        </td>
                        <td className="truncate-cell">{row.message || '—'}</td>
                      </tr>
                      {expanded ? (
                        <tr>
                          <td colSpan={6} className="row-expanded-panel">
                            <div style={{ fontSize: 12, marginBottom: 8 }}>
                              Error ID: <code className="mono">{row.error_id}</code> • Request ID:{' '}
                              <code className="mono">{row.request_id || '—'}</code>
                            </div>
                            <pre className="code-block">
                              {[row.message, row.exception].filter(Boolean).join('\n\n') ||
                                '(Sin traza)'}
                            </pre>
                          </td>
                        </tr>
                      ) : null}
                    </React.Fragment>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>

        {/* Pagination */}
        <div
          className="table-toolbar"
          style={{ borderTop: '1px solid var(--border)', borderBottom: 'none' }}
        >
          <span className="tabular" style={{ fontSize: 12.5, color: 'var(--text-muted)' }}>
            Página {Math.floor(offset / PAGE_SIZE) + 1} • Mostrando {records.length} de{' '}
            {formatNumber(total)} registros
          </span>
          <div style={{ display: 'flex', gap: 6 }}>
            <button
              type="button"
              className="btn btn-sm"
              disabled={offset === 0}
              onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
            >
              Anterior
            </button>
            <button
              type="button"
              className="btn btn-sm"
              disabled={records.length < PAGE_SIZE}
              onClick={() => setOffset(offset + PAGE_SIZE)}
            >
              Siguiente
            </button>
          </div>
        </div>
      </section>
    </div>
  );
}
