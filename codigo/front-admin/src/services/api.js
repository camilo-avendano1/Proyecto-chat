/**
 * Cliente API autenticado para la Consola Administrativa de Atenta.
 * Consume auth-service (:8002), back-chat (:8000) y llm-gateway (:8003).
 */

const AUTH_BASE = (import.meta.env.VITE_AUTH_SERVICE_URL || '/api/auth').replace(/\/$/, '');
const CHAT_BASE = (import.meta.env.VITE_BACK_CHAT_URL || '/api/chat').replace(/\/$/, '');
const GATEWAY_BASE = (import.meta.env.VITE_LLM_GATEWAY_URL || '/api/gateway').replace(/\/$/, '');

const STORAGE_TOKEN_KEY = 'saas_admin_token';
const STORAGE_USER_KEY = 'saas_admin_user';
const STORAGE_EXPIRES_KEY = 'saas_admin_expires_at';

let unauthorizedCallback = null;

export function setUnauthorizedHandler(handler) {
  unauthorizedCallback = typeof handler === 'function' ? handler : null;
}

export function getStoredToken() {
  try {
    return sessionStorage.getItem(STORAGE_TOKEN_KEY) || '';
  } catch {
    return '';
  }
}

export function getStoredSession() {
  try {
    const token = sessionStorage.getItem(STORAGE_TOKEN_KEY);
    const rawUser = sessionStorage.getItem(STORAGE_USER_KEY);
    const expiresAtRaw = sessionStorage.getItem(STORAGE_EXPIRES_KEY);
    if (!token || !rawUser) return null;
    const expiresAt = expiresAtRaw ? Number(expiresAtRaw) : 0;
    if (expiresAt && Date.now() > expiresAt) {
      clearStoredSession();
      return null;
    }
    const user = JSON.parse(rawUser);
    return {
      token,
      user,
      expiresAt,
    };
  } catch {
    return null;
  }
}

export function setStoredSession(token, user, expiresInSeconds) {
  try {
    sessionStorage.setItem(STORAGE_TOKEN_KEY, token);
    sessionStorage.setItem(STORAGE_USER_KEY, JSON.stringify(user));
    if (expiresInSeconds) {
      sessionStorage.setItem(
        STORAGE_EXPIRES_KEY,
        String(Date.now() + Number(expiresInSeconds) * 1000)
      );
    }
  } catch {
    // Ignorar errores de almacenamiento si el navegador restringe sessionStorage
  }
}

export function updateStoredUser(user) {
  try {
    if (user) {
      sessionStorage.setItem(STORAGE_USER_KEY, JSON.stringify(user));
    }
  } catch {
    // noop
  }
}

export function clearStoredSession() {
  try {
    sessionStorage.removeItem(STORAGE_TOKEN_KEY);
    sessionStorage.removeItem(STORAGE_USER_KEY);
    sessionStorage.removeItem(STORAGE_EXPIRES_KEY);
  } catch {
    // noop
  }
}

export class ApiError extends Error {
  constructor(message, status, payload = null) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.payload = payload;
  }
}

function buildQuery(params = {}) {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === null || value === '' || value === 'ALL') return;
    search.set(key, String(value));
  });
  const qs = search.toString();
  return qs ? `?${qs}` : '';
}

function parseErrorDetail(payload, status, fallbackText) {
  if (payload) {
    if (typeof payload.detail === 'string' && payload.detail.trim()) {
      return payload.detail;
    }
    if (Array.isArray(payload.detail) && payload.detail.length > 0) {
      return payload.detail
        .map((item) => {
          const loc = Array.isArray(item.loc) ? item.loc.slice(1).join('.') : '';
          return loc ? `${loc}: ${item.msg}` : item.msg || JSON.stringify(item);
        })
        .join(' | ');
    }
    if (typeof payload.message === 'string' && payload.message.trim()) {
      return payload.message;
    }
  }
  if (fallbackText && fallbackText.trim()) return fallbackText;
  return `Error HTTP ${status}`;
}

