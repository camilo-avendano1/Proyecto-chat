/**
 * Client API Service for SaaS Core Microservices
 * Communicates with:
 * - Auth Service:      http://localhost:8002
 * - LLM Gateway:       http://localhost:8003
 * - Back Central Chat: http://localhost:8000
 */

export const AUTH_SERVICE_URL = 'http://localhost:8002';
export const LLM_GATEWAY_URL = 'http://localhost:8003';
export const API_BASE_URL = 'http://localhost:8000';

export async function fetchHealth() {
  try {
    const res = await fetch(`${API_BASE_URL}/health`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (err) {
    return { status: 'error', error: err.message };
  }
}

export async function fetchSystemStatus() {
  try {
    const res = await fetch(`${API_BASE_URL}/api/v1/status`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (err) {
    return { status: 'error', error: err.message };
  }
}

/**
 * Initializes widget session.
 * Tries Auth Service (:8002) first, falling back to Back Central proxy (:8000).
 */
export async function createSession({ clientId, origin, epsId, ipsCode, apiKey }) {
  const payload = {
    client_id: clientId,
    origin: origin || window.location.origin,
    eps_id: epsId,
    ips_code: ipsCode,
  };

  try {
    const res = await fetch(`${AUTH_SERVICE_URL}/api/v1/widget/session`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Widget-Key': apiKey,
      },
      body: JSON.stringify(payload),
    });
    if (res.ok) {
      return await res.json();
    }
  } catch (err) {
    console.warn('Auth Service (:8002) no alcanzable directamente, intentando via Gateway (:8000):', err);
  }

  const fallbackRes = await fetch(`${API_BASE_URL}/api/v1/widget/session`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Widget-Key': apiKey,
    },
    body: JSON.stringify(payload),
  });

  if (!fallbackRes.ok) {
    const errorData = await fallbackRes.json().catch(() => ({ detail: `Error HTTP ${fallbackRes.status}` }));
    throw new Error(errorData.detail || `Error al inicializar sesión (${fallbackRes.status})`);
  }

  return await fallbackRes.json();
}

/**
 * Diagnostic in streaming mode using SSE (Server-Sent Events)
 */
export async function streamDiagnostic({
  token,
  payload,
  onChunk,
  onErrorDiagnostic,
  onSources,
  onDone,
  onError,
  onRawEvent,
}) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/v1/diagnostic/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
        'Accept': 'text/event-stream',
      },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      const errJson = await response.json().catch(() => ({ detail: `Error ${response.status}` }));
      throw new Error(errJson.detail || `Error en streaming (${response.status})`);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder('utf-8');
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      let currentEvent = 'message';

      for (let i = 0; i < lines.length; i++) {
        const line = lines[i].trim();
        if (!line) continue;

        if (line.startsWith('event: ')) {
          currentEvent = line.replace('event: ', '').trim();
        } else if (line.startsWith('data: ')) {
          const rawData = line.replace('data: ', '').trim();
          
          if (onRawEvent) {
            onRawEvent({ event: currentEvent, data: rawData });
          }

          try {
            const parsed = JSON.parse(rawData);

            if (currentEvent === 'chunk' && onChunk) {
              onChunk(parsed.text || '');
            } else if (currentEvent === 'error_diagnostic' && onErrorDiagnostic) {
              onErrorDiagnostic(parsed);
            } else if (currentEvent === 'sources' && onSources) {
              onSources(parsed);
            } else if (currentEvent === 'done' && onDone) {
              onDone(parsed);
            } else if (currentEvent === 'error' && onError) {
              onError(parsed.error || 'Error reportado por el servidor');
            }
          } catch (e) {
            if (currentEvent === 'chunk' && onChunk) {
              onChunk(rawData);
            }
          }
        }
      }
    }
  } catch (error) {
    if (onError) onError(error.message);
    else throw error;
  }
}

/**
 * Diagnostic in synchronous mode (returns consolidated JSON)
 */
export async function queryDiagnostic({ token, payload }) {
  const res = await fetch(`${API_BASE_URL}/api/v1/diagnostic/query`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`,
    },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({ detail: `Error HTTP ${res.status}` }));
    throw new Error(errorData.detail || `Error al procesar consulta (${res.status})`);
  }

  return await res.json();
}

/**
 * Administrator Authentication via Auth Service (:8002)
 */
export async function adminLogin({ username, password }) {
  const res = await fetch(`${AUTH_SERVICE_URL}/api/v1/admin/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  });
  if (!res.ok) {
    const errData = await res.json().catch(() => ({ detail: `Error ${res.status}` }));
    throw new Error(errData.detail || 'Credenciales de administrador inválidas');
  }
  return await res.json();
}

