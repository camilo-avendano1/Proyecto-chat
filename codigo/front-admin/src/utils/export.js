/**
 * Utilidades de exportación (CSV UTF-8 con BOM, JSON con metadatos)
 * y formateadores numéricos/monetarios/fechas para la Consola Administrativa de Atenta.
 */

function escapeCsvCell(raw) {
  if (raw === null || raw === undefined) return '';
  let str;
  if (typeof raw === 'object') {
    try {
      str = JSON.stringify(raw);
    } catch {
      str = String(raw);
    }
  } else {
    str = String(raw);
  }
  if (/[",\r\n]/.test(str)) {
    return `"${str.replace(/"/g, '""')}"`;
  }
  return str;
}

function triggerDownload(filename, blob) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/**
 * Descarga un arreglo de registros en formato CSV compatible con Microsoft Excel (BOM UTF-8).
 * @param {string} filename
 * @param {Array<string | {key: string, label: string, format?: Function}>} columns
 * @param {Array<Record<string, any>>} rows
 */
export function downloadCSV(filename, columns, rows) {
  const normalizedCols = (columns || []).map((col) =>
    typeof col === 'string' ? { key: col, label: col } : col
  );

  const headerLine = normalizedCols.map((c) => escapeCsvCell(c.label ?? c.key)).join(',');
  const dataLines = (rows || []).map((row) =>
    normalizedCols
      .map((col) => {
        const raw = typeof col.format === 'function' ? col.format(row?.[col.key], row) : row?.[col.key];
        return escapeCsvCell(raw);
      })
      .join(',')
  );

  const csvBody = [headerLine, ...dataLines].join('\r\n');
  const safeName = filename.endsWith('.csv') ? filename : `${filename}.csv`;
  const blob = new Blob(['\uFEFF' + csvBody], { type: 'text/csv;charset=utf-8;' });
  triggerDownload(safeName, blob);
}

/**
 * Descarga datos estructurados en JSON incluyendo metadatos de exportación.
 * @param {string} filename
 * @param {any} data
 * @param {Record<string, any>} [metadata]
 */
export function downloadJSON(filename, data, metadata = {}) {
  const baseMeta = {
    exported_at: new Date().toISOString(),
    source: 'atenta-admin-console',
    ...metadata,
  };

  let payload;
  if (Array.isArray(data)) {
    payload = {
      ...baseMeta,
      total_records: data.length,
      records: data,
    };
  } else if (data && typeof data === 'object') {
    payload = {
      ...baseMeta,
      ...data,
    };
  } else {
    payload = {
      ...baseMeta,
      data,
    };
  }

  const safeName = filename.endsWith('.json') ? filename : `${filename}.json`;
  const blob = new Blob([JSON.stringify(payload, null, 2)], {
    type: 'application/json;charset=utf-8;',
  });
  triggerDownload(safeName, blob);
}

export function formatCurrency(value, decimals) {
  const num = Number(value ?? 0);
  if (!Number.isFinite(num)) return '$0.00';
  const abs = Math.abs(num);
  const maxDigits = decimals !== undefined ? decimals : abs > 0 && abs < 1 ? 4 : 2;
  const minDigits = decimals !== undefined ? decimals : 2;
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: minDigits,
    maximumFractionDigits: Math.max(minDigits, maxDigits),
  }).format(num);
}

export function formatNumber(value, maximumFractionDigits = 0) {
  const num = Number(value ?? 0);
  if (!Number.isFinite(num)) return '0';
  return new Intl.NumberFormat('es-CO', {
    maximumFractionDigits,
  }).format(num);
}

export function formatCompactNumber(value) {
  const num = Number(value ?? 0);
  if (!Number.isFinite(num)) return '0';
  if (Math.abs(num) < 1000) return formatNumber(num);
  return new Intl.NumberFormat('en-US', {
    notation: 'compact',
    maximumFractionDigits: 1,
  }).format(num);
}

export function formatBytes(bytes) {
  const num = Number(bytes ?? 0);
  if (!Number.isFinite(num) || num <= 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  const idx = Math.min(Math.floor(Math.log(num) / Math.log(1024)), units.length - 1);
  const val = num / Math.pow(1024, idx);
  return `${val >= 10 || idx === 0 ? val.toFixed(0) : val.toFixed(1)} ${units[idx]}`;
}

export function formatDateTime(isoString) {
  if (!isoString) return '—';
  const date = new Date(isoString);
  if (Number.isNaN(date.getTime())) return String(isoString);
  return new Intl.DateTimeFormat('es-CO', {
    year: 'numeric',
    month: 'short',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date);
}

export function formatShortDate(dateValue) {
  if (!dateValue) return '';
  if (/^\d{4}-\d{2}-\d{2}$/.test(String(dateValue))) {
    const [y, m, d] = String(dateValue).split('-').map(Number);
    const dt = new Date(y, m - 1, d);
    return new Intl.DateTimeFormat('es-CO', { day: '2-digit', month: 'short' }).format(dt);
  }
  const parsed = new Date(dateValue);
  if (Number.isNaN(parsed.getTime())) return String(dateValue);
  return new Intl.DateTimeFormat('es-CO', { day: '2-digit', month: 'short' }).format(parsed);
}
