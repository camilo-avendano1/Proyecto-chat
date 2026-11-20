import React, { useState } from 'react';
import { Eye, EyeOff, Lock, ShieldCheck, AlertCircle } from 'lucide-react';
import { loginAdmin } from '../services/api';

function resolveLoginError(err) {
  if (!err) return 'Error inesperado al iniciar sesión.';
  if (err.status === 401) {
    return 'Credenciales inválidas. Verifica tu usuario y contraseña.';
  }
  if (err.status === 423) {
    return (
      err.message ||
      'Cuenta bloqueada temporalmente por múltiples intentos fallidos. Espera unos minutos o contacta al Admin Global.'
    );
  }
  if (err.status === 403) {
    return err.message || 'Acceso denegado. Verifica que la cuenta administrativa esté activa.';
  }
  if (err.status === 0) {
    return 'No se pudo conectar con el servicio de autenticación. Verifica que esté en ejecución.';
  }
  return err.message || 'No fue posible iniciar sesión.';
}

export default function LoginView({ initialNotice = '', onLoginSuccess }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');

  async function handleSubmit(e) {
    e.preventDefault();
    const cleanUser = username.trim();
    if (!cleanUser || !password) {
      setErrorMessage('Ingresa usuario y contraseña para continuar.');
      return;
    }

    setSubmitting(true);
    setErrorMessage('');
    try {
      const session = await loginAdmin(cleanUser, password);
      onLoginSuccess(session);
    } catch (err) {
      setErrorMessage(resolveLoginError(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="login-page">
      <div className="login-card">
        <div className="brand-mark">
          <div className="brand-icon">
            <ShieldCheck size={19} />
          </div>
          <div>
            <div className="brand-title">Atenta</div>
            <div className="brand-sub">Consola de Administración · Métricas, sedes y documentos</div>
          </div>
        </div>

        {initialNotice ? (
          <div className="alert alert--warning" role="status">
            <span>{initialNotice}</span>
          </div>
        ) : null}

        {errorMessage ? (
          <div className="alert alert--error" role="alert">
            <span style={{ display: 'flex', alignItems: 'flex-start', gap: 8 }}>
              <AlertCircle size={16} style={{ flexShrink: 0, marginTop: 2 }} />
              <span>{errorMessage}</span>
            </span>
          </div>
        ) : null}

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div className="form-field">
            <label className="form-label" htmlFor="admin-username">
              Usuario administrativo
            </label>
            <input
              id="admin-username"
              type="text"
              className="input"
              autoComplete="username"
              placeholder="ej. admin.empresa"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              disabled={submitting}
              autoFocus
            />
          </div>

          <div className="form-field">
            <label className="form-label" htmlFor="admin-password">
              Contraseña
            </label>
            <div style={{ position: 'relative' }}>
              <input
                id="admin-password"
                type={showPassword ? 'text' : 'password'}
                className="input"
                autoComplete="current-password"
                placeholder="••••••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                disabled={submitting}
                style={{ paddingRight: 40 }}
              />
              <button
                type="button"
                onClick={() => setShowPassword((prev) => !prev)}
                aria-label={showPassword ? 'Ocultar contraseña' : 'Ver contraseña'}
                style={{
                  position: 'absolute',
                  right: 8,
                  top: '50%',
                  transform: 'translateY(-50%)',
                  border: 'none',
                  background: 'transparent',
                  cursor: 'pointer',
                  color: 'var(--text-muted)',
                  padding: 4,
                  display: 'grid',
                  placeItems: 'center',
                }}
              >
                {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
          </div>

          <button
            type="submit"
            className="btn btn-primary"
            disabled={submitting}
            style={{ height: 40, marginTop: 4 }}
          >
            <Lock size={15} />
            {submitting ? 'Verificando acceso...' : 'Ingresar a la Consola'}
          </button>
        </form>

        <div
          style={{
            borderTop: '1px solid var(--border)',
            paddingTop: 12,
            fontSize: 12,
            color: 'var(--text-muted)',
          }}
        >
          Acceso protegido para perfiles <strong>Admin Global</strong> y{' '}
          <strong>Administrador</strong> de organización.
        </div>
      </div>
    </div>
  );
}