/**
 * Central Audit Logs queries
 */
export async function fetchAdminSecurityLogs({ token, clientId, limit = 50 }) {
  const url = new URL(`${API_BASE_URL}/api/v1/admin/logs/security`);
  if (clientId) url.searchParams.set('client_id', clientId);
  url.searchParams.set('limit', limit);
  const res = await fetch(url.toString(), {
    headers: { 'Authorization': `Bearer ${token}` }
  });
  if (!res.ok) throw new Error('Error al consultar logs de seguridad');
  return await res.json();
}

export async function fetchAdminMessageLogs({ token, clientId, limit = 50 }) {
  const url = new URL(`${API_BASE_URL}/api/v1/admin/logs/messages`);
  if (clientId) url.searchParams.set('client_id', clientId);
  url.searchParams.set('limit', limit);
  const res = await fetch(url.toString(), {
    headers: { 'Authorization': `Bearer ${token}` }
  });
  if (!res.ok) throw new Error('Error al consultar trazas de mensajes');
  return await res.json();
}

/**
 * Segmented Usage Metrics queries (Caller attribution & models)
 */
export async function fetchAdminUsageSummary({ token, clientId }) {
  const url = new URL(`${API_BASE_URL}/api/v1/admin/usage/summary`);
  if (clientId) url.searchParams.set('client_id', clientId);
  const res = await fetch(url.toString(), {
    headers: { 'Authorization': `Bearer ${token}` }
  });
  if (!res.ok) throw new Error('Error al consultar resumen de métricas');
  return await res.json();
}

export async function fetchAdminUsageByUser({ token, clientId }) {
  const url = new URL(`${API_BASE_URL}/api/v1/admin/usage/by-user`);
  if (clientId) url.searchParams.set('client_id', clientId);
  const res = await fetch(url.toString(), {
    headers: { 'Authorization': `Bearer ${token}` }
  });
  if (!res.ok) throw new Error('Error al consultar consumo por usuario');
  return await res.json();
}

export async function fetchAdminUsageByTenant({ token, clientId }) {
  const url = new URL(`${API_BASE_URL}/api/v1/admin/usage/by-tenant`);
  if (clientId) url.searchParams.set('client_id', clientId);
  const res = await fetch(url.toString(), {
    headers: { 'Authorization': `Bearer ${token}` }
  });
  if (!res.ok) throw new Error('Error al consultar consumo por división/tenant');
  return await res.json();
}

export async function fetchAdminUsageByRole({ token, clientId }) {
  const url = new URL(`${API_BASE_URL}/api/v1/admin/usage/by-role`);
  if (clientId) url.searchParams.set('client_id', clientId);
  const res = await fetch(url.toString(), {
    headers: { 'Authorization': `Bearer ${token}` }
  });
  if (!res.ok) throw new Error('Error al consultar consumo por rol');
  return await res.json();
}

export async function fetchAdminUsageByModel({ token, clientId }) {
  const url = new URL(`${API_BASE_URL}/api/v1/admin/usage/by-model`);
  if (clientId) url.searchParams.set('client_id', clientId);
  const res = await fetch(url.toString(), {
    headers: { 'Authorization': `Bearer ${token}` }
  });
  if (!res.ok) throw new Error('Error al consultar consumo por modelo');
  return await res.json();
}

// Fallback legacy endpoints (in-memory ring buffer)
export async function fetchUsageSummary() {
  const res = await fetch(`${API_BASE_URL}/api/v1/usage`);
  if (!res.ok) throw new Error('Error al obtener métricas de consumo');
  return await res.json();
}

export async function fetchUsageByUser() {
  const res = await fetch(`${API_BASE_URL}/api/v1/usage/by-user`);
  if (!res.ok) throw new Error('Error al obtener consumo por usuario');
  return await res.json();
}

export async function fetchSecurityLogs() {
  const res = await fetch(`${API_BASE_URL}/api/v1/usage/security-logs?limit=50`);
  if (!res.ok) throw new Error('Error al obtener logs de seguridad');
  return await res.json();
}

export async function fetchMessageLogs() {
  const res = await fetch(`${API_BASE_URL}/api/v1/usage/message-logs?limit=50`);
  if (!res.ok) throw new Error('Error al obtener logs de mensajes');
  return await res.json();
}
