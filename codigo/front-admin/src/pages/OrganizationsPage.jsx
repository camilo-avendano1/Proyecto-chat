import React, { useEffect, useState, useMemo, useCallback } from 'react';
import {
  Building2,
  Plus,
  MapPin,
  UserPlus,
  Users,
  KeyRound,
  ShieldCheck,
  Power,
  Pencil,
} from 'lucide-react';
import Modal from '../components/Modal';
import {
  fetchOrganizations,
  createOrganization,
  updateOrganization,
  fetchAdminUsers,
  createAdminUser,
  updateAdminUser,
  fetchUsageBySite,
  extractArray,
} from '../services/api';
import {
  formatCompactNumber,
  formatCurrency,
  formatDateTime,
  formatNumber,
} from '../utils/export';
import { SITE_LABEL_PRESETS, formatRoleLabel, resolveSiteLabels } from '../utils/labels';

function parseDomains(raw) {
  if (!raw) return [];
  return raw
    .split(/[\n,;]+/)
    .map((s) => s.trim())
    .filter(Boolean);
}

function formatDomainsList(domains) {
  if (Array.isArray(domains)) return domains;
  if (typeof domains === 'string') return parseDomains(domains);
  return [];
}

export default function OrganizationsPage({
  currentUser,
  filters,
  refreshKey,
  onReloadCatalog,
  onInspectOrgSites,
  onToast,
}) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [organizations, setOrganizations] = useState([]);
  const [adminUsers, setAdminUsers] = useState([]);
  const [usageBySite, setUsageBySite] = useState([]);

  // Create Organization Modal
  const [createOrgOpen, setCreateOrgOpen] = useState(false);
  const [orgForm, setOrgForm] = useState({
    org_id: '',
    nombre: '',
    busqueda_api_url: '',
    dominios_permitidos: '',
    site_label: 'Sede',
    site_label_plural: 'Sedes',
  });
  const [savingOrg, setSavingOrg] = useState(false);
  const [orgError, setOrgError] = useState('');

  // Edit Organization Modal
  const [editingOrg, setEditingOrg] = useState(null);
  const [editOrgForm, setEditOrgForm] = useState({
    nombre: '',
    busqueda_api_url: '',
    dominios_permitidos: '',
    site_label: 'Sede',
    site_label_plural: 'Sedes',
    status: 'ACTIVE',
  });
  const [savingEditOrg, setSavingEditOrg] = useState(false);
  const [editOrgError, setEditOrgError] = useState('');

  // Create Admin User Modal
  const [createUserOpen, setCreateUserOpen] = useState(false);
  const [userForm, setUserForm] = useState({
    username: '',
    full_name: '',
    password: '',
    role: 'ORG_ADMIN',
    org_id: '',
  });
  const [savingUser, setSavingUser] = useState(false);
  const [userError, setUserError] = useState('');

  // Edit Admin User Modal
  const [editingUser, setEditingUser] = useState(null);
  const [editUserForm, setEditUserForm] = useState({
    full_name: '',
    role: 'ORG_ADMIN',
    org_id: '',
    is_active: true,
    password: '',
  });
  const [savingEditUser, setSavingEditUser] = useState(false);
  const [editUserError, setEditUserError] = useState('');

  const loadData = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const [orgsRes, usersRes, usageRes] = await Promise.allSettled([
        fetchOrganizations(),
        fetchAdminUsers(),
        fetchUsageBySite({ timeRange: filters.timeRange }),
      ]);

      if (orgsRes.status === 'fulfilled') {
        setOrganizations(extractArray(orgsRes.value));
      } else {
        setError(orgsRes.reason?.message || 'Error al cargar organizaciones.');
      }

      if (usersRes.status === 'fulfilled') {
        setAdminUsers(extractArray(usersRes.value));
      }

      if (usageRes.status === 'fulfilled') {
        setUsageBySite(extractArray(usageRes.value));
      }
    } catch (err) {
      setError(err.message || 'No se pudieron cargar los datos de organizaciones.');
    } finally {
      setLoading(false);
    }
  }, [filters.timeRange]);

  useEffect(() => {
    loadData();
  }, [loadData, refreshKey]);

  const orgMap = useMemo(() => {
    const map = {};
    organizations.forEach((o) => {
      if (o.org_id) map[o.org_id] = o;
    });
    return map;
  }, [organizations]);

  const usageByOrg = useMemo(() => {
    const map = {};
    usageBySite.forEach((row) => {
      const oid = row.org_id;
      if (!oid) return;
      if (!map[oid]) {
        map[oid] = { tokens: 0, cost: 0, requests: 0 };
      }
      map[oid].tokens += Number(row.total_tokens ?? 0);
      map[oid].cost += Number(row.total_cost_usd ?? row.cost_usd ?? 0);
      map[oid].requests += Number(row.total_requests ?? 0);
    });
    return map;
  }, [usageBySite]);

  function openNewOrgModal() {
    setOrgForm({
      org_id: '',
      nombre: '',
      busqueda_api_url: '',
      dominios_permitidos: '',
      site_label: 'Sede',
      site_label_plural: 'Sedes',
    });
    setOrgError('');
    setCreateOrgOpen(true);
  }

  async function handleCreateOrg(e) {
    e.preventDefault();
    setOrgError('');
    const oid = orgForm.org_id.trim();
    const nombre = orgForm.nombre.trim();
    const singular = orgForm.site_label.trim() || 'Sede';
    const plural = orgForm.site_label_plural.trim() || 'Sedes';
    if (!oid || !nombre) {
      setOrgError('Los campos identificador (org_id) y nombre son obligatorios.');
      return;
    }

    setSavingOrg(true);
    try {
      const payload = {
        org_id: oid,
        nombre,
        site_label: singular,
        site_label_plural: plural,
      };
      if (orgForm.busqueda_api_url.trim()) {
        payload.busqueda_api_url = orgForm.busqueda_api_url.trim();
      }
      const domains = parseDomains(orgForm.dominios_permitidos);
      if (domains.length > 0) {
        payload.dominios_permitidos = domains;
      }
      await createOrganization(payload);
      if (onToast) onToast(`Organización "${nombre}" creada.`, 'success');
      setCreateOrgOpen(false);
      await loadData();
      if (onReloadCatalog) await onReloadCatalog();
    } catch (err) {
      setOrgError(err.message || 'No se pudo crear la organización.');
    } finally {
      setSavingOrg(false);
    }
  }

  function openEditOrgModal(org) {
    const labels = resolveSiteLabels(org);
    setEditingOrg(org);
    setEditOrgForm({
      nombre: org.nombre || org.org_name || '',
      busqueda_api_url: org.busqueda_api_url || '',
      dominios_permitidos: formatDomainsList(org.dominios_permitidos).join(', '),
      site_label: labels.singular,
      site_label_plural: labels.plural,
      status: org.status || 'ACTIVE',
    });
    setEditOrgError('');
  }

  async function handleSaveEditOrg(e) {
    e.preventDefault();
    if (!editingOrg) return;
    setEditOrgError('');

    const nombre = editOrgForm.nombre.trim();
    const singular = editOrgForm.site_label.trim();
    const plural = editOrgForm.site_label_plural.trim();
    if (!nombre) {
      setEditOrgError('El nombre de la organización es obligatorio.');
      return;
    }
    if (!singular || !plural) {
      setEditOrgError('Define los nombres en singular y plural para sus unidades.');
      return;
    }

    setSavingEditOrg(true);
    try {
      const payload = {
        nombre,
        site_label: singular,
        site_label_plural: plural,
        status: editOrgForm.status,
        busqueda_api_url: editOrgForm.busqueda_api_url.trim() || null,
        dominios_permitidos: parseDomains(editOrgForm.dominios_permitidos),
      };
      const updated = await updateOrganization(editingOrg.org_id, payload);
      if (onToast) onToast(`Organización "${nombre}" actualizada.`, 'success');
      setEditingOrg(null);
      await loadData();
      if (onReloadCatalog) await onReloadCatalog(updated);
    } catch (err) {
      setEditOrgError(err.message || 'No se pudo actualizar la organización.');
    } finally {
      setSavingEditOrg(false);
    }
  }

  function openNewUserModal() {
    setUserForm({
      username: '',
      full_name: '',
      password: '',
      role: 'ORG_ADMIN',
      org_id: organizations[0]?.org_id || '',
    });
    setUserError('');
    setCreateUserOpen(true);
  }

  async function handleCreateUser(e) {
    e.preventDefault();
    setUserError('');
    const uname = userForm.username.trim();
    if (!/^[a-zA-Z0-9._-]{3,100}$/.test(uname)) {
      setUserError('El usuario debe tener entre 3 y 100 caracteres (letras, números, . _ -).');
      return;
    }
    if (userForm.password.length < 10 || userForm.password.length > 72) {
      setUserError('La contraseña debe tener entre 10 y 72 caracteres.');
      return;
    }
    if (userForm.role === 'ORG_ADMIN' && !userForm.org_id) {
      setUserError('Un Administrador debe estar asignado a una organización.');
      return;
    }

    setSavingUser(true);
    try {
      await createAdminUser({
        username: uname,
        full_name: userForm.full_name.trim() || null,
        password: userForm.password,
        role: userForm.role,
        org_id: userForm.role === 'GLOBAL_ADMIN' ? null : userForm.org_id,
      });
      if (onToast) onToast(`Administrador "${uname}" creado.`, 'success');
      setCreateUserOpen(false);
      await loadData();
    } catch (err) {
      setUserError(err.message || 'Error al crear el administrador.');
    } finally {
      setSavingUser(false);
    }
  }

  function openEditUserModal(admin) {
    setEditingUser(admin);
    setEditUserForm({
      full_name: admin.full_name || '',
      role: admin.role || 'ORG_ADMIN',
      org_id: admin.org_id || '',
      is_active: Boolean(admin.is_active),
      password: '',
    });
    setEditUserError('');
  }

  async function handleSaveEditUser(e) {
    e.preventDefault();
    if (!editingUser) return;
    setEditUserError('');

    if (
      editUserForm.password &&
      (editUserForm.password.length < 10 || editUserForm.password.length > 72)
    ) {
      setEditUserError('Si cambias la contraseña, debe tener entre 10 y 72 caracteres.');
      return;
    }
    if (editUserForm.role === 'ORG_ADMIN' && !editUserForm.org_id) {
      setEditUserError('El perfil Administrador requiere seleccionar una organización.');
      return;
    }

    setSavingEditUser(true);
    try {
      const payload = {
        full_name: editUserForm.full_name.trim() || null,
        role: editUserForm.role,
        org_id: editUserForm.role === 'GLOBAL_ADMIN' ? null : editUserForm.org_id,
        is_active: editUserForm.is_active,
      };
      if (editUserForm.password) {
        payload.password = editUserForm.password;
      }

      await updateAdminUser(editingUser.admin_id, payload);
      if (onToast) onToast(`Administrador "${editingUser.username}" actualizado.`, 'success');
      setEditingUser(null);
      await loadData();
    } catch (err) {
      setEditUserError(err.message || 'Error al actualizar el administrador.');
    } finally {
      setSavingEditUser(false);
    }
  }

  async function handleToggleUserActive(admin) {
    try {
      await updateAdminUser(admin.admin_id, { is_active: !admin.is_active });
      if (onToast) {
        onToast(
          `Usuario "${admin.username}" ${!admin.is_active ? 'activado' : 'desactivado'}.`,
          'success'
        );
      }
      await loadData();
    } catch (err) {
      if (onToast) onToast(err.message || 'No se pudo cambiar el estado del usuario.', 'error');
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 22 }}>
      <div className="page-header">
        <div>
          <h1 className="page-title">Organizaciones y Accesos</h1>
          <p className="page-subtitle">
            Administración global de organizaciones, nomenclatura personalizada, consumo agregado y usuarios administrativos.
          </p>
        </div>
        <div className="page-actions">
          <button type="button" className="btn" onClick={openNewUserModal}>
            <UserPlus size={15} />
            <span>Nuevo Administrador</span>
          </button>
          <button type="button" className="btn btn-primary" onClick={openNewOrgModal}>
            <Plus size={15} />
            <span>Nueva Organización</span>
          </button>
        </div>
      </div>

      {error ? (
        <div className="alert alert--error" role="alert">
          <span>{error}</span>
        </div>
      ) : null}

      {/* Organizations Summary Cards */}
      <section>
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            marginBottom: 12,
          }}
        >
          <h2 style={{ margin: 0, fontSize: 16, fontWeight: 700, display: 'flex', alignItems: 'center', gap: 8 }}>
            <Building2 size={17} />
            <span>Organizaciones ({organizations.length})</span>
          </h2>
        </div>

        {loading && organizations.length === 0 ? (
          <div className="card">
            <div className="empty-state">Cargando organizaciones...</div>
          </div>
        ) : organizations.length === 0 ? (
          <div className="card">
            <div className="empty-state">No hay organizaciones registradas.</div>
          </div>
        ) : (
          <div className="grid-3">
            {organizations.map((org) => {
              const stats = usageByOrg[org.org_id] || { tokens: 0, cost: 0, requests: 0 };
              const isActive = (org.status || 'ACTIVE').toUpperCase() === 'ACTIVE';
              const labels = resolveSiteLabels(org);
              return (
                <div key={org.org_id} className="card">
                  <div className="card-body" style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8 }}>
                      <div>
                        <div style={{ fontWeight: 700, fontSize: 15 }}>{org.nombre || org.org_name}</div>
                        <div className="mono" style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                          {org.org_id}
                        </div>
                      </div>
                      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', justifyContent: 'flex-end' }}>
                        <span className="badge badge--neutral" title="Nomenclatura personalizada">
                          {labels.singular} / {labels.plural}
                        </span>
                        <span className={`badge ${isActive ? 'badge--emerald' : 'badge--rose'}`}>
                          {isActive ? 'Activa' : 'Suspendida'}
                        </span>
                      </div>
                    </div>

                    <div
                      style={{
                        display: 'grid',
                        gridTemplateColumns: 'repeat(3, minmax(0, 1fr))',
                        gap: 8,
                        padding: '10px 12px',
                        borderRadius: 'var(--radius-sm)',
                        background: 'var(--bg-subtle)',
                        border: '1px solid var(--border)',
                      }}
                    >
                      <div>
                        <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{labels.plural}</div>
                        <div className="tabular" style={{ fontWeight: 700, fontSize: 14 }}>
                          {formatNumber(org.active_site_count ?? 0)}/{formatNumber(org.site_count ?? 0)}
                        </div>
                      </div>
                      <div>
                        <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>Tokens</div>
                        <div className="tabular" style={{ fontWeight: 700, fontSize: 14 }}>
                          {formatCompactNumber(stats.tokens)}
                        </div>
                      </div>
                      <div>
                        <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>Costo USD</div>
                        <div className="tabular" style={{ fontWeight: 700, fontSize: 14 }}>
                          {formatCurrency(stats.cost)}
                        </div>
                      </div>
                    </div>

                    {org.busqueda_api_url ? (
                      <div style={{ fontSize: 11.5, color: 'var(--text-muted)' }} className="truncate-cell">
                        Buscador externo: <code className="mono">{org.busqueda_api_url}</code>
                      </div>
                    ) : null}

                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
                      <span style={{ fontSize: 11.5, color: 'var(--text-faint)' }}>
                        {formatDateTime(org.created_at)}
                      </span>
                      <div style={{ display: 'flex', gap: 6 }}>
                        <button
                          type="button"
                          className="btn btn-sm"
                          onClick={() => openEditOrgModal(org)}
                          title="Editar organización y su etiqueta"
                        >
                          <Pencil size={13} />
                          <span>Editar</span>
                        </button>
                        <button
                          type="button"
                          className="btn btn-sm"
                          onClick={() => onInspectOrgSites(org.org_id)}
                        >
                          <MapPin size={13} />
                          <span>Ver {labels.plural}</span>
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </section>

      {/* Admin Users Management Table */}
      <section className="card">
        <div className="card-header">
          <div>
            <h2 className="card-title">
              <Users size={17} />
              <span>Administradores de la Consola</span>
            </h2>
            <p className="card-subtitle">
              Gestión de cuentas con perfil Admin Global y Administrador por organización.
            </p>
          </div>
          <span className="badge badge--neutral tabular">{adminUsers.length} usuarios</span>
        </div>

        <div className="table-wrap">
          {adminUsers.length === 0 ? (
            <div className="empty-state">
              <ShieldCheck size={24} />
              <span>No hay usuarios administrativos disponibles.</span>
            </div>
          ) : (
            <table className="table">
              <thead>
                <tr>
                  <th>Usuario</th>
                  <th>Nombre Completo</th>
                  <th>Rol</th>
                  <th>Organización Asignada</th>
                  <th>Último Acceso</th>
                  <th>Estado</th>
                  <th className="text-right">Acciones</th>
                </tr>
              </thead>
              <tbody>
                {adminUsers.map((admin) => {
                  const isSelf = admin.admin_id === currentUser?.admin_id;
                  const isGlobal = admin.role === 'GLOBAL_ADMIN';
                  const orgObj = admin.org_id ? orgMap[admin.org_id] : null;
                  return (
                    <tr key={admin.admin_id}>
                      <td>
                        <span className="mono" style={{ fontWeight: 600 }}>
                          {admin.username}
                        </span>
                        {isSelf ? (
                          <span className="badge badge--blue" style={{ marginLeft: 6, fontSize: 10.5 }}>
                            Tú
                          </span>
                        ) : null}
                      </td>
                      <td>{admin.full_name || '—'}</td>
                      <td>
                        <span className={`badge ${isGlobal ? 'badge--violet' : 'badge--blue'}`}>
                          {formatRoleLabel(admin.role)}
                        </span>
                      </td>
                      <td>
                        {admin.org_id ? (
                          <div>
                            <div style={{ fontSize: 13 }}>
                              {admin.org_name || orgObj?.nombre || admin.org_id}
                            </div>
                            <div className="mono" style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                              {admin.org_id}
                            </div>
                          </div>
                        ) : (
                          <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                            Plataforma global
                          </span>
                        )}
                      </td>
                      <td style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
                        {formatDateTime(admin.last_login_at)}
                      </td>
                      <td>
                        <span
                          className={`badge ${
                            admin.is_active ? 'badge--emerald' : 'badge--rose'
                          }`}
                        >
                          {admin.is_active ? 'Activo' : 'Inactivo'}
                        </span>
                      </td>
                      <td className="text-right">
                        <div style={{ display: 'inline-flex', gap: 6 }}>
                          <button
                            type="button"
                            className="btn btn-sm"
                            onClick={() => openEditUserModal(admin)}
                          >
                            <KeyRound size={13} />
                            <span>Editar / Clave</span>
                          </button>
                          <button
                            type="button"
                            className={`btn btn-sm ${admin.is_active ? 'btn-danger' : ''}`}
                            disabled={isSelf}
                            title={
                              isSelf
                                ? 'No puedes desactivar tu propia sesión'
                                : admin.is_active
                                ? 'Desactivar acceso'
                                : 'Reactivar acceso'
                            }
                            onClick={() => handleToggleUserActive(admin)}
                          >
                            <Power size={13} />
                            <span>{admin.is_active ? 'Desactivar' : 'Activar'}</span>
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

      {/* Modal: Nueva Organización */}
      <Modal
        open={createOrgOpen}
        title="Nueva Organización"
        onClose={() => !savingOrg && setCreateOrgOpen(false)}
        footer={
          <>
            <button
              type="button"
              className="btn"
              disabled={savingOrg}
              onClick={() => setCreateOrgOpen(false)}
            >
              Cancelar
            </button>
            <button
              type="submit"
              form="new-org-form"
              className="btn btn-primary"
              disabled={savingOrg}
            >
              {savingOrg ? 'Creando...' : 'Crear Organización'}
            </button>
          </>
        }
      >
        {orgError ? (
          <div className="alert alert--error" role="alert">
            <span>{orgError}</span>
          </div>
        ) : null}

        <form id="new-org-form" onSubmit={handleCreateOrg} className="form-grid">
          <div className="form-field">
            <label className="form-label" htmlFor="no-id">
              Identificador único (org_id) *
            </label>
            <input
              id="no-id"
              type="text"
              className="input mono"
              placeholder="ej. clinica_vida"
              value={orgForm.org_id}
              onChange={(e) =>
                setOrgForm((prev) => ({ ...prev, org_id: e.target.value }))
              }
            />
          </div>

          <div className="form-field">
            <label className="form-label" htmlFor="no-nombre">
              Nombre comercial *
            </label>
            <input
              id="no-nombre"
              type="text"
              className="input"
              placeholder="ej. Clínica Vida Integral S.A.S."
              value={orgForm.nombre}
              onChange={(e) =>
                setOrgForm((prev) => ({ ...prev, nombre: e.target.value }))
              }
            />
          </div>

          <div className="form-field form-field--full">
            <span className="form-label">¿Cómo llama esta organización a sus sedes?</span>
            <div className="preset-chips">
              {SITE_LABEL_PRESETS.map((preset) => {
                const isSelected =
                  orgForm.site_label.trim() === preset.singular &&
                  orgForm.site_label_plural.trim() === preset.plural;
                return (
                  <button
                    key={`${preset.singular}-${preset.plural}`}
                    type="button"
                    className={`preset-chip ${isSelected ? 'preset-chip--active' : ''}`}
                    onClick={() =>
                      setOrgForm((prev) => ({
                        ...prev,
                        site_label: preset.singular,
                        site_label_plural: preset.plural,
                      }))
                    }
                  >
                    {preset.singular} / {preset.plural}
                  </button>
                );
              })}
            </div>
          </div>

          <div className="form-field">
            <label className="form-label" htmlFor="no-label">
              Etiqueta singular
            </label>
            <input
              id="no-label"
              type="text"
              className="input"
              placeholder="Sede"
              value={orgForm.site_label}
              onChange={(e) =>
                setOrgForm((prev) => ({ ...prev, site_label: e.target.value }))
              }
            />
          </div>

          <div className="form-field">
            <label className="form-label" htmlFor="no-label-plural">
              Etiqueta plural
            </label>
            <input
              id="no-label-plural"
              type="text"
              className="input"
              placeholder="Sedes"
              value={orgForm.site_label_plural}
              onChange={(e) =>
                setOrgForm((prev) => ({ ...prev, site_label_plural: e.target.value }))
              }
            />
          </div>

          <div className="form-field form-field--full">
            <label className="form-label" htmlFor="no-busqueda">
              URL de Buscador Externo (opcional)
            </label>
            <input
              id="no-busqueda"
              type="url"
              className="input mono"
              placeholder="https://busqueda.empresa.com/api/v1/search"
              value={orgForm.busqueda_api_url}
              onChange={(e) =>
                setOrgForm((prev) => ({ ...prev, busqueda_api_url: e.target.value }))
              }
            />
          </div>

          <div className="form-field form-field--full">
            <label className="form-label" htmlFor="no-domains">
              Dominios permitidos por defecto (separados por coma)
            </label>
            <input
              id="no-domains"
              type="text"
              className="input mono"
              placeholder="https://portal.empresa.com, https://sede.empresa.com"
              value={orgForm.dominios_permitidos}
              onChange={(e) =>
                setOrgForm((prev) => ({
                  ...prev,
                  dominios_permitidos: e.target.value,
                }))
              }
            />
          </div>
        </form>
      </Modal>

      {/* Modal: Editar Organización */}
      <Modal
        open={Boolean(editingOrg)}
        title={
          editingOrg
            ? `Editar Organización: ${editingOrg.nombre || editingOrg.org_id}`
            : 'Editar Organización'
        }
        onClose={() => !savingEditOrg && setEditingOrg(null)}
        footer={
          <>
            <button
              type="button"
              className="btn"
              disabled={savingEditOrg}
              onClick={() => setEditingOrg(null)}
            >
              Cancelar
            </button>
            <button
              type="submit"
              form="edit-org-form"
              className="btn btn-primary"
              disabled={savingEditOrg}
            >
              {savingEditOrg ? 'Guardando...' : 'Guardar Cambios'}
            </button>
          </>
        }
      >
        {editOrgError ? (
          <div className="alert alert--error" role="alert">
            <span>{editOrgError}</span>
          </div>
        ) : null}

        {editingOrg ? (
          <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
            Identificador: <code className="mono">{editingOrg.org_id}</code>
          </div>
        ) : null}

        <form id="edit-org-form" onSubmit={handleSaveEditOrg} className="form-grid">
          <div className="form-field">
            <label className="form-label" htmlFor="eo-nombre">
              Nombre comercial *
            </label>
            <input
              id="eo-nombre"
              type="text"
              className="input"
              value={editOrgForm.nombre}
              onChange={(e) =>
                setEditOrgForm((prev) => ({ ...prev, nombre: e.target.value }))
              }
            />
          </div>

          <div className="form-field">
            <label className="form-label" htmlFor="eo-status">
              Estado
            </label>
            <select
              id="eo-status"
              className="select"
              value={editOrgForm.status}
              onChange={(e) =>
                setEditOrgForm((prev) => ({ ...prev, status: e.target.value }))
              }
            >
              <option value="ACTIVE">Activa</option>
              <option value="SUSPENDED">Suspendida</option>
            </select>
          </div>

          <div className="form-field form-field--full">
            <span className="form-label">Etiqueta de unidades operativas</span>
            <div className="preset-chips">
              {SITE_LABEL_PRESETS.map((preset) => {
                const isSelected =
                  editOrgForm.site_label.trim() === preset.singular &&
                  editOrgForm.site_label_plural.trim() === preset.plural;
                return (
                  <button
                    key={`${preset.singular}-${preset.plural}`}
                    type="button"
                    className={`preset-chip ${isSelected ? 'preset-chip--active' : ''}`}
                    onClick={() =>
                      setEditOrgForm((prev) => ({
                        ...prev,
                        site_label: preset.singular,
                        site_label_plural: preset.plural,
                      }))
                    }
                  >
                    {preset.singular} / {preset.plural}
                  </button>
                );
              })}
            </div>
          </div>

          <div className="form-field">
            <label className="form-label" htmlFor="eo-label">
              Etiqueta singular *
            </label>
            <input
              id="eo-label"
              type="text"
              className="input"
              value={editOrgForm.site_label}
              onChange={(e) =>
                setEditOrgForm((prev) => ({ ...prev, site_label: e.target.value }))
              }
            />
          </div>

          <div className="form-field">
            <label className="form-label" htmlFor="eo-label-plural">
              Etiqueta plural *
            </label>
            <input
              id="eo-label-plural"
              type="text"
              className="input"
              value={editOrgForm.site_label_plural}
              onChange={(e) =>
                setEditOrgForm((prev) => ({ ...prev, site_label_plural: e.target.value }))
              }
            />
          </div>

          <div className="form-field form-field--full">
            <label className="form-label" htmlFor="eo-busqueda">
              URL de Buscador Externo (opcional)
            </label>
            <input
              id="eo-busqueda"
              type="url"
              className="input mono"
              placeholder="https://busqueda.empresa.com/api/v1/search"
              value={editOrgForm.busqueda_api_url}
              onChange={(e) =>
                setEditOrgForm((prev) => ({ ...prev, busqueda_api_url: e.target.value }))
              }
            />
          </div>

          <div className="form-field form-field--full">
            <label className="form-label" htmlFor="eo-domains">
              Dominios permitidos (separados por coma)
            </label>
            <input
              id="eo-domains"
              type="text"
              className="input mono"
              value={editOrgForm.dominios_permitidos}
              onChange={(e) =>
                setEditOrgForm((prev) => ({
                  ...prev,
                  dominios_permitidos: e.target.value,
                }))
              }
            />
          </div>
        </form>
      </Modal>

      {/* Modal: Crear Administrador */}
      <Modal
        open={createUserOpen}
        title="Crear Usuario Administrador"
        onClose={() => !savingUser && setCreateUserOpen(false)}
        footer={
          <>
            <button
              type="button"
              className="btn"
              disabled={savingUser}
              onClick={() => setCreateUserOpen(false)}
            >
              Cancelar
            </button>
            <button
              type="submit"
              form="create-admin-form"
              className="btn btn-primary"
              disabled={savingUser}
            >
              {savingUser ? 'Creando...' : 'Crear Administrador'}
            </button>
          </>
        }
      >
        {userError ? (
          <div className="alert alert--error" role="alert">
            <span>{userError}</span>
          </div>
        ) : null}

        <form id="create-admin-form" onSubmit={handleCreateUser} className="form-grid">
          <div className="form-field">
            <label className="form-label" htmlFor="cu-username">
              Usuario *
            </label>
            <input
              id="cu-username"
              type="text"
              className="input mono"
              placeholder="ej. admin.clinica"
              value={userForm.username}
              onChange={(e) =>
                setUserForm((prev) => ({ ...prev, username: e.target.value }))
              }
            />
          </div>

          <div className="form-field">
            <label className="form-label" htmlFor="cu-fullname">
              Nombre completo
            </label>
            <input
              id="cu-fullname"
              type="text"
              className="input"
              placeholder="ej. Laura Gómez"
              value={userForm.full_name}
              onChange={(e) =>
                setUserForm((prev) => ({ ...prev, full_name: e.target.value }))
              }
            />
          </div>

          <div className="form-field">
            <label className="form-label" htmlFor="cu-role">
              Perfil / Rol *
            </label>
            <select
              id="cu-role"
              className="select"
              value={userForm.role}
              onChange={(e) =>
                setUserForm((prev) => ({ ...prev, role: e.target.value }))
              }
            >
              <option value="ORG_ADMIN">{formatRoleLabel('ORG_ADMIN')}</option>
              <option value="GLOBAL_ADMIN">{formatRoleLabel('GLOBAL_ADMIN')}</option>
            </select>
          </div>

          <div className="form-field">
            <label className="form-label" htmlFor="cu-org">
              Organización asignada {userForm.role === 'ORG_ADMIN' ? '*' : ''}
            </label>
            <select
              id="cu-org"
              className="select"
              disabled={userForm.role === 'GLOBAL_ADMIN'}
              value={userForm.role === 'GLOBAL_ADMIN' ? '' : userForm.org_id}
              onChange={(e) =>
                setUserForm((prev) => ({ ...prev, org_id: e.target.value }))
              }
            >
              <option value="">
                {userForm.role === 'GLOBAL_ADMIN'
                  ? 'Plataforma global'
                  : 'Selecciona una organización...'}
              </option>
              {organizations.map((o) => (
                <option key={o.org_id} value={o.org_id}>
                  {o.nombre || o.org_name || o.org_id} ({o.org_id})
                </option>
              ))}
            </select>
          </div>

          <div className="form-field form-field--full">
            <label className="form-label" htmlFor="cu-password">
              Contraseña inicial (10–72 caracteres) *
            </label>
            <input
              id="cu-password"
              type="password"
              className="input"
              value={userForm.password}
              onChange={(e) =>
                setUserForm((prev) => ({ ...prev, password: e.target.value }))
              }
            />
          </div>
        </form>
      </Modal>

      {/* Modal: Editar / Resetear Contraseña de Administrador */}
      <Modal
        open={Boolean(editingUser)}
        title={editingUser ? `Editar Administrador: ${editingUser.username}` : 'Editar Administrador'}
        onClose={() => !savingEditUser && setEditingUser(null)}
        footer={
          <>
            <button
              type="button"
              className="btn"
              disabled={savingEditUser}
              onClick={() => setEditingUser(null)}
            >
              Cancelar
            </button>
            <button
              type="submit"
              form="edit-admin-form"
              className="btn btn-primary"
              disabled={savingEditUser}
            >
              {savingEditUser ? 'Guardando...' : 'Guardar Cambios'}
            </button>
          </>
        }
      >
        {editUserError ? (
          <div className="alert alert--error" role="alert">
            <span>{editUserError}</span>
          </div>
        ) : null}

        <form id="edit-admin-form" onSubmit={handleSaveEditUser} className="form-grid">
          <div className="form-field">
            <label className="form-label" htmlFor="eu-fullname">
              Nombre completo
            </label>
            <input
              id="eu-fullname"
              type="text"
              className="input"
              value={editUserForm.full_name}
              onChange={(e) =>
                setEditUserForm((prev) => ({ ...prev, full_name: e.target.value }))
              }
            />
          </div>

          <div className="form-field">
            <label className="form-label" htmlFor="eu-role">
              Perfil / Rol
            </label>
            <select
              id="eu-role"
              className="select"
              value={editUserForm.role}
              onChange={(e) =>
                setEditUserForm((prev) => ({ ...prev, role: e.target.value }))
              }
            >
              <option value="ORG_ADMIN">{formatRoleLabel('ORG_ADMIN')}</option>
              <option value="GLOBAL_ADMIN">{formatRoleLabel('GLOBAL_ADMIN')}</option>
            </select>
          </div>

          <div className="form-field">
            <label className="form-label" htmlFor="eu-org">
              Organización asignada
            </label>
            <select
              id="eu-org"
              className="select"
              disabled={editUserForm.role === 'GLOBAL_ADMIN'}
              value={editUserForm.role === 'GLOBAL_ADMIN' ? '' : editUserForm.org_id}
              onChange={(e) =>
                setEditUserForm((prev) => ({ ...prev, org_id: e.target.value }))
              }
            >
              <option value="">
                {editUserForm.role === 'GLOBAL_ADMIN'
                  ? 'Plataforma global'
                  : 'Selecciona una organización...'}
              </option>
              {organizations.map((o) => (
                <option key={o.org_id} value={o.org_id}>
                  {o.nombre || o.org_name || o.org_id} ({o.org_id})
                </option>
              ))}
            </select>
          </div>

          <div className="form-field">
            <label className="form-label" htmlFor="eu-active">
              Estado
            </label>
            <select
              id="eu-active"
              className="select"
              value={editUserForm.is_active ? 'true' : 'false'}
              onChange={(e) =>
                setEditUserForm((prev) => ({
                  ...prev,
                  is_active: e.target.value === 'true',
                }))
              }
            >
              <option value="true">Activo</option>
              <option value="false">Inactivo</option>
            </select>
          </div>

          <div className="form-field form-field--full">
            <label className="form-label" htmlFor="eu-password">
              Resetear contraseña (dejar vacío para mantener la actual)
            </label>
            <input
              id="eu-password"
              type="password"
              className="input"
              placeholder="Mínimo 10 caracteres si deseas cambiarla"
              value={editUserForm.password}
              onChange={(e) =>
                setEditUserForm((prev) => ({ ...prev, password: e.target.value }))
              }
            />
          </div>
        </form>
      </Modal>
    </div>
  );
}
