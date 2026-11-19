import React, { useEffect, useState, useMemo, useCallback } from 'react';
import {
  MapPin,
  Plus,
  Settings,
  FileText,
  BarChart3,
  Copy,
  Check,
  RefreshCw,
  Search,
  KeyRound,
  AlertTriangle,
  Tag,
} from 'lucide-react';
import Modal from '../components/Modal';
import {
  fetchSites,
  createSite,
  updateSite,
  updateOrganization,
  fetchUsageBySite,
  fetchDocuments,
  extractArray,
  normalizeCountsBySite,
} from '../services/api';
import { formatCurrency, formatNumber, formatDateTime } from '../utils/export';
import { SITE_LABEL_PRESETS, resolveSiteLabels } from '../utils/labels';

function parseDomainsInput(raw) {
  if (!raw) return [];
  return raw
    .split(/[\n,;]+/)
    .map((s) => s.trim())
    .filter(Boolean);
}

function formatDomainsList(domains) {
  if (Array.isArray(domains)) return domains;
  if (typeof domains === 'string') return parseDomainsInput(domains);
  return [];
}

function CopyCredentialBox({ label, value }) {
  const [copied, setCopied] = useState(false);

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // fallback manual selection
    }
  }

  return (
    <div className="secret-box">
      <div style={{ fontSize: 12.5, fontWeight: 700, color: '#92400E' }}>
        {label} — Copia esta clave ahora, no volverá a mostrarse completa.
      </div>
      <div className="secret-value-row">
        <code className="secret-code">{value}</code>
        <button type="button" className="btn btn-sm" onClick={handleCopy}>
          {copied ? <Check size={14} /> : <Copy size={14} />}
          <span>{copied ? 'Copiada' : 'Copiar'}</span>
        </button>
      </div>
    </div>
  );
}