async function apiRequest(baseUrl, path, options = {}) {
  const {
    method = 'GET',
    params,
    body,
    skipAuth = false,
    triggerUnauthorized = true,
    timeoutMs = 20000,
  } = options;

  const url = `${baseUrl}${path}${buildQuery(params)}`;
  const headers = new Headers(options.headers || {});
  if (body !== undefined && !(body instanceof FormData)) {
    headers.set('Content-Type', 'application/json');
  }

  if (!skipAuth) {
    const token = getStoredToken();
    if (token) {
      headers.set('Authorization', `Bearer ${token}`);
    }
  }

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  let response;
  try {
    response = await fetch(url, {
      method,
      headers,
      body:
        body === undefined
          ? undefined
          : body instanceof FormData
          ? body
          : JSON.stringify(body),
      signal: controller.signal,
    });
  } catch (err) {
    clearTimeout(timer);
    if (err.name === 'AbortError') {
      throw new ApiError('Tiempo de espera agotado al conectar con el servidor.', 504);
    }
    throw new ApiError('No hay conexión con el servicio solicitado.', 0);
  } finally {
    clearTimeout(timer);
  }

  const contentType = response.headers.get('content-type') || '';
  let payload = null;
  let rawText = '';

  if (response.status !== 204) {
    if (contentType.includes('application/json')) {
      try {
        payload = await response.json();
      } catch {
        payload = null;
      }
    } else {
      try {
        rawText = await response.text();
        if (rawText && (rawText.startsWith('{') || rawText.startsWith('['))) {
          payload = JSON.parse(rawText);
        }
      } catch {
        payload = null;
      }
    }
  }

  if (!response.ok) {
    if (response.status === 401 && !skipAuth && triggerUnauthorized) {
      clearStoredSession();
      if (unauthorizedCallback) {
        unauthorizedCallback('Tu sesión administrativa expiró o no es válida. Inicia sesión nuevamente.');
      }
    }
    const msg = parseErrorDetail(payload, response.status, rawText);
    throw new ApiError(msg, response.status, payload);
  }

  return payload;
}

export function buildUsageFilterParams(filters = {}) {
  const params = {};
  if (filters.orgId) params.org_id = filters.orgId;
  if (filters.siteId) params.site_id = filters.siteId;
  if (filters.timeRange && filters.timeRange !== 'all') {
    const daysMap = { '7d': 7, '30d': 30, '90d': 90 };
    if (daysMap[filters.timeRange]) {
      params.days = daysMap[filters.timeRange];
    }
  }
  if (filters.dateFrom) params.date_from = filters.dateFrom;
  if (filters.dateTo) params.date_to = filters.dateTo;
  return params;
}

// ---------------------------------------------------------------------------
// Auth Service (:8002)
// ---------------------------------------------------------------------------

export async function loginAdmin(username, password) {
  const data = await apiRequest(AUTH_BASE, '/api/v1/admin/auth/login', {
    method: 'POST',
    body: { username, password },
    skipAuth: true,
    triggerUnauthorized: false,
  });
  const user = {
    admin_id: data.admin_id,
    username: data.username,
    full_name: data.full_name || null,
    role: data.role,
    org_id: data.org_id || null,
    org_name: data.org_name || null,
    site_label: data.site_label || 'Sede',
    site_label_plural: data.site_label_plural || 'Sedes',
  };
  setStoredSession(data.access_token, user, data.expires_in_seconds);
  return { token: data.access_token, user, raw: data };
}

export function fetchAdminMe() {
  return apiRequest(AUTH_BASE, '/api/v1/admin/auth/me');
}

export function changeAdminPassword(currentPassword, newPassword) {
  return apiRequest(AUTH_BASE, '/api/v1/admin/auth/change-password', {
    method: 'POST',
    body: {
      current_password: currentPassword,
      new_password: newPassword,
    },
  });
}

