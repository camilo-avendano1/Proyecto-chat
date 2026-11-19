import React from 'react';
import {
  LayoutDashboard,
  MapPin,
  FileText,
  ShieldCheck,
  FileSpreadsheet,
  Building2,
  X,
} from 'lucide-react';
import { formatRoleLabel } from '../utils/labels';

export default function Sidebar({
  activePage,
  onNavigate,
  user,
  siteLabels = { singular: 'Sede', plural: 'Sedes' },
  mobileOpen,
  onCloseMobile,
}) {
  const isGlobalAdmin = user?.role === 'GLOBAL_ADMIN';

  const navItems = [
    { id: 'overview', label: 'Resumen', icon: LayoutDashboard },
    { id: 'sites', label: siteLabels.plural || 'Sedes', icon: MapPin },
    { id: 'documents', label: 'Documentos', icon: FileText },
    { id: 'audit', label: 'Historial y Seguridad', icon: ShieldCheck },
    { id: 'reports', label: 'Reportes y Descargas', icon: FileSpreadsheet },
  ];

  function handleSelect(pageId) {
    onNavigate(pageId);
    if (onCloseMobile) onCloseMobile();
  }

  const orgDisplay = user?.org_name || user?.org_id || 'Acceso Global';

  return (
    <>
      {mobileOpen ? <div className="sidebar-backdrop" onClick={onCloseMobile} /> : null}
      <aside className={`sidebar ${mobileOpen ? 'sidebar--open' : ''}`}>
        <div className="sidebar-brand">
          <div className="brand-mark">
            <div className="brand-icon">
              <LayoutDashboard size={18} />
            </div>
            <div>
              <div className="brand-title">Consola Admin</div>
              <div className="brand-sub">Métricas y Documentos</div>
            </div>
          </div>
          {mobileOpen ? (
            <button
              type="button"
              className="btn btn-sm btn-icon"
              onClick={onCloseMobile}
              aria-label="Cerrar menú"
            >
              <X size={16} />
            </button>
          ) : null}
        </div>

        <nav className="sidebar-nav" aria-label="Navegación principal">
          <div className="nav-section-label">Operación y Analítica</div>
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = activePage === item.id;
            return (
              <button
                key={item.id}
                type="button"
                className={`nav-item ${isActive ? 'nav-item--active' : ''}`}
                onClick={() => handleSelect(item.id)}
              >
                <Icon size={17} />
                <span>{item.label}</span>
              </button>
            );
          })}

          {isGlobalAdmin ? (
            <>
              <div className="nav-section-label" style={{ marginTop: 10 }}>
                Plataforma
              </div>
              <button
                type="button"
                className={`nav-item ${activePage === 'organizations' ? 'nav-item--active' : ''}`}
                onClick={() => handleSelect('organizations')}
              >
                <Building2 size={17} />
                <span>Organizaciones y Accesos</span>
              </button>
            </>
          ) : null}
        </nav>

        <div className="sidebar-footer">
          <div className="user-card">
            <div className="user-card-row">
              <span className="user-name" title={user?.full_name || user?.username}>
                {user?.full_name || user?.username || 'Administrador'}
              </span>
              <span className={`badge ${isGlobalAdmin ? 'badge--violet' : 'badge--blue'}`}>
                {formatRoleLabel(user?.role)}
              </span>
            </div>
            <div className="user-meta">
              <span className="mono">{user?.username}</span>
              {` • ${orgDisplay}`}
            </div>
          </div>
        </div>
      </aside>
    </>
  );
}
