import React from 'react';
import { RefreshCw, KeyRound, LogOut, Lock, Menu } from 'lucide-react';

const TIME_RANGES = [
  { id: '7d', label: '7d' },
  { id: '30d', label: '30d' },
  { id: '90d', label: '90d' },
  { id: 'all', label: 'Todo' },
];

function HealthPill({ label, status }) {
  const dotClass =
    status === undefined
      ? 'health-dot--checking'
      : status?.online
      ? 'health-dot--ok'
      : 'health-dot--down';
  const titleText =
    status === undefined
      ? `${label}: verificando...`
      : status?.online
      ? `${label}: En línea (${status.latencyMs ?? 0} ms)`
      : `${label}: Sin conexión (${status.error || 'offline'})`;

  return (
    <span className="health-pill" title={titleText}>
      <span className={`health-dot ${dotClass}`} />
      <span>{label}</span>
    </span>
  );
}

export default function Topbar({
  user,
  organizations = [],
  sites = [],
  siteLabels = { singular: 'Sede', plural: 'Sedes' },
  filters,
  onChangeFilters,
  onRefresh,
  refreshing,
  health,
  onOpenChangePassword,
  onLogout,
  onOpenMobileMenu,
}) {
  const isGlobalAdmin = user?.role === 'GLOBAL_ADMIN';

  const currentOrgObj = organizations.find(
    (o) => o.org_id === (isGlobalAdmin ? filters.orgId : user?.org_id)
  );

  const scopedSites =
    isGlobalAdmin && filters.orgId
      ? sites.filter((s) => s.org_id === filters.orgId)
      : sites;

  return (
    <header className="topbar">
      <div className="topbar-left">
        <button
          type="button"
          className="btn btn-icon mobile-menu-btn"
          onClick={onOpenMobileMenu}
          aria-label="Abrir menú"
        >
          <Menu size={17} />
        </button>

        {isGlobalAdmin ? (
          <div className="filter-group">
            <label className="filter-label" htmlFor="filter-org">
              Organización:
            </label>
            <select
              id="filter-org"
              className="topbar-select"
              value={filters.orgId}
              onChange={(e) =>
                onChangeFilters({
                  ...filters,
                  orgId: e.target.value,
                  siteId: '',
                })
              }
            >
              <option value="">Todas las Organizaciones</option>
              {organizations.map((o) => (
                <option key={o.org_id} value={o.org_id}>
                  {o.nombre || o.org_name || o.org_id} ({o.org_id})
                </option>
              ))}
            </select>
          </div>
        ) : (
          <span
            className="badge badge--blue"
            style={{ height: 32, padding: '0 10px', fontSize: 12 }}
            title="Aislamiento estricto por organización"
          >
            <Lock size={12} />
            <span>
              Organización:{' '}
              {currentOrgObj?.nombre ||
                currentOrgObj?.org_name ||
                user?.org_name ||
                user?.org_id ||
                'Asignada'}
            </span>
          </span>
        )}

        <div className="filter-group">
          <label className="filter-label" htmlFor="filter-site">
            {siteLabels.singular}:
          </label>
          <select
            id="filter-site"
            className="topbar-select"
            value={filters.siteId}
            onChange={(e) =>
              onChangeFilters({
                ...filters,
                siteId: e.target.value,
              })
            }
          >
            <option value="">Todas las {siteLabels.plural}</option>
            {scopedSites.map((s) => (
              <option key={s.site_id} value={s.site_id}>
                {s.nombre || s.site_name || s.site_id} {s.site_code ? `(${s.site_code})` : ''}
              </option>
            ))}
          </select>
        </div>

        <div className="segmented" role="group" aria-label="Rango de tiempo">
          {TIME_RANGES.map((range) => (
            <button
              key={range.id}
              type="button"
              className={`segmented-btn ${
                filters.timeRange === range.id ? 'segmented-btn--active' : ''
              }`}
              onClick={() =>
                onChangeFilters({
                  ...filters,
                  timeRange: range.id,
                })
              }
            >
              {range.label}
            </button>
          ))}
        </div>
      </div>

      <div className="topbar-right">
        <div className="health-group" aria-label="Estado de servicios">
          <HealthPill label="Auth" status={health?.auth} />
          <HealthPill label="Chat" status={health?.chat} />
          <HealthPill label="Gateway" status={health?.gateway} />
        </div>

        <button
          type="button"
          className="btn"
          onClick={onRefresh}
          disabled={refreshing}
          title="Actualizar métricas y estado de servicios"
        >
          <RefreshCw size={14} className={refreshing ? 'spin' : ''} />
          <span>Actualizar</span>
        </button>

        <button
          type="button"
          className="btn"
          onClick={onOpenChangePassword}
          title="Cambiar contraseña de administrador"
        >
          <KeyRound size={14} />
          <span>Clave</span>
        </button>

        <button
          type="button"
          className="btn"
          onClick={onLogout}
          title="Cerrar sesión"
        >
          <LogOut size={14} />
          <span>Salir</span>
        </button>
      </div>
    </header>
  );
}