export function fetchAdminUsers() {
  return apiRequest(AUTH_BASE, '/api/v1/admin/users');
}

export function createAdminUser(payload) {
  return apiRequest(AUTH_BASE, '/api/v1/admin/users', {
    method: 'POST',
    body: payload,
  });
}

export function updateAdminUser(adminId, payload) {
  return apiRequest(AUTH_BASE, `/api/v1/admin/users/${encodeURIComponent(adminId)}`, {
    method: 'PATCH',
    body: payload,
  });
}

export function fetchOrganizations() {
  return apiRequest(AUTH_BASE, '/api/v1/admin/organizations');
}

export function createOrganization(payload) {
  return apiRequest(AUTH_BASE, '/api/v1/admin/organizations', {
    method: 'POST',
    body: payload,
  });
}

export function updateOrganization(orgId, payload) {
  return apiRequest(AUTH_BASE, `/api/v1/admin/organizations/${encodeURIComponent(orgId)}`, {
    method: 'PATCH',
    body: payload,
  });
}

export function fetchSites(orgId) {
  return apiRequest(AUTH_BASE, '/api/v1/admin/sites', {
    params: orgId ? { org_id: orgId } : undefined,
  });
}

export function createSite(payload) {
  return apiRequest(AUTH_BASE, '/api/v1/admin/sites', {
    method: 'POST',
    body: payload,
  });
}

export function updateSite(siteId, payload) {
  return apiRequest(AUTH_BASE, `/api/v1/admin/sites/${encodeURIComponent(siteId)}`, {
    method: 'PATCH',
    body: payload,
  });
}

// ---------------------------------------------------------------------------
// Back-Chat Observability, Usage & Assistant Documents (:8000)
// ---------------------------------------------------------------------------

export function fetchUsageSummary(filters) {
  return apiRequest(CHAT_BASE, '/api/v1/admin/usage/summary', {
    params: buildUsageFilterParams(filters),
  });
}

export function fetchUsageTimeseries(filters) {
  return apiRequest(CHAT_BASE, '/api/v1/admin/usage/timeseries', {
    params: buildUsageFilterParams(filters),
  });
}

export function fetchUsageBySite(filters) {
  return apiRequest(CHAT_BASE, '/api/v1/admin/usage/by-site', {
    params: buildUsageFilterParams(filters),
  });
}

export function fetchUsageByUser(filters) {
  return apiRequest(CHAT_BASE, '/api/v1/admin/usage/by-user', {
    params: buildUsageFilterParams(filters),
  });
}

export function fetchUsageByRole(filters) {
  return apiRequest(CHAT_BASE, '/api/v1/admin/usage/by-role', {
    params: buildUsageFilterParams(filters),
  });
}

export function fetchUsageByModel(filters) {
  return apiRequest(CHAT_BASE, '/api/v1/admin/usage/by-model', {
    params: buildUsageFilterParams(filters),
  });
}

export function fetchUsageRecords(params = {}) {
  return apiRequest(CHAT_BASE, '/api/v1/admin/usage/records', { params });
}

export function fetchMessageLogs(params = {}) {
  return apiRequest(CHAT_BASE, '/api/v1/admin/logs/messages', { params });
}

export function fetchSecurityLogs(params = {}) {
  return apiRequest(CHAT_BASE, '/api/v1/admin/logs/security', { params });
}

export function fetchSystemErrorLogs(params = {}) {
  return apiRequest(CHAT_BASE, '/api/v1/admin/logs/system-errors', { params });
}

export function fetchDocuments(params = {}) {
  return apiRequest(CHAT_BASE, '/api/v1/admin/documents', { params });
}

export function uploadDocument(payload) {
  return apiRequest(CHAT_BASE, '/api/v1/admin/documents', {
    method: 'POST',
    body: payload,
    timeoutMs: 45000,
  });
}

