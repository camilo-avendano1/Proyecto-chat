import React, { useEffect, useState, useMemo, useCallback } from 'react';
import {
  Activity,
  Cpu,
  DollarSign,
  Zap,
  FileText,
  Download,
  Users,
  Briefcase,
} from 'lucide-react';
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
} from 'recharts';
import {
  fetchUsageSummary,
  fetchUsageTimeseries,
  fetchUsageBySite,
  fetchUsageByUser,
  fetchUsageByRole,
  fetchUsageByModel,
  fetchDocuments,
  extractArray,
  normalizeTimeseries,
} from '../services/api';
import {
  downloadCSV,
  formatCompactNumber,
  formatCurrency,
  formatNumber,
  formatShortDate,
} from '../utils/export';

const CHART_COLORS = ['#1D4ED8', '#059669', '#D97706', '#6D28D9', '#0891B2', '#DC2626'];

function buildSiteNameMap(sites = []) {
  const map = {};
  sites.forEach((s) => {
    if (s.site_id) {
      map[s.site_id] = s.nombre || s.site_name || s.site_code || s.site_id;
    }
  });
  return map;
}

export default function OverviewPage({
  filters,
  sites = [],
  siteLabels = { singular: 'Sede', plural: 'Sedes' },
  refreshKey,
  onToast,
}) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [summary, setSummary] = useState(null);
  const [timeseries, setTimeseries] = useState([]);
  const [bySite, setBySite] = useState([]);
  const [byUser, setByUser] = useState([]);
  const [byRole, setByRole] = useState([]);
  const [byModel, setByModel] = useState([]);
  const [docsTotal, setDocsTotal] = useState(0);
  const [docsSyncedCount, setDocsSyncedCount] = useState(0);

  const [trendMetric, setTrendMetric] = useState('requests'); // 'requests' | 'tokens' | 'cost'
  const [barMetric, setBarMetric] = useState('tokens'); // 'tokens' | 'requests' | 'cost'

  const siteNameMap = useMemo(() => buildSiteNameMap(sites), [sites]);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const docParams = { limit: 100, offset: 0 };
      if (filters.orgId) docParams.org_id = filters.orgId;
      if (filters.siteId) docParams.site_id = filters.siteId;

      const results = await Promise.allSettled([
        fetchUsageSummary(filters),
        fetchUsageTimeseries(filters),
        fetchUsageBySite(filters),
        fetchUsageByUser(filters),
        fetchUsageByRole(filters),
        fetchUsageByModel(filters),
        fetchDocuments(docParams),
      ]);

      const [sumRes, tsRes, siteRes, usrRes, roleRes, modRes, docRes] = results;

      if (sumRes.status === 'fulfilled') setSummary(sumRes.value || {});
      if (tsRes.status === 'fulfilled') setTimeseries(normalizeTimeseries(tsRes.value));
      if (siteRes.status === 'fulfilled') setBySite(extractArray(siteRes.value));
      if (usrRes.status === 'fulfilled') setByUser(extractArray(usrRes.value));
      if (roleRes.status === 'fulfilled') setByRole(extractArray(roleRes.value));
      if (modRes.status === 'fulfilled') setByModel(extractArray(modRes.value));
      if (docRes.status === 'fulfilled') {
        const docPayload = docRes.value || {};
        const recs = extractArray(docPayload);
        setDocsTotal(Number(docPayload.total ?? recs.length ?? 0));
        setDocsSyncedCount(
          recs.filter(
            (d) =>
              (d.vector_sync_status || d.sync_status || d.vector_status) === 'SYNCED_REMOTE'
          ).length
        );
      }

      const rejected = results.filter((r) => r.status === 'rejected');
      if (rejected.length === results.length) {
        setError(rejected[0].reason?.message || 'No se pudieron cargar las métricas.');
      }
    } catch (err) {
      setError(err.message || 'Error al cargar métricas.');
    } finally {
      setLoading(false);
    }
  }, [filters]);

  useEffect(() => {
    loadData();
  }, [loadData, refreshKey]);

  const totalQueries = Number(summary?.total_requests ?? summary?.total_records ?? 0);
  const directCalls = Number(
    summary?.fast_path_requests ?? summary?.direct_requests ?? summary?.saved_fast_path_calls ?? 0
  );
  const llmCalls = Number(
    summary?.llm_requests ?? Math.max(0, totalQueries - directCalls)
  );
  const tokensIn = Number(summary?.total_tokens_input ?? 0);
  const tokensOut = Number(summary?.total_tokens_output ?? 0);
  const totalTokens = Number(summary?.total_tokens ?? tokensIn + tokensOut);
  const totalCost = Number(summary?.total_cost_usd ?? summary?.total_costo_usd ?? 0);
  const directPct = Number(
    summary?.fast_path_savings_pct ??
      summary?.direct_savings_pct ??
      (totalQueries > 0 ? (directCalls / totalQueries) * 100 : 0)
  );

  const chartTimeseries = useMemo(
    () =>
      timeseries.map((pt) => ({
        ...pt,
        shortDate: formatShortDate(pt.date) || pt.date,
      })),
    [timeseries]
  );

  const lowerSingular = siteLabels.singular.toLowerCase();
  const lowerPlural = siteLabels.plural.toLowerCase();

  const siteChartData = useMemo(() => {
    return [...bySite]
      .map((row) => {
        const label =
          row.site_name || siteNameMap[row.site_id] || row.site_id || `Sin ${lowerSingular}`;
        const requests = Number(row.total_requests ?? 0);
        const tokens = Number(row.total_tokens ?? 0);
        const cost = Number(row.total_cost_usd ?? row.cost_usd ?? 0);
        return {
          ...row,
          label: label.length > 22 ? `${label.slice(0, 20)}…` : label,
          fullName: label,
          requests,
          tokens,
          cost,
        };
      })
      .sort((a, b) => b[barMetric] - a[barMetric])
      .slice(0, 8);
  }, [bySite, siteNameMap, barMetric, lowerSingular]);

  const modelPieData = useMemo(() => {
    return byModel.map((row, idx) => ({
      name: row.model || 'Desconocido',
      provider: row.provider || '—',
      requests: Number(row.total_requests ?? 0),
      tokens: Number(row.total_tokens ?? 0),
      cost: Number(row.total_cost_usd ?? row.cost_usd ?? 0),
      avgLatency: Number(row.avg_latency_ms ?? row.avg_latencia_ms ?? row.latencia_ms ?? 0),
      color: CHART_COLORS[idx % CHART_COLORS.length],
    }));
  }, [byModel]);

  const roleTotalTokens = useMemo(
    () => byRole.reduce((acc, r) => acc + Number(r.total_tokens ?? 0), 0),
    [byRole]
  );

  function handleDownloadSummaryCSV() {
    const stamp = new Date().toISOString().slice(0, 10);
    if (bySite.length > 0) {
      downloadCSV(
        `resumen-consumo-${stamp}.csv`,
        [
          { key: 'org_id', label: 'Organización' },
          { key: 'site_id', label: `${siteLabels.singular} ID` },
          {
            key: 'site_name',
            label: siteLabels.singular,
            format: (v, r) => v || siteNameMap[r.site_id] || r.site_id,
          },
          { key: 'total_requests', label: 'Consultas Totales' },
          { key: 'llm_requests', label: 'Llamadas al modelo' },
          { key: 'fast_path_requests', label: 'Respuestas directas (sin costo)' },
          { key: 'total_tokens_input', label: 'Tokens Entrada' },
          { key: 'total_tokens_output', label: 'Tokens Salida' },
          { key: 'total_tokens', label: 'Tokens Totales' },
          {
            key: 'total_cost_usd',
            label: 'Costo USD',
            format: (v) => Number(v ?? 0).toFixed(6),
          },
        ],
        bySite
      );
    } else {
      downloadCSV(
        `resumen-kpis-${stamp}.csv`,
        [
          { key: 'consultas_totales', label: 'Consultas Totales' },
          { key: 'llamadas_modelo', label: 'Llamadas al modelo' },
          { key: 'respuestas_directas', label: 'Respuestas directas (sin costo)' },
          { key: 'respuestas_directas_pct', label: 'Respuestas directas %' },
          { key: 'tokens_input', label: 'Tokens Entrada' },
          { key: 'tokens_output', label: 'Tokens Salida' },
          { key: 'tokens_total', label: 'Tokens Totales' },
          { key: 'costo_usd', label: 'Costo Estimado USD' },
          { key: 'docs_asistente', label: 'Documentos del Asistente' },
        ],
        [
          {
            consultas_totales: totalQueries,
            llamadas_modelo: llmCalls,
            respuestas_directas: directCalls,
            respuestas_directas_pct: directPct.toFixed(2),
            tokens_input: tokensIn,
            tokens_output: tokensOut,
            tokens_total: totalTokens,
            costo_usd: totalCost.toFixed(6),
            docs_asistente: docsTotal,
          },
        ]
      );
    }
    if (onToast) onToast('Resumen CSV descargado.', 'success');
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div className="page-header">
        <div>
          <h1 className="page-title">Resumen y Analítica</h1>
          <p className="page-subtitle">
            Observabilidad consolidada de consultas, consumo de tokens, respuestas directas y documentos del asistente.
          </p>
        </div>
        <div className="page-actions">
          <button
            type="button"
            className="btn btn-primary"
            onClick={handleDownloadSummaryCSV}
            disabled={loading}
          >
            <Download size={15} />
            <span>Descargar Resumen CSV</span>
          </button>
        </div>
      </div>

      {error ? (
        <div className="alert alert--error" role="alert">
          <span>{error}</span>
        </div>
      ) : null}

      {/* 5 KPI Cards */}
      <div className="kpi-grid">
        <div className="kpi-card">
          <div className="kpi-top">
            <span className="kpi-label">Consultas Totales</span>
            <span className="kpi-icon">
              <Activity size={16} />
            </span>
          </div>
          <div className="kpi-value tabular">
            {loading && !summary ? '—' : formatNumber(totalQueries)}
          </div>
          <div className="kpi-foot tabular">
            Con IA: {formatNumber(llmCalls)} • Directas: {formatNumber(directCalls)}
          </div>
        </div>

        <div className="kpi-card">
          <div className="kpi-top">
            <span className="kpi-label">Tokens IA In / Out</span>
            <span className="kpi-icon kpi-icon--violet">
              <Cpu size={16} />
            </span>
          </div>
          <div className="kpi-value tabular">
            {loading && !summary ? '—' : formatCompactNumber(totalTokens)}
          </div>
          <div className="kpi-foot tabular">
            In: {formatCompactNumber(tokensIn)} • Out: {formatCompactNumber(tokensOut)}
          </div>
        </div>

        <div className="kpi-card">
          <div className="kpi-top">
            <span className="kpi-label">Costo Estimado USD</span>
            <span className="kpi-icon kpi-icon--amber">
              <DollarSign size={16} />
            </span>
          </div>
          <div className="kpi-value tabular">
            {loading && !summary ? '—' : formatCurrency(totalCost)}
          </div>
          <div className="kpi-foot tabular">
            Prom.: {totalQueries > 0 ? formatCurrency(totalCost / totalQueries, 5) : '$0.00'}/consulta
          </div>
        </div>

        <div className="kpi-card">
          <div className="kpi-top">
            <span className="kpi-label">Respuestas directas (sin costo)</span>
            <span className="kpi-icon kpi-icon--emerald">
              <Zap size={16} />
            </span>
          </div>
          <div className="kpi-value tabular">
            {loading && !summary ? '—' : `${directPct.toFixed(1)}%`}
          </div>
          <div className="kpi-foot tabular">
            {formatNumber(directCalls)} resueltas sin llamada al modelo
          </div>
        </div>

        <div className="kpi-card">
          <div className="kpi-top">
            <span className="kpi-label">Documentos del Asistente</span>
            <span className="kpi-icon">
              <FileText size={16} />
            </span>
          </div>
          <div className="kpi-value tabular">{formatNumber(docsTotal)}</div>
          <div className="kpi-foot tabular">
            Sincronizados en muestra: {formatNumber(docsSyncedCount)}
          </div>
        </div>
      </div>

      {/* Timeseries & Site Bar Chart */}
      <div className="grid-overview-charts">
        <section className="card">
          <div className="card-header">
            <div>
              <h2 className="card-title">Tendencia diaria de consultas y tokens</h2>
              <p className="card-subtitle">Evolución diaria según filtros activos</p>
            </div>
            <div className="segmented">
              <button
                type="button"
                className={`segmented-btn ${trendMetric === 'requests' ? 'segmented-btn--active' : ''}`}
                onClick={() => setTrendMetric('requests')}
              >
                Consultas
              </button>
              <button
                type="button"
                className={`segmented-btn ${trendMetric === 'tokens' ? 'segmented-btn--active' : ''}`}
                onClick={() => setTrendMetric('tokens')}
              >
                Tokens
              </button>
              <button
                type="button"
                className={`segmented-btn ${trendMetric === 'cost' ? 'segmented-btn--active' : ''}`}
                onClick={() => setTrendMetric('cost')}
              >
                Costo USD
              </button>
            </div>
          </div>
          <div className="card-body">
            {chartTimeseries.length === 0 ? (
              <div className="empty-state" style={{ height: 270, justifyContent: 'center' }}>
                <span>No hay registros en el rango seleccionado.</span>
              </div>
            ) : (
              <div style={{ width: '100%', height: 270 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={chartTimeseries} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
                    <defs>
                      <linearGradient id="gradPrimary" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#1D4ED8" stopOpacity={0.22} />
                        <stop offset="95%" stopColor="#1D4ED8" stopOpacity={0.01} />
                      </linearGradient>
                      <linearGradient id="gradEmerald" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#059669" stopOpacity={0.24} />
                        <stop offset="95%" stopColor="#059669" stopOpacity={0.01} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" vertical={false} />
                    <XAxis dataKey="shortDate" tick={{ fontSize: 12, fill: '#6B7280' }} />
                    <YAxis
                      tick={{ fontSize: 12, fill: '#6B7280' }}
                      tickFormatter={(v) =>
                        trendMetric === 'cost' ? `$${Number(v).toFixed(2)}` : formatCompactNumber(v)
                      }
                    />
                    <Tooltip
                      contentStyle={{
                        borderRadius: 8,
                        border: '1px solid #E5E7EB',
                        fontSize: 12,
                      }}
                      formatter={(val, name) => {
                        if (name === 'Costo USD') return [formatCurrency(val, 4), name];
                        return [formatNumber(val), name];
                      }}
                      labelFormatter={(label, payload) =>
                        payload?.[0]?.payload?.date ? `Fecha: ${payload[0].payload.date}` : label
                      }
                    />
                    {trendMetric === 'requests' ? (
                      <>
                        <Area
                          type="monotone"
                          dataKey="total_requests"
                          name="Consultas Totales"
                          stroke="#1D4ED8"
                          strokeWidth={2}
                          fill="url(#gradPrimary)"
                        />
                        <Area
                          type="monotone"
                          dataKey="fast_path_requests"
                          name="Respuestas directas (sin costo)"
                          stroke="#059669"
                          strokeWidth={2}
                          fill="url(#gradEmerald)"
                        />
                      </>
                    ) : trendMetric === 'tokens' ? (
                      <Area
                        type="monotone"
                        dataKey="total_tokens"
                        name="Tokens Totales"
                        stroke="#1D4ED8"
                        strokeWidth={2}
                        fill="url(#gradPrimary)"
                      />
                    ) : (
                      <Area
                        type="monotone"
                        dataKey="total_cost_usd"
                        name="Costo USD"
                        stroke="#D97706"
                        strokeWidth={2}
                        fill="url(#gradPrimary)"
                      />
                    )}
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            )}
          </div>
        </section>

        <section className="card">
          <div className="card-header">
            <div>
              <h2 className="card-title">Consumo por {lowerSingular}</h2>
              <p className="card-subtitle">Top 8 {lowerPlural} ordenadas por consumo</p>
            </div>
            <div className="segmented">
              <button
                type="button"
                className={`segmented-btn ${barMetric === 'tokens' ? 'segmented-btn--active' : ''}`}
                onClick={() => setBarMetric('tokens')}
              >
                Tokens
              </button>
              <button
                type="button"
                className={`segmented-btn ${barMetric === 'requests' ? 'segmented-btn--active' : ''}`}
                onClick={() => setBarMetric('requests')}
              >
                Consultas
              </button>
              <button
                type="button"
                className={`segmented-btn ${barMetric === 'cost' ? 'segmented-btn--active' : ''}`}
                onClick={() => setBarMetric('cost')}
              >
                Costo
              </button>
            </div>
          </div>
          <div className="card-body">
            {siteChartData.length === 0 ? (
              <div className="empty-state" style={{ height: 270, justifyContent: 'center' }}>
                <span>Sin consumo registrado por {lowerSingular}.</span>
              </div>
            ) : (
              <div style={{ width: '100%', height: 270 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart
                    data={siteChartData}
                    layout="vertical"
                    margin={{ top: 4, right: 16, left: 6, bottom: 0 }}
                  >
                    <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" horizontal={false} />
                    <XAxis
                      type="number"
                      tick={{ fontSize: 11.5, fill: '#6B7280' }}
                      tickFormatter={(v) =>
                        barMetric === 'cost' ? `$${Number(v).toFixed(2)}` : formatCompactNumber(v)
                      }
                    />
                    <YAxis
                      type="category"
                      dataKey="label"
                      width={122}
                      tick={{ fontSize: 12, fill: '#374151' }}
                    />
                    <Tooltip
                      contentStyle={{
                        borderRadius: 8,
                        border: '1px solid #E5E7EB',
                        fontSize: 12,
                      }}
                      formatter={(val) =>
                        barMetric === 'cost' ? formatCurrency(val, 4) : formatNumber(val)
                      }
                      labelFormatter={(_, payload) => payload?.[0]?.payload?.fullName || ''}
                    />
                    <Bar
                      dataKey={barMetric}
                      name={
                        barMetric === 'tokens'
                          ? 'Tokens'
                          : barMetric === 'requests'
                          ? 'Consultas'
                          : 'Costo USD'
                      }
                      fill="#1D4ED8"
                      radius={[0, 5, 5, 0]}
                      barSize={18}
                    />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
          </div>
        </section>
      </div>

      {/* Model Usage PieChart + Table */}
      <section className="card">
        <div className="card-header">
          <div>
            <h2 className="card-title">Uso por modelo de IA (latencia promedio y costo)</h2>
            <p className="card-subtitle">Distribución de llamadas, tokens, latencia y costo por motor</p>
          </div>
        </div>
        <div className="card-body">
          {modelPieData.length === 0 ? (
            <div className="empty-state">
              <span>No hay métricas por modelo para los filtros seleccionados.</span>
            </div>
          ) : (
            <div className="grid-overview-charts" style={{ alignItems: 'center' }}>
              <div style={{ width: '100%', height: 240 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={modelPieData}
                      dataKey="tokens"
                      nameKey="name"
                      cx="50%"
                      cy="50%"
                      innerRadius={56}
                      outerRadius={90}
                      paddingAngle={2}
                    >
                      {modelPieData.map((entry) => (
                        <Cell key={entry.name} fill={entry.color} />
                      ))}
                    </Pie>
                    <Tooltip
                      contentStyle={{
                        borderRadius: 8,
                        border: '1px solid #E5E7EB',
                        fontSize: 12,
                      }}
                      formatter={(val) => [`${formatNumber(val)} tokens`, 'Consumo']}
                    />
                  </PieChart>
                </ResponsiveContainer>
              </div>

              <div className="table-wrap">
                <table className="table">
                  <thead>
                    <tr>
                      <th>Modelo</th>
                      <th>Proveedor</th>
                      <th className="text-right">Consultas</th>
                      <th className="text-right">Tokens</th>
                      <th className="text-right">Latencia Prom.</th>
                      <th className="text-right">Costo USD</th>
                    </tr>
                  </thead>
                  <tbody>
                    {modelPieData.map((m) => (
                      <tr key={`${m.provider}-${m.name}`}>
                        <td>
                          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
                            <span
                              style={{
                                width: 9,
                                height: 9,
                                borderRadius: '50%',
                                background: m.color,
                                flexShrink: 0,
                              }}
                            />
                            <span className="mono" style={{ fontWeight: 600 }}>
                              {m.name}
                            </span>
                          </span>
                        </td>
                        <td>
                          <span className="badge badge--neutral">{m.provider}</span>
                        </td>
                        <td className="text-right tabular">{formatNumber(m.requests)}</td>
                        <td className="text-right tabular">{formatNumber(m.tokens)}</td>
                        <td className="text-right tabular">
                          {m.avgLatency > 0 ? `${formatNumber(m.avgLatency)} ms` : '—'}
                        </td>
                        <td className="text-right tabular">{formatCurrency(m.cost)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      </section>

      {/* Top Users & Breakdown by Role */}
      <div className="grid-2">
        <section className="card">
          <div className="card-header">
            <h2 className="card-title">
              <Users size={16} />
              <span>Top Usuarios</span>
            </h2>
            <span className="badge badge--neutral tabular">{byUser.length} usuarios</span>
          </div>
          <div className="table-wrap">
            {byUser.length === 0 ? (
              <div className="empty-state">
                <span>Sin consumo registrado por usuario.</span>
              </div>
            ) : (
              <table className="table">
                <thead>
                  <tr>
                    <th>Usuario</th>
                    <th>{siteLabels.singular}</th>
                    <th>Rol</th>
                    <th className="text-right">Consultas</th>
                    <th className="text-right">Tokens</th>
                    <th className="text-right">Costo USD</th>
                  </tr>
                </thead>
                <tbody>
                  {byUser.slice(0, 10).map((u, idx) => (
                    <tr key={`${u.usuario}-${u.site_id}-${idx}`}>
                      <td style={{ fontWeight: 600 }}>{u.usuario}</td>
                      <td>{siteNameMap[u.site_id] || u.site_name || u.site_id}</td>
                      <td>
                        <span className="badge badge--neutral">{u.rol || 'SIN_ROL'}</span>
                      </td>
                      <td className="text-right tabular">
                        {formatNumber(u.total_requests)}
                        <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                          IA {formatNumber(u.llm_requests)} / Directas {formatNumber(u.fast_path_requests)}
                        </div>
                      </td>
                      <td className="text-right tabular">{formatNumber(u.total_tokens)}</td>
                      <td className="text-right tabular">{formatCurrency(u.total_cost_usd)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </section>

        <section className="card">
          <div className="card-header">
            <h2 className="card-title">
              <Briefcase size={16} />
              <span>Desglose por Rol</span>
            </h2>
            <span className="badge badge--neutral tabular">{byRole.length} roles</span>
          </div>
          <div className="table-wrap">
            {byRole.length === 0 ? (
              <div className="empty-state">
                <span>Sin consumo desglosado por rol.</span>
              </div>
            ) : (
              <table className="table">
                <thead>
                  <tr>
                    <th>Rol</th>
                    <th className="text-right">Consultas</th>
                    <th className="text-right">Tokens</th>
                    <th className="text-right">% Tokens</th>
                    <th className="text-right">Costo USD</th>
                  </tr>
                </thead>
                <tbody>
                  {byRole.map((r, idx) => {
                    const tokens = Number(r.total_tokens ?? 0);
                    const share = roleTotalTokens > 0 ? (tokens / roleTotalTokens) * 100 : 0;
                    return (
                      <tr key={`${r.rol}-${r.org_id}-${idx}`}>
                        <td>
                          <span className="badge badge--blue">{r.rol || 'SIN_ROL'}</span>
                        </td>
                        <td className="text-right tabular">{formatNumber(r.total_requests)}</td>
                        <td className="text-right tabular">{formatNumber(tokens)}</td>
                        <td className="text-right tabular">{share.toFixed(1)}%</td>
                        <td className="text-right tabular">{formatCurrency(r.total_cost_usd)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}
