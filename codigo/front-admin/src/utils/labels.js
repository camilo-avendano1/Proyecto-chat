/**
 * Utilidades de etiquetas amigables y personalizables por organización.
 * Permite adaptar la consola a distintos sectores (Sedes, IPS, Tiendas, Talleres, etc.).
 */

export const SITE_LABEL_PRESETS = [
  { singular: 'Sede', plural: 'Sedes' },
  { singular: 'IPS', plural: 'IPS' },
  { singular: 'Tienda', plural: 'Tiendas' },
  { singular: 'Taller', plural: 'Talleres' },
  { singular: 'Sucursal', plural: 'Sucursales' },
  { singular: 'Clínica', plural: 'Clínicas' },
];

export function resolveSiteLabels(source) {
  return {
    singular: source?.site_label?.trim() || 'Sede',
    plural: source?.site_label_plural?.trim() || 'Sedes',
  };
}

export function formatRoleLabel(role) {
  const normalized = String(role || '').toUpperCase();
  if (normalized === 'GLOBAL_ADMIN') return 'Admin Global';
  if (normalized === 'ORG_ADMIN') return 'Administrador';
  return role || 'Administrador';
}

export function formatScopeLabel(scope, siteLabel = 'Sede') {
  const normalized = String(scope || '').toUpperCase();
  if (normalized === 'SITE') return `Solo esta ${siteLabel}`;
  if (normalized === 'ORGANIZATION') return 'Toda la organización';
  if (normalized === 'GLOBAL') return 'Plataforma global';
  return scope || `Solo esta ${siteLabel}`;
}