export function fetchDocumentChunks(docId) {
  return apiRequest(CHAT_BASE, `/api/v1/admin/documents/${encodeURIComponent(docId)}/chunks`);
}

export function syncDocumentVector(docId) {
  return apiRequest(CHAT_BASE, `/api/v1/admin/documents/${encodeURIComponent(docId)}/sync`, {
    method: 'POST',
    timeoutMs: 30000,
  });
}

export function deleteDocument(docId) {
  return apiRequest(CHAT_BASE, `/api/v1/admin/documents/${encodeURIComponent(docId)}`, {
    method: 'DELETE',
  });
}

// ---------------------------------------------------------------------------
// Health Checks
// ---------------------------------------------------------------------------

async function pingEndpoint(baseUrl, path) {
  const started = performance.now();
  try {
    const data = await apiRequest(baseUrl, path, {
      skipAuth: true,
      triggerUnauthorized: false,
      timeoutMs: 4000,
    });
    return {
      online: true,
      latencyMs: Math.round(performance.now() - started),
      data,
    };
  } catch (err) {
    return {
      online: false,
      latencyMs: Math.round(performance.now() - started),
      error: err.message,
    };
  }
}

export async function checkServicesHealth() {
  const [auth, chat, gateway] = await Promise.all([
    pingEndpoint(AUTH_BASE, '/health'),
    pingEndpoint(CHAT_BASE, '/health'),
    pingEndpoint(GATEWAY_BASE, '/health'),
  ]);
  return { auth, chat, gateway };
}

// ---------------------------------------------------------------------------
// Helpers de normalización de respuestas heterogéneas
// ---------------------------------------------------------------------------

export function extractArray(data, fallbackKeys = ['records', 'items', 'data', 'results']) {
  if (Array.isArray(data)) return data;
  if (data && typeof data === 'object') {
    for (const key of fallbackKeys) {
      if (Array.isArray(data[key])) return data[key];
    }
  }
  return [];
}

export function normalizeTimeseries(raw) {
  const list = extractArray(raw, ['points', 'series', 'records', 'items', 'data']);
  return list.map((pt) => {
    const dateVal = pt.date || pt.day || pt.period || pt.fecha || '';
    const tokensIn = Number(pt.tokens_input ?? pt.total_tokens_input ?? 0);
    const tokensOut = Number(pt.tokens_output ?? pt.total_tokens_output ?? 0);
    const totalTokens = Number(pt.total_tokens ?? pt.tokens_total ?? tokensIn + tokensOut);
    const llmCalls = Number(pt.llm_requests ?? pt.llm_calls ?? 0);
    const fastPathCalls = Number(
      pt.fast_path_requests ?? pt.fast_path_calls ?? pt.direct_requests ?? pt.saved_fast_path_calls ?? 0
    );
    const totalRequests = Number(
      pt.total_requests ?? pt.requests ?? pt.total_records ?? llmCalls + fastPathCalls
    );
    const costUsd = Number(pt.total_cost_usd ?? pt.cost_usd ?? pt.costo_usd ?? 0);
    return {
      date: dateVal,
      total_requests: totalRequests,
      llm_requests: llmCalls,
      fast_path_requests: fastPathCalls,
      tokens_input: tokensIn,
      tokens_output: tokensOut,
      total_tokens: totalTokens,
      total_cost_usd: costUsd,
    };
  });
}

export function normalizeCountsBySite(rawCounts) {
  const map = {};
  if (!rawCounts) return map;
  if (Array.isArray(rawCounts)) {
    rawCounts.forEach((item) => {
      const id = item.site_id || item.id;
      if (id) map[id] = Number(item.count ?? item.total ?? item.documents ?? 0);
    });
    return map;
  }
  if (typeof rawCounts === 'object') {
    Object.entries(rawCounts).forEach(([k, v]) => {
      map[k] = Number(v ?? 0);
    });
  }
  return map;
}