export default function SitesPage({
  user,
  organizations = [],
  activeOrg,
  siteLabels = { singular: 'Sede', plural: 'Sedes' },
  filters,
  refreshKey,
  onReloadCatalog,
  onOpenSiteDocuments,
  onOpenSiteMetrics,
  onToast,
}) {
  const isGlobalAdmin = user?.role === 'GLOBAL_ADMIN';
  const [loading, setLoading] = useState(true);
  const [sites, setSites] = useState([]);
  const [usageBySite, setUsageBySite] = useState([]);
  const [docCounts, setDocCounts] = useState({});
  const [search, setSearch] = useState('');
  const [error, setError] = useState('');

  // Customize Organization Labels Modal
  const [customizeOpen, setCustomizeOpen] = useState(false);
  const [labelTargetOrgId, setLabelTargetOrgId] = useState('');
  const [labelForm, setLabelForm] = useState({
    site_label: 'Sede',
    site_label_plural: 'Sedes',
  });
  const [savingLabels, setSavingLabels] = useState(false);
  const [labelsError, setLabelsError] = useState('');

  // Create Modal State
  const [createOpen, setCreateOpen] = useState(false);
  const [createForm, setCreateForm] = useState({
    org_id: '',
    nombre: '',
    site_code: '',
    dominios_permitidos: '',
  });
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState('');
  const [createdKey, setCreatedKey] = useState('');

  // Configure Modal State
  const [editingSite, setEditingSite] = useState(null);
  const [editForm, setEditForm] = useState({
    nombre: '',
    site_code: '',
    dominios_permitidos: '',
    status: 'ACTIVE',
  });
  const [savingEdit, setSavingEdit] = useState(false);
  const [editError, setEditError] = useState('');
  const [confirmRotate, setConfirmRotate] = useState(false);
  const [rotatingKey, setRotatingKey] = useState(false);
  const [rotatedNewKey, setRotatedNewKey] = useState('');

  const orgMap = useMemo(() => {
    const m = {};
    organizations.forEach((o) => {
      if (o.org_id) m[o.org_id] = o;
    });
    return m;
  }, [organizations]);

  const loadSitesData = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const docParams = { limit: 1, offset: 0 };
      if (filters.orgId) docParams.org_id = filters.orgId;
      if (filters.siteId) docParams.site_id = filters.siteId;

      const [sitesRes, usageRes, docsRes] = await Promise.allSettled([
        fetchSites(isGlobalAdmin ? filters.orgId : undefined),
        fetchUsageBySite(filters),
        fetchDocuments(docParams),
      ]);

      if (sitesRes.status === 'fulfilled') {
        setSites(extractArray(sitesRes.value));
      } else {
        setError(sitesRes.reason?.message || `Error al consultar ${siteLabels.plural.toLowerCase()}.`);
      }

      if (usageRes.status === 'fulfilled') {
        setUsageBySite(extractArray(usageRes.value));
      }
      if (docsRes.status === 'fulfilled') {
        setDocCounts(normalizeCountsBySite(docsRes.value?.counts_by_site));
      }
    } catch (err) {
      setError(err.message || `No se pudo cargar el listado de ${siteLabels.plural.toLowerCase()}.`);
    } finally {
      setLoading(false);
    }
  }, [filters, isGlobalAdmin, siteLabels.plural]);

  useEffect(() => {
    loadSitesData();
  }, [loadSitesData, refreshKey]);

  const usageMap = useMemo(() => {
    const map = {};
    usageBySite.forEach((row) => {
      if (row.site_id) map[row.site_id] = row;
    });
    return map;
  }, [usageBySite]);

  const mergedRows = useMemo(() => {
    const query = search.trim().toLowerCase();
    return sites
      .filter((s) => {
        if (filters.siteId && s.site_id !== filters.siteId) return false;
        if (!query) return true;
        const domains = formatDomainsList(s.dominios_permitidos).join(' ').toLowerCase();
        return (
          String(s.nombre || s.site_name || '').toLowerCase().includes(query) ||
          String(s.site_id || '').toLowerCase().includes(query) ||
          String(s.site_code || '').toLowerCase().includes(query) ||
          String(s.org_id || '').toLowerCase().includes(query) ||
          String(s.org_name || '').toLowerCase().includes(query) ||
          domains.includes(query)
        );
      })
      .map((s) => {
        const usage = usageMap[s.site_id] || {};
        return {
          ...s,
          displayName: s.nombre || s.site_name || s.site_id,
          domainsList: formatDomainsList(s.dominios_permitidos),
          total_requests: Number(usage.total_requests ?? 0),
          total_tokens: Number(usage.total_tokens ?? 0),
          total_cost_usd: Number(usage.total_cost_usd ?? 0),
          doc_count: Number(docCounts[s.site_id] ?? 0),
        };
      });
  }, [sites, usageMap, docCounts, filters.siteId, search]);

  function openCustomizeModal() {
    const defaultOrgId = isGlobalAdmin
      ? filters.orgId || organizations[0]?.org_id || ''
      : user?.org_id || activeOrg?.org_id || '';
    const targetOrg = orgMap[defaultOrgId] || activeOrg || user;
    const resolved = resolveSiteLabels(targetOrg);
    setLabelTargetOrgId(defaultOrgId);
    setLabelForm({
      site_label: resolved.singular,
      site_label_plural: resolved.plural,
    });
    setLabelsError('');
    setCustomizeOpen(true);
  }

  function handleCustomizeOrgChange(nextOrgId) {
    setLabelTargetOrgId(nextOrgId);
    const targetOrg = orgMap[nextOrgId];
    const resolved = resolveSiteLabels(targetOrg);
    setLabelForm({
      site_label: resolved.singular,
      site_label_plural: resolved.plural,
    });
  }

  async function handleSaveLabels(e) {
    e.preventDefault();
    setLabelsError('');
    const singular = labelForm.site_label.trim();
    const plural = labelForm.site_label_plural.trim();
    if (!labelTargetOrgId) {
      setLabelsError('Selecciona una organización para personalizar su nombre.');
      return;
    }
    if (!singular || !plural) {
      setLabelsError('Ingresa tanto el nombre en singular como en plural.');
      return;
    }

    setSavingLabels(true);
    try {
      const updatedOrg = await updateOrganization(labelTargetOrgId, {
        site_label: singular,
        site_label_plural: plural,
      });
      if (onToast) {
        onToast(`Etiqueta actualizada a "${singular} / ${plural}".`, 'success');
      }
      if (onReloadCatalog) {
        await onReloadCatalog(updatedOrg || {
          org_id: labelTargetOrgId,
          site_label: singular,
          site_label_plural: plural,
        });
      }
      setCustomizeOpen(false);
    } catch (err) {
      setLabelsError(err.message || 'No se pudo actualizar el nombre personalizado.');
    } finally {
      setSavingLabels(false);
    }
  }

  function openCreateModal() {
    setCreateForm({
      org_id: isGlobalAdmin
        ? filters.orgId || organizations[0]?.org_id || ''
        : user?.org_id || '',
      nombre: '',
      site_code: '',
      dominios_permitidos: '',
    });
    setCreateError('');
    setCreatedKey('');
    setCreateOpen(true);
  }

  async function handleCreateSubmit(e) {
    e.preventDefault();
    setCreateError('');
    if (!createForm.nombre.trim()) {
      setCreateError(`El nombre de la ${siteLabels.singular.toLowerCase()} es obligatorio.`);
      return;
    }
    if (isGlobalAdmin && !createForm.org_id) {
      setCreateError(`Selecciona la organización a la que pertenecerá esta ${siteLabels.singular.toLowerCase()}.`);
      return;
    }

    setCreating(true);
    try {
      const domains = parseDomainsInput(createForm.dominios_permitidos);
      const payload = {
        nombre: createForm.nombre.trim(),
      };
      if (domains.length > 0) {
        payload.dominios_permitidos = domains;
      }
      if (createForm.site_code.trim()) {
        payload.site_code = createForm.site_code.trim();
      }
      if (isGlobalAdmin && createForm.org_id) {
        payload.org_id = createForm.org_id;
      }

      const created = await createSite(payload);
      setCreatedKey(created?.api_key || '');
      if (onToast) {
        onToast(`${siteLabels.singular} "${created?.nombre || payload.nombre}" creada.`, 'success');
      }
      await loadSitesData();
      if (onReloadCatalog) await onReloadCatalog();
    } catch (err) {
      setCreateError(err.message || `Error al crear la ${siteLabels.singular.toLowerCase()}.`);
    } finally {
      setCreating(false);
    }
  }

  function openConfigureModal(site) {
    setEditingSite(site);
    setEditForm({
      nombre: site.nombre || site.site_name || '',
      site_code: site.site_code || '',
      dominios_permitidos: formatDomainsList(site.dominios_permitidos).join(', '),
      status: site.status || 'ACTIVE',
    });
    setEditError('');
    setConfirmRotate(false);
    setRotatedNewKey('');
  }

  async function handleSaveConfig(e) {
    e.preventDefault();
    if (!editingSite) return;
    setEditError('');
    if (!editForm.nombre.trim()) {
      setEditError('El nombre no puede estar vacío.');
      return;
    }

    setSavingEdit(true);
    try {
      const domains = parseDomainsInput(editForm.dominios_permitidos);
      const patchPayload = {
        nombre: editForm.nombre.trim(),
        status: editForm.status,
        dominios_permitidos: domains,
      };
      if (editForm.site_code.trim()) {
        patchPayload.site_code = editForm.site_code.trim();
      }
      await updateSite(editingSite.site_id, patchPayload);
      if (onToast) onToast(`Configuración de ${siteLabels.singular.toLowerCase()} actualizada.`, 'success');
      await loadSitesData();
      if (onReloadCatalog) await onReloadCatalog();
      setEditingSite(null);
    } catch (err) {
      setEditError(err.message || `No se pudo actualizar la ${siteLabels.singular.toLowerCase()}.`);
    } finally {
      setSavingEdit(false);
    }
  }

  async function handleRotateKey() {
    if (!editingSite) return;
    setRotatingKey(true);
    setEditError('');
    try {
      const updated = await updateSite(editingSite.site_id, {
        rotate_api_key: true,
      });
      const nextKey = updated?.new_api_key || updated?.api_key || '';
      setRotatedNewKey(nextKey);
      setConfirmRotate(false);
      if (onToast) onToast('Clave de conexión rotada exitosamente.', 'success');
      await loadSitesData();
    } catch (err) {
      setEditError(err.message || 'No fue posible rotar la clave de conexión.');
    } finally {
      setRotatingKey(false);
    }
  }

  const lowerSingular = siteLabels.singular.toLowerCase();
  const lowerPlural = siteLabels.plural.toLowerCase();

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div className="page-header">
        <div>
          <h1 className="page-title">Gestión de {siteLabels.plural}</h1>
          <p className="page-subtitle">
            Administra tus {lowerPlural}, claves de conexión para el asistente, dominios autorizados, consumo y documentos.
          </p>
        </div>
        <div className="page-actions">
          <button
            type="button"
            className="btn"
            onClick={openCustomizeModal}
            title="Cambiar cómo se muestran las sedes en tu organización (ej. IPS, Tienda, Taller)"
          >
            <Tag size={15} />
            <span>Personalizar nombre</span>
          </button>
          <button type="button" className="btn btn-primary" onClick={openCreateModal}>
            <Plus size={15} />
            <span>Crear {siteLabels.singular}</span>
          </button>
        </div>
      </div>

      {error ? (
        <div className="alert alert--error" role="alert">
          <span>{error}</span>
        </div>
      ) : null}

      <section className="card">
        <div className="table-toolbar">
          <div className="table-toolbar-group">
            <div style={{ position: 'relative', minWidth: 260 }}>
              <Search
                size={15}
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
                placeholder="Buscar por nombre, código, ID o dominio..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                style={{ paddingLeft: 32, height: 34 }}
              />
            </div>
          </div>
          <span className="badge badge--neutral tabular">
            {mergedRows.length} {lowerPlural} visibles
          </span>
        </div>

        <div className="table-wrap">
          {loading && mergedRows.length === 0 ? (
            <div className="empty-state">
              <span>Cargando {lowerPlural} y métricas...</span>
            </div>
          ) : mergedRows.length === 0 ? (
            <div className="empty-state">
              <MapPin size={26} />
              <span>No se encontraron {lowerPlural} con los filtros actuales.</span>
            </div>
          ) : (
            <table className="table">
              <thead>
                <tr>
                  <th>{siteLabels.singular}</th>
                  {isGlobalAdmin ? <th>Organización</th> : null}
                  <th>Clave de conexión</th>
                  <th>Dominios Permitidos</th>
                  <th className="text-right">Consultas</th>
                  <th className="text-right">Tokens</th>
                  <th className="text-right">Costo USD</th>
                  <th className="text-right">Docs</th>
                  <th>Estado</th>
                  <th className="text-right">Acciones</th>
                </tr>
              </thead>
              <tbody>
                {mergedRows.map((s) => {
                  const isActive = (s.status || 'ACTIVE').toUpperCase() === 'ACTIVE';
                  const orgObj = s.org_id ? orgMap[s.org_id] : null;
                  return (
                    <tr key={s.site_id}>
                      <td>
                        <div style={{ fontWeight: 600 }}>{s.displayName}</div>
                        <div className="mono" style={{ fontSize: 11.5, color: 'var(--text-muted)' }}>
                          {s.site_id}
                          {s.site_code ? ` • ${s.site_code}` : ''}
                        </div>
                      </td>
                      {isGlobalAdmin ? (
                        <td>
                          <div>{s.org_name || orgObj?.nombre || s.org_id}</div>
                          {(s.org_name || orgObj?.nombre) ? (
                            <div className="mono" style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                              {s.org_id}
                            </div>
                          ) : null}
                        </td>
                      ) : null}
                      <td>
                        <span className="mono badge badge--neutral">
                          {s.api_key_prefix ? `${s.api_key_prefix}…` : 'Clave activa'}
                        </span>
                      </td>
                      <td>
                        {s.domainsList.length === 0 ? (
                          <span style={{ color: 'var(--text-faint)', fontSize: 12 }}>Sin restricción</span>
                        ) : (
                          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, maxWidth: 230 }}>
                            {s.domainsList.slice(0, 2).map((d) => (
                              <span key={d} className="badge badge--neutral mono" style={{ fontSize: 11 }}>
                                {d}
                              </span>
                            ))}
                            {s.domainsList.length > 2 ? (
                              <span className="badge badge--neutral" title={s.domainsList.join(', ')}>
                                +{s.domainsList.length - 2}
                              </span>
                            ) : null}
                          </div>
                        )}
                      </td>
                      <td className="text-right tabular">{formatNumber(s.total_requests)}</td>
                      <td className="text-right tabular">{formatNumber(s.total_tokens)}</td>
                      <td className="text-right tabular">{formatCurrency(s.total_cost_usd)}</td>
                      <td className="text-right tabular">
                        <span className="badge badge--blue">{formatNumber(s.doc_count)}</span>
                      </td>
                      <td>
                        <span className={`badge ${isActive ? 'badge--emerald' : 'badge--rose'}`}>
                          {isActive ? 'Activa' : 'Suspendida'}
                        </span>
                      </td>
                      <td className="text-right">
                        <div style={{ display: 'inline-flex', gap: 6, justifyContent: 'flex-end' }}>
                          <button
                            type="button"
                            className="btn btn-sm"
                            onClick={() => onOpenSiteDocuments(s)}
                            title={`Ver documentos de esta ${lowerSingular}`}
                          >
                            <FileText size={13} />
                            <span>Documentos</span>
                          </button>
                          <button
                            type="button"
                            className="btn btn-sm"
                            onClick={() => onOpenSiteMetrics(s)}
                            title={`Ver analítica de esta ${lowerSingular}`}
                          >
                            <BarChart3 size={13} />
                            <span>Métricas</span>
                          </button>
                          <button
                            type="button"
                            className="btn btn-sm"
                            onClick={() => openConfigureModal(s)}
                          >
                            <Settings size={13} />
                            <span>Configurar</span>
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>
      </section>

      {/* Modal: Personalizar nombre */}
      <Modal
        open={customizeOpen}
        title="Personalizar nombre"
        onClose={() => !savingLabels && setCustomizeOpen(false)}
        footer={
          <>
            <button
              type="button"
              className="btn"
              onClick={() => setCustomizeOpen(false)}
              disabled={savingLabels}
            >
              Cancelar
            </button>
            <button
              type="submit"
              form="customize-labels-form"
              className="btn btn-primary"
              disabled={savingLabels || !labelTargetOrgId}
            >
              {savingLabels ? 'Guardando...' : 'Aplicar nombre'}
            </button>
          </>
        }
      >
        {labelsError ? (
          <div className="alert alert--error" role="alert">
            <span>{labelsError}</span>
          </div>
        ) : null}

        <p style={{ margin: 0, fontSize: 13, color: 'var(--text-secondary)' }}>
          Elige cómo se mostrará cada unidad operativa en menús, filtros y reportes para tu sector.
        </p>

        <form
          id="customize-labels-form"
          onSubmit={handleSaveLabels}
          className="form-grid"
        >
          {isGlobalAdmin ? (
            <div className="form-field form-field--full">
              <label className="form-label" htmlFor="cl-org">
                Organización *
              </label>
              <select
                id="cl-org"
                className="select"
                value={labelTargetOrgId}
                onChange={(e) => handleCustomizeOrgChange(e.target.value)}
              >
                <option value="">Selecciona una organización...</option>
                {organizations.map((o) => (
                  <option key={o.org_id} value={o.org_id}>
                    {o.nombre || o.org_name || o.org_id} ({o.org_id})
                  </option>
                ))}
              </select>
            </div>
          ) : (
            <div className="form-field form-field--full">
              <span className="form-label">Organización</span>
              <div>
                <span className="badge badge--blue">
                  {activeOrg?.nombre || activeOrg?.org_name || user?.org_name || user?.org_id}
                </span>
              </div>
            </div>
          )}

          <div className="form-field form-field--full">
            <span className="form-label">Opciones sugeridas</span>
            <div className="preset-chips">
              {SITE_LABEL_PRESETS.map((preset) => {
                const isSelected =
                  labelForm.site_label.trim() === preset.singular &&
                  labelForm.site_label_plural.trim() === preset.plural;
                return (
                  <button
                    key={`${preset.singular}-${preset.plural}`}
                    type="button"
                    className={`preset-chip ${isSelected ? 'preset-chip--active' : ''}`}
                    onClick={() =>
                      setLabelForm({
                        site_label: preset.singular,
                        site_label_plural: preset.plural,
                      })
                    }
                  >
                    {preset.singular} / {preset.plural}
                  </button>
                );
              })}
            </div>
          </div>

          <div className="form-field">
            <label className="form-label" htmlFor="cl-singular">
              Nombre en singular *
            </label>
            <input
              id="cl-singular"
              type="text"
              className="input"
              placeholder="ej. Sede, IPS, Taller"
              value={labelForm.site_label}
              onChange={(e) =>
                setLabelForm((prev) => ({ ...prev, site_label: e.target.value }))
              }
            />
          </div>

          <div className="form-field">
            <label className="form-label" htmlFor="cl-plural">
              Nombre en plural *
            </label>
            <input
              id="cl-plural"
              type="text"
              className="input"
              placeholder="ej. Sedes, IPS, Talleres"
              value={labelForm.site_label_plural}
              onChange={(e) =>
                setLabelForm((prev) => ({ ...prev, site_label_plural: e.target.value }))
              }
            />
          </div>
        </form>
      </Modal>

      {/* Modal: Crear Sede */}
      <Modal
        open={createOpen}
        title={`Crear ${siteLabels.singular}`}
        onClose={() => setCreateOpen(false)}
        footer={
          createdKey ? (
            <button type="button" className="btn btn-primary" onClick={() => setCreateOpen(false)}>
              He copiado la clave — Cerrar
            </button>
          ) : (
            <>
              <button
                type="button"
                className="btn"
                onClick={() => setCreateOpen(false)}
                disabled={creating}
              >
                Cancelar
              </button>
              <button
                type="submit"
                form="create-site-form"
                className="btn btn-primary"
                disabled={creating}
              >
                {creating ? 'Creando...' : `Crear ${siteLabels.singular}`}
              </button>
            </>
          )
        }
      >
        {createdKey ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            <div className="alert alert--success">
              <span>
                {siteLabels.singular} creada exitosamente. Guarda su clave de conexión para el asistente embebido.
              </span>
            </div>
            <CopyCredentialBox label="Clave de conexión generada" value={createdKey} />
          </div>
        ) : (
          <>
            {createError ? (
              <div className="alert alert--error" role="alert">
                <span>{createError}</span>
              </div>
            ) : null}
            <form
              id="create-site-form"
              onSubmit={handleCreateSubmit}
              className="form-grid"
            >
              {isGlobalAdmin ? (
                <div className="form-field form-field--full">
                  <label className="form-label" htmlFor="cs-org">
                    Organización *
                  </label>
                  <select
                    id="cs-org"
                    className="select"
                    value={createForm.org_id}
                    onChange={(e) =>
                      setCreateForm((prev) => ({ ...prev, org_id: e.target.value }))
                    }
                  >
                    <option value="">Selecciona una organización...</option>
                    {organizations.map((o) => (
                      <option key={o.org_id} value={o.org_id}>
                        {o.nombre || o.org_name || o.org_id} ({o.org_id})
                      </option>
                    ))}
                  </select>
                </div>
              ) : null}

              <div className="form-field">
                <label className="form-label" htmlFor="cs-nombre">
                  Nombre ({siteLabels.singular}) *
                </label>
                <input
                  id="cs-nombre"
                  type="text"
                  className="input"
                  placeholder="ej. Sede Norte Bogotá"
                  value={createForm.nombre}
                  onChange={(e) =>
                    setCreateForm((prev) => ({ ...prev, nombre: e.target.value }))
                  }
                />
              </div>

              <div className="form-field">
                <label className="form-label" htmlFor="cs-code">
                  Código interno (opcional)
                </label>
                <input
                  id="cs-code"
                  type="text"
                  className="input mono"
                  placeholder="ej. SEDE-BOG-01"
                  value={createForm.site_code}
                  onChange={(e) =>
                    setCreateForm((prev) => ({ ...prev, site_code: e.target.value }))
                  }
                />
              </div>

              <div className="form-field form-field--full">
                <label className="form-label" htmlFor="cs-domains">
                  Dominios permitidos (separados por coma)
                </label>
                <input
                  id="cs-domains"
                  type="text"
                  className="input mono"
                  placeholder="https://portal.empresa.com, http://localhost:5173"
                  value={createForm.dominios_permitidos}
                  onChange={(e) =>
                    setCreateForm((prev) => ({
                      ...prev,
                      dominios_permitidos: e.target.value,
                    }))
                  }
                />
                <span className="form-hint">
                  Orígenes web autorizados para abrir el asistente con esta clave de conexión.
                </span>
              </div>
            </form>
          </>
        )}
      </Modal>

      {/* Modal: Configurar Sede */}
      <Modal
        open={Boolean(editingSite)}
        title={
          editingSite
            ? `Configurar: ${editingSite.nombre || editingSite.site_name}`
            : `Configurar ${siteLabels.singular}`
        }
        onClose={() => setEditingSite(null)}
        footer={
          <>
            <button
              type="button"
              className="btn"
              onClick={() => setEditingSite(null)}
              disabled={savingEdit || rotatingKey}
            >
              Cerrar
            </button>
            <button
              type="submit"
              form="edit-site-form"
              className="btn btn-primary"
              disabled={savingEdit || rotatingKey}
            >
              {savingEdit ? 'Guardando...' : 'Guardar Cambios'}
            </button>
          </>
        }
      >
        {editingSite ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            {editError ? (
              <div className="alert alert--error" role="alert">
                <span>{editError}</span>
              </div>
            ) : null}

            <div
              style={{
                fontSize: 12,
                color: 'var(--text-muted)',
                display: 'flex',
                flexWrap: 'wrap',
                gap: 12,
              }}
            >
              <span>
                ID: <code className="mono">{editingSite.site_id}</code>
              </span>
              <span>Creada: {formatDateTime(editingSite.created_at)}</span>
            </div>

            <form
              id="edit-site-form"
              onSubmit={handleSaveConfig}
              className="form-grid"
            >
              <div className="form-field">
                <label className="form-label" htmlFor="es-nombre">
                  Nombre
                </label>
                <input
                  id="es-nombre"
                  type="text"
                  className="input"
                  value={editForm.nombre}
                  onChange={(e) =>
                    setEditForm((prev) => ({ ...prev, nombre: e.target.value }))
                  }
                />
              </div>

              <div className="form-field">
                <label className="form-label" htmlFor="es-code">
                  Código interno
                </label>
                <input
                  id="es-code"
                  type="text"
                  className="input mono"
                  value={editForm.site_code}
                  onChange={(e) =>
                    setEditForm((prev) => ({ ...prev, site_code: e.target.value }))
                  }
                />
              </div>

              <div className="form-field form-field--full">
                <label className="form-label" htmlFor="es-domains">
                  Dominios permitidos (separados por coma)
                </label>
                <input
                  id="es-domains"
                  type="text"
                  className="input mono"
                  value={editForm.dominios_permitidos}
                  onChange={(e) =>
                    setEditForm((prev) => ({
                      ...prev,
                      dominios_permitidos: e.target.value,
                    }))
                  }
                />
              </div>

              <div className="form-field form-field--full">
                <label className="form-label" htmlFor="es-status">
                  Estado operativo
                </label>
                <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
                  <select
                    id="es-status"
                    className="select"
                    value={editForm.status}
                    onChange={(e) =>
                      setEditForm((prev) => ({ ...prev, status: e.target.value }))
                    }
                    style={{ maxWidth: 220 }}
                  >
                    <option value="ACTIVE">Activa</option>
                    <option value="SUSPENDED">Suspendida</option>
                  </select>
                  <span
                    className={`badge ${
                      editForm.status === 'ACTIVE' ? 'badge--emerald' : 'badge--rose'
                    }`}
                  >
                    {editForm.status === 'ACTIVE' ? 'Activa' : 'Suspendida'}
                  </span>
                </div>
              </div>
            </form>

            {/* Sección Rotación Clave de conexión */}
            <div
              style={{
                borderTop: '1px solid var(--border)',
                paddingTop: 14,
                display: 'flex',
                flexDirection: 'column',
                gap: 10,
              }}
            >
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  gap: 10,
                }}
              >
                <div>
                  <div style={{ fontWeight: 600, fontSize: 13.5, display: 'flex', alignItems: 'center', gap: 6 }}>
                    <KeyRound size={15} />
                    <span>Rotación de Clave de conexión</span>
                  </div>
                  <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                    Prefijo actual:{' '}
                    <code className="mono">{editingSite.api_key_prefix || '—'}</code>
                  </div>
                </div>
                {!confirmRotate && !rotatedNewKey ? (
                  <button
                    type="button"
                    className="btn btn-danger btn-sm"
                    onClick={() => setConfirmRotate(true)}
                  >
                    <RefreshCw size={13} />
                    <span>Rotar clave</span>
                  </button>
                ) : null}
              </div>

              {confirmRotate ? (
                <div className="alert alert--warning" style={{ flexDirection: 'column' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontWeight: 600 }}>
                    <AlertTriangle size={15} />
                    <span>Confirmar rotación inmediata</span>
                  </div>
                  <span style={{ fontSize: 12.5 }}>
                    La clave actual dejará de funcionar de inmediato en los sitios web donde esté instalada.
                  </span>
                  <div style={{ display: 'flex', gap: 8 }}>
                    <button
                      type="button"
                      className="btn btn-danger-solid btn-sm"
                      onClick={handleRotateKey}
                      disabled={rotatingKey}
                    >
                      {rotatingKey ? 'Rotando...' : 'Sí, generar nueva clave'}
                    </button>
                    <button
                      type="button"
                      className="btn btn-sm"
                      onClick={() => setConfirmRotate(false)}
                      disabled={rotatingKey}
                    >
                      Cancelar
                    </button>
                  </div>
                </div>
              ) : null}

              {rotatedNewKey ? (
                <CopyCredentialBox label="Nueva clave de conexión generada" value={rotatedNewKey} />
              ) : null}
            </div>
          </div>
        ) : null}
      </Modal>
    </div>
  );
}
