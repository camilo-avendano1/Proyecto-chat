import React, { useEffect, useState, useMemo, useCallback } from 'react';
import {
  FileSpreadsheet,
  FileJson,
  Download,
  TrendingUp,
  Users,
  Cpu,
  MessageSquareText,
  Layers,
  MapPin,
} from 'lucide-react';
import {
  fetchUsageSummary,
  fetchUsageTimeseries,
  fetchUsageBySite,
  fetchUsageByUser,
  fetchUsageByRole,
  fetchUsageByModel,
  fetchMessageLogs,
  fetchDocuments,
  extractArray,
  normalizeTimeseries,
} from '../services/api';
import {
  downloadCSV,
  downloadJSON,
  formatCurrency,
  formatNumber,
} from '../utils/export';

export default function ReportsExportPage({
  filters,
  sites = [],
  siteLabels = { singular: 'Sede', plural: 'Sedes' },
  refreshKey,
  onToast,
}) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [summary, setSummary] = useState({});
  const [timeseries, setTimeseries] = useState([]);
  const [bySite, setBySite] = useState([]);
  const [byUser, setByUser] = useState([]);
  const [byRole, setByRole] = useState([]);
  const [byModel, setByModel] = useState([]);
  const [exportingId, setExportingId] = useState('');

  const siteNameMap = useMemo(() => {
    const m = {};
    sites.forEach((s) => {
      if (s.site_id) m[s.site_id] = s.nombre || s.site_name || s.site_code || s.site_id;
    });
    return m;
  }, [sites]);

  const loadReportsData = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const results = await Promise.allSettled([
        fetchUsageSummary(filters),
        fetchUsageTimeseries(filters),
        fetchUsageBySite(filters),
        fetchUsageByUser(filters),
        fetchUsageByRole(filters),
        fetchUsageByModel(filters),
      ]);
      const [sumRes, tsRes, siteRes, usrRes, roleRes, modRes] = results;

      if (sumRes.status === 'fulfilled') setSummary(sumRes.value || {});
      if (tsRes.status === 'fulfilled') setTimeseries(normalizeTimeseries(tsRes.value));
      if (siteRes.status === 'fulfilled') setBySite(extractArray(siteRes.value));
      if (usrRes.status === 'fulfilled') setByUser(extractArray(usrRes.value));
      if (roleRes.status === 'fulfilled') setByRole(extractArray(roleRes.value));
      if (modRes.status === 'fulfilled') setByModel(extractArray(modRes.value));

      const failed = results.filter((r) => r.status === 'rejected');
      if (failed.length === results.length) {
        setError(failed[0].reason?.message || 'Error al cargar analíticas de reporte.');
      }
    } catch (err) {
      setError(err.message || 'No se pudieron cargar los datos de reporte.');
    } finally {
      setLoading(false);
    }
  }, [filters]);

  useEffect(() => {
    loadReportsData();
  }, [loadReportsData, refreshKey]);

  const lowerSingular = siteLabels.singular.toLowerCase();
  const lowerPlural = siteLabels.plural.toLowerCase();

  const comparativeRows = useMemo(() => {
    const totalCostAll = bySite.reduce(
      (acc, r) => acc + Number(r.total_cost_usd ?? r.cost_usd ?? 0),
      0
    );

    return bySite
      .map((row) => {
        const totalReq = Number(row.total_requests ?? 0);
        const directReq = Number(row.fast_path_requests ?? row.direct_requests ?? 0);
        const llmReq = Number(row.llm_requests ?? Math.max(0, totalReq - directReq));
        const efficiencyPct = totalReq > 0 ? (directReq / totalReq) * 100 : 0;
        const tokensIn = Number(row.total_tokens_input ?? 0);
        const tokensOut = Number(row.total_tokens_output ?? 0);
        const tokensTotal = Number(row.total_tokens ?? tokensIn + tokensOut);
        const cost = Number(row.total_cost_usd ?? row.cost_usd ?? 0);
        const costSharePct = totalCostAll > 0 ? (cost / totalCostAll) * 100 : 0;
        const avgLatency = Number(
          row.avg_latency_ms ?? row.avg_latencia_ms ?? row.latencia_promedio_ms ?? 0
        );

        return {
          org_id: row.org_id || '',
          site_id: row.site_id || '',
          site_name:
            row.site_name || siteNameMap[row.site_id] || row.site_id || `Sin ${lowerSingular}`,
          total_requests: totalReq,
          llm_requests: llmReq,
          direct_requests: directReq,
          efficiency_pct: efficiencyPct,
          total_tokens_input: tokensIn,
          total_tokens_output: tokensOut,
          total_tokens: tokensTotal,
          total_cost_usd: cost,
          cost_share_pct: costSharePct,
          avg_latency_ms: avgLatency,
        };
      })
      .sort((a, b) => b.total_cost_usd - a.total_cost_usd || b.total_tokens - a.total_tokens);
  }, [bySite, siteNameMap, lowerSingular]);

  const totalsRow = useMemo(() => {
    const agg = comparativeRows.reduce(
      (acc, r) => {
        acc.total_requests += r.total_requests;
        acc.llm_requests += r.llm_requests;
        acc.direct_requests += r.direct_requests;
        acc.total_tokens_input += r.total_tokens_input;
        acc.total_tokens_output += r.total_tokens_output;
        acc.total_tokens += r.total_tokens;
        acc.total_cost_usd += r.total_cost_usd;
        if (r.avg_latency_ms > 0) {
          acc.latencySum += r.avg_latency_ms * Math.max(1, r.total_requests);
          acc.latencyWeight += Math.max(1, r.total_requests);
        }
        return acc;
      },
      {
        total_requests: 0,
        llm_requests: 0,
        direct_requests: 0,
        total_tokens_input: 0,
        total_tokens_output: 0,
        total_tokens: 0,
        total_cost_usd: 0,
        latencySum: 0,
        latencyWeight: 0,
      }
    );
    return {
      ...agg,
      efficiency_pct:
        agg.total_requests > 0 ? (agg.direct_requests / agg.total_requests) * 100 : 0,
      avg_latency_ms: agg.latencyWeight > 0 ? agg.latencySum / agg.latencyWeight : 0,
    };
  }, [comparativeRows]);

  const filterMeta = useMemo(
    () => ({
      org_id: filters.orgId || 'ALL',
      site_id: filters.siteId || 'ALL',
      time_range: filters.timeRange || '30d',
    }),
    [filters]
  );

  const dateStamp = new Date().toISOString().slice(0, 10);

  function exportSiteComparative(format) {
    const fileSlug = lowerPlural.replace(/[^a-z0-9]+/gi, '-').toLowerCase() || 'sedes';
    if (format === 'csv') {
      downloadCSV(
        `comparativo-${fileSlug}-${dateStamp}.csv`,
        [
          { key: 'org_id', label: 'Organización' },
          { key: 'site_id', label: `${siteLabels.singular} ID` },
          { key: 'site_name', label: siteLabels.singular },
          { key: 'total_requests', label: 'Consultas Totales' },
          { key: 'llm_requests', label: 'Llamadas al modelo' },
          { key: 'direct_requests', label: 'Respuestas directas' },
          {
            key: 'efficiency_pct',
            label: 'Eficiencia sin IA %',
            format: (v) => Number(v ?? 0).toFixed(2),
          },
          { key: 'total_tokens_input', label: 'Tokens Entrada' },
          { key: 'total_tokens_output', label: 'Tokens Salida' },
          { key: 'total_tokens', label: 'Tokens Totales' },
          {
            key: 'total_cost_usd',
            label: 'Costo USD',
            format: (v) => Number(v ?? 0).toFixed(6),
          },
          {
            key: 'cost_share_pct',
            label: '% Costo',
            format: (v) => Number(v ?? 0).toFixed(2),
          },
          {
            key: 'avg_latency_ms',
            label: 'Latencia Prom. (ms)',
            format: (v) => Math.round(Number(v ?? 0)),
          },
        ],
        comparativeRows
      );
    } else {
      downloadJSON(`comparativo-${fileSlug}-${dateStamp}.json`, comparativeRows, {
        report_type: 'site_comparative',
        filters: filterMeta,
      });
    }
    if (onToast) onToast(`Comparativo por ${lowerSingular} exportado (${format.toUpperCase()}).`, 'success');
  }

  function exportTimeseries(format) {
    if (format === 'csv') {
      downloadCSV(
        `serie-temporal-${dateStamp}.csv`,
        [
          { key: 'date', label: 'Fecha' },
          { key: 'total_requests', label: 'Consultas Totales' },
          { key: 'llm_requests', label: 'Llamadas al modelo' },
          { key: 'fast_path_requests', label: 'Respuestas directas' },
          { key: 'tokens_input', label: 'Tokens Entrada' },
          { key: 'tokens_output', label: 'Tokens Salida' },
          { key: 'total_tokens', label: 'Tokens Totales' },
          {
            key: 'total_cost_usd',
            label: 'Costo USD',
            format: (v) => Number(v ?? 0).toFixed(6),
          },
        ],
        timeseries
      );
    } else {
      downloadJSON(`serie-temporal-${dateStamp}.json`, timeseries, {
        report_type: 'daily_timeseries',
        filters: filterMeta,
      });
    }
    if (onToast) onToast(`Serie temporal exportada (${format.toUpperCase()}).`, 'success');
  }

  function exportUsersAndRoles(format) {
    if (format === 'csv') {
      const combined = [
        ...byUser.map((u) => ({
          nivel: 'USUARIO',
          org_id: u.org_id,
          site_id: u.site_id,
          site_name: siteNameMap[u.site_id] || u.site_name || u.site_id,
          usuario: u.usuario,
          rol: u.rol,
          total_requests: u.total_requests,
          llm_requests: u.llm_requests,
          direct_requests: u.fast_path_requests ?? u.direct_requests ?? 0,
          total_tokens_input: u.total_tokens_input,
          total_tokens_output: u.total_tokens_output,
          total_tokens: u.total_tokens,
          total_cost_usd: Number(u.total_cost_usd ?? 0).toFixed(6),
        })),
        ...byRole.map((r) => ({
          nivel: 'ROL_AGREGADO',
          org_id: r.org_id,
          site_id: 'ALL',
          site_name: 'Todas',
          usuario: '—',
          rol: r.rol,
          total_requests: r.total_requests,
          llm_requests: '',
          direct_requests: '',
          total_tokens_input: '',
          total_tokens_output: '',
          total_tokens: r.total_tokens,
          total_cost_usd: Number(r.total_cost_usd ?? 0).toFixed(6),
        })),
      ];
      downloadCSV(
        `desglose-usuarios-roles-${dateStamp}.csv`,
        [
          { key: 'nivel', label: 'Nivel' },
          { key: 'org_id', label: 'Organización' },
          { key: 'site_id', label: `${siteLabels.singular} ID` },
          { key: 'site_name', label: siteLabels.singular },
          { key: 'usuario', label: 'Usuario' },
          { key: 'rol', label: 'Rol' },
          { key: 'total_requests', label: 'Consultas' },
          { key: 'llm_requests', label: 'Llamadas al modelo' },
          { key: 'direct_requests', label: 'Respuestas directas' },
          { key: 'total_tokens_input', label: 'Tokens Entrada' },
          { key: 'total_tokens_output', label: 'Tokens Salida' },
          { key: 'total_tokens', label: 'Tokens Totales' },
          { key: 'total_cost_usd', label: 'Costo USD' },
        ],
        combined
      );
    } else {
      downloadJSON(
        `desglose-usuarios-roles-${dateStamp}.json`,
        { by_user: byUser, by_role: byRole },
        { report_type: 'user_and_role_breakdown', filters: filterMeta }
      );
    }
    if (onToast) onToast(`Desglose por usuario y rol exportado (${format.toUpperCase()}).`, 'success');
  }

  function exportModels(format) {
    if (format === 'csv') {
      downloadCSV(
        `rendimiento-modelos-${dateStamp}.csv`,
        [
          { key: 'model', label: 'Modelo' },
          { key: 'provider', label: 'Proveedor' },
          { key: 'total_requests', label: 'Consultas' },
          { key: 'total_tokens', label: 'Tokens Totales' },
          {
            key: 'avg_latency_ms',
            label: 'Latencia Prom. (ms)',
            format: (v, r) =>
              Math.round(Number(v ?? r.avg_latencia_ms ?? r.latencia_ms ?? 0)),
          },
          {
            key: 'total_cost_usd',
            label: 'Costo USD',
            format: (v, r) => Number(v ?? r.cost_usd ?? 0).toFixed(6),
          },
        ],
        byModel
      );
    } else {
      downloadJSON(`rendimiento-modelos-${dateStamp}.json`, byModel, {
        report_type: 'model_performance',
        filters: filterMeta,
      });
    }
    if (onToast) onToast(`Rendimiento por modelo exportado (${format.toUpperCase()}).`, 'success');
  }

  async function exportQueriesHistory(format) {
    setExportingId(`queries-${format}`);
    try {
      const res = await fetchMessageLogs({
        org_id: filters.orgId || undefined,
        site_id: filters.siteId || undefined,
        limit: 500,
        offset: 0,
      });
      const list = extractArray(res);
      if (format === 'csv') {
        downloadCSV(
          `historial-consultas-${dateStamp}.csv`,
          [
            { key: 'created_at', label: 'Fecha' },
            { key: 'log_id', label: 'Log ID' },
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
          list
        );
      } else {
        downloadJSON(`historial-consultas-${dateStamp}.json`, list, {
          report_type: 'queries_history',
          filters: filterMeta,
        });
      }
      if (onToast) {
        onToast(
          `Historial de ${list.length} consultas exportado (${format.toUpperCase()}).`,
          'success'
        );
      }
    } catch (err) {
      if (onToast) onToast(err.message || 'Error al exportar historial de consultas.', 'error');
    } finally {
      setExportingId('');
    }
  }

  async function exportConsolidatedJSON() {
    setExportingId('consolidated');
    try {
      const [msgRes, docsRes] = await Promise.allSettled([
        fetchMessageLogs({
          org_id: filters.orgId || undefined,
          site_id: filters.siteId || undefined,
          limit: 200,
          offset: 0,
        }),
        fetchDocuments({
          org_id: filters.orgId || undefined,
          site_id: filters.siteId || undefined,
          limit: 200,
          offset: 0,
        }),
      ]);

      const payload = {
        report_type: 'full_consolidated_admin_report',
        filters: filterMeta,
        summary,
        site_comparative: comparativeRows,
        timeseries,
        by_user: byUser,
        by_role: byRole,
        by_model: byModel,
        documents_summary:
          docsRes.status === 'fulfilled'
            ? {
                total: docsRes.value?.total ?? 0,
                counts_by_site: docsRes.value?.counts_by_site ?? {},
                records: extractArray(docsRes.value),
              }
            : null,
        recent_messages_sample:
          msgRes.status === 'fulfilled' ? extractArray(msgRes.value) : [],
      };

      downloadJSON(`reporte-consolidado-saas-${dateStamp}.json`, payload);
      if (onToast) onToast('Reporte consolidado JSON descargado.', 'success');
    } catch (err) {
      if (onToast) onToast(err.message || 'Error al generar el reporte consolidado.', 'error');
    } finally {
      setExportingId('');
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div className="page-header">
        <div>
          <h1 className="page-title">Reportes y Descargas</h1>
          <p className="page-subtitle">
            Tabla comparativa de eficiencia por {lowerSingular} y exportaciones listas para Excel (CSV UTF-8) o auditoría (JSON).
          </p>
        </div>
      </div>

      {error ? (
        <div className="alert alert--error" role="alert">
          <span>{error}</span>
        </div>
      ) : null}

      {/* Comparative Site Analytics Table */}
      <section className="card">
        <div className="card-header">
          <div>
            <h2 className="card-title">
              <MapPin size={17} />
              <span>Comparativo de Consumo y Eficiencia por {siteLabels.singular}</span>
            </h2>
            <p className="card-subtitle">
              Desglose comparativo de volumen, tokens, costo USD, participación y respuestas directas (sin costo).
            </p>
          </div>
          <div style={{ display: 'flex', gap: 6 }}>
            <button
              type="button"
              className="btn btn-sm"
              onClick={() => exportSiteComparative('csv')}
              disabled={comparativeRows.length === 0}
            >
              <Download size={13} />
              <span>CSV</span>
            </button>
            <button
              type="button"
              className="btn btn-sm"
              onClick={() => exportSiteComparative('json')}
              disabled={comparativeRows.length === 0}
            >
              <Download size={13} />
              <span>JSON</span>
            </button>
          </div>
        </div>

        <div className="table-wrap">
          {loading && comparativeRows.length === 0 ? (
            <div className="empty-state">
              <span>Calculando comparativo por {lowerSingular}...</span>
            </div>
          ) : comparativeRows.length === 0 ? (
            <div className="empty-state">
              <span>Sin métricas registradas en el período seleccionado.</span>
            </div>
          ) : (
            <table className="table">
              <thead>
                <tr>
                  <th>{siteLabels.singular}</th>
                  <th className="text-right">Consultas</th>
                  <th className="text-right">Llamadas al modelo</th>
                  <th className="text-right">Respuestas directas</th>
                  <th className="text-right">Eficiencia sin IA %</th>
                  <th className="text-right">Tokens In</th>
                  <th className="text-right">Tokens Out</th>
                  <th className="text-right">Tokens Total</th>
                  <th className="text-right">Costo USD</th>
                  <th className="text-right">% Costo</th>
                  <th className="text-right">Latencia Prom.</th>
                </tr>
              </thead>
              <tbody>
                {comparativeRows.map((row) => (
                  <tr key={`${row.org_id}-${row.site_id}`}>
                    <td>
                      <div style={{ fontWeight: 600 }}>{row.site_name}</div>
                      <div className="mono" style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                        {row.site_id}
                      </div>
                    </td>
                    <td className="text-right tabular" style={{ fontWeight: 600 }}>
                      {formatNumber(row.total_requests)}
                    </td>
                    <td className="text-right tabular">{formatNumber(row.llm_requests)}</td>
                    <td className="text-right tabular">{formatNumber(row.direct_requests)}</td>
                    <td className="text-right tabular">
                      <span
                        className={`badge ${
                          row.efficiency_pct >= 50
                            ? 'badge--emerald'
                            : row.efficiency_pct >= 20
                            ? 'badge--blue'
                            : 'badge--neutral'
                        }`}
                      >
                        {row.efficiency_pct.toFixed(1)}%
                      </span>
                    </td>
                    <td className="text-right tabular">{formatNumber(row.total_tokens_input)}</td>
                    <td className="text-right tabular">{formatNumber(row.total_tokens_output)}</td>
                    <td className="text-right tabular" style={{ fontWeight: 600 }}>
                      {formatNumber(row.total_tokens)}
                    </td>
                    <td className="text-right tabular">{formatCurrency(row.total_cost_usd)}</td>
                    <td className="text-right tabular">{row.cost_share_pct.toFixed(1)}%</td>
                    <td className="text-right tabular">
                      {row.avg_latency_ms > 0
                        ? `${formatNumber(Math.round(row.avg_latency_ms))} ms`
                        : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr>
                  <td>Total Consolidado ({comparativeRows.length} {lowerPlural})</td>
                  <td className="text-right tabular">{formatNumber(totalsRow.total_requests)}</td>
                  <td className="text-right tabular">{formatNumber(totalsRow.llm_requests)}</td>
                  <td className="text-right tabular">
                    {formatNumber(totalsRow.direct_requests)}
                  </td>
                  <td className="text-right tabular">{totalsRow.efficiency_pct.toFixed(1)}%</td>
                  <td className="text-right tabular">
                    {formatNumber(totalsRow.total_tokens_input)}
                  </td>
                  <td className="text-right tabular">
                    {formatNumber(totalsRow.total_tokens_output)}
                  </td>
                  <td className="text-right tabular">{formatNumber(totalsRow.total_tokens)}</td>
                  <td className="text-right tabular">
                    {formatCurrency(totalsRow.total_cost_usd)}
                  </td>
                  <td className="text-right tabular">100.0%</td>
                  <td className="text-right tabular">
                    {totalsRow.avg_latency_ms > 0
                      ? `${formatNumber(Math.round(totalsRow.avg_latency_ms))} ms`
                      : '—'}
                  </td>
                </tr>
              </tfoot>
            </table>
          )}
        </div>
      </section>

      {/* 1-Click Export Cards */}
      <div>
        <h2 style={{ margin: '0 0 12px', fontSize: 16, fontWeight: 700 }}>
          Centro de Descargas (1 Clic)
        </h2>
        <div className="grid-3">
          <div className="card">
            <div className="card-body" style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <span className="kpi-icon">
                  <MapPin size={17} />
                </span>
                <div>
                  <div style={{ fontWeight: 700 }}>Comparativo por {siteLabels.singular}</div>
                  <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                    {comparativeRows.length} {lowerPlural} en alcance
                  </div>
                </div>
              </div>
              <div style={{ display: 'flex', gap: 8 }}>
                <button
                  type="button"
                  className="btn btn-sm"
                  onClick={() => exportSiteComparative('csv')}
                  disabled={comparativeRows.length === 0}
                >
                  <FileSpreadsheet size={14} />
                  <span>Descargar CSV</span>
                </button>
                <button
                  type="button"
                  className="btn btn-sm"
                  onClick={() => exportSiteComparative('json')}
                  disabled={comparativeRows.length === 0}
                >
                  <FileJson size={14} />
                  <span>JSON</span>
                </button>
              </div>
            </div>
          </div>

          <div className="card">
            <div className="card-body" style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <span className="kpi-icon kpi-icon--emerald">
                  <TrendingUp size={17} />
                </span>
                <div>
                  <div style={{ fontWeight: 700 }}>Serie Temporal Diaria</div>
                  <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                    {timeseries.length} días con actividad
                  </div>
                </div>
              </div>
              <div style={{ display: 'flex', gap: 8 }}>
                <button
                  type="button"
                  className="btn btn-sm"
                  onClick={() => exportTimeseries('csv')}
                  disabled={timeseries.length === 0}
                >
                  <FileSpreadsheet size={14} />
                  <span>Descargar CSV</span>
                </button>
                <button
                  type="button"
                  className="btn btn-sm"
                  onClick={() => exportTimeseries('json')}
                  disabled={timeseries.length === 0}
                >
                  <FileJson size={14} />
                  <span>JSON</span>
                </button>
              </div>
            </div>
          </div>

          <div className="card">
            <div className="card-body" style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <span className="kpi-icon kpi-icon--violet">
                  <Users size={17} />
                </span>
                <div>
                  <div style={{ fontWeight: 700 }}>Desglose por Usuario y Rol</div>
                  <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                    {byUser.length} usuarios • {byRole.length} roles
                  </div>
                </div>
              </div>
              <div style={{ display: 'flex', gap: 8 }}>
                <button
                  type="button"
                  className="btn btn-sm"
                  onClick={() => exportUsersAndRoles('csv')}
                  disabled={byUser.length === 0 && byRole.length === 0}
                >
                  <FileSpreadsheet size={14} />
                  <span>Descargar CSV</span>
                </button>
                <button
                  type="button"
                  className="btn btn-sm"
                  onClick={() => exportUsersAndRoles('json')}
                  disabled={byUser.length === 0 && byRole.length === 0}
                >
                  <FileJson size={14} />
                  <span>JSON</span>
                </button>
              </div>
            </div>
          </div>

          <div className="card">
            <div className="card-body" style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <span className="kpi-icon kpi-icon--amber">
                  <Cpu size={17} />
                </span>
                <div>
                  <div style={{ fontWeight: 700 }}>Rendimiento por Modelo</div>
                  <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                    {byModel.length} modelos evaluados
                  </div>
                </div>
              </div>
              <div style={{ display: 'flex', gap: 8 }}>
                <button
                  type="button"
                  className="btn btn-sm"
                  onClick={() => exportModels('csv')}
                  disabled={byModel.length === 0}
                >
                  <FileSpreadsheet size={14} />
                  <span>Descargar CSV</span>
                </button>
                <button
                  type="button"
                  className="btn btn-sm"
                  onClick={() => exportModels('json')}
                  disabled={byModel.length === 0}
                >
                  <FileJson size={14} />
                  <span>JSON</span>
                </button>
              </div>
            </div>
          </div>

          <div className="card">
            <div className="card-body" style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <span className="kpi-icon">
                  <MessageSquareText size={17} />
                </span>
                <div>
                  <div style={{ fontWeight: 700 }}>Historial de Consultas</div>
                  <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                    Últimos 500 mensajes sanitizados
                  </div>
                </div>
              </div>
              <div style={{ display: 'flex', gap: 8 }}>
                <button
                  type="button"
                  className="btn btn-sm"
                  disabled={exportingId === 'queries-csv'}
                  onClick={() => exportQueriesHistory('csv')}
                >
                  <FileSpreadsheet size={14} />
                  <span>{exportingId === 'queries-csv' ? 'Generando...' : 'Descargar CSV'}</span>
                </button>
                <button
                  type="button"
                  className="btn btn-sm"
                  disabled={exportingId === 'queries-json'}
                  onClick={() => exportQueriesHistory('json')}
                >
                  <FileJson size={14} />
                  <span>{exportingId === 'queries-json' ? 'Generando...' : 'JSON'}</span>
                </button>
              </div>
            </div>
          </div>

          <div className="card" style={{ borderColor: 'var(--accent-border)', background: '#FAFCFF' }}>
            <div className="card-body" style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <span className="kpi-icon">
                  <Layers size={17} />
                </span>
                <div>
                  <div style={{ fontWeight: 700 }}>Reporte Consolidado Completo</div>
                  <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                    Métricas, modelos, documentos y muestra de historial
                  </div>
                </div>
              </div>
              <div>
                <button
                  type="button"
                  className="btn btn-primary btn-sm"
                  disabled={exportingId === 'consolidated'}
                  onClick={exportConsolidatedJSON}
                >
                  <Download size={14} />
                  <span>
                    {exportingId === 'consolidated'
                      ? 'Consolidando...'
                      : 'Descargar Reporte JSON'}
                  </span>
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
