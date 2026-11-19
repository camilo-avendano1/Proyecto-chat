import React, { useState } from 'react';
import Modal from './Modal';
import { changeAdminPassword } from '../services/api';

export default function ChangePasswordModal({ open, onClose, onSuccess }) {
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  function resetAndClose() {
    setCurrentPassword('');
    setNewPassword('');
    setConfirmPassword('');
    setError('');
    onClose();
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError('');

    if (!currentPassword) {
      setError('Ingresa tu contraseña actual.');
      return;
    }
    if (newPassword.length < 10 || newPassword.length > 72) {
      setError('La nueva contraseña debe tener entre 10 y 72 caracteres.');
      return;
    }
    if (newPassword !== confirmPassword) {
      setError('La confirmación no coincide con la nueva contraseña.');
      return;
    }

    setSaving(true);
    try {
      await changeAdminPassword(currentPassword, newPassword);
      if (onSuccess) onSuccess('Contraseña actualizada correctamente.');
      resetAndClose();
    } catch (err) {
      setError(err.message || 'No fue posible actualizar la contraseña.');
    } finally {
      setSaving(false);
    }
  }

  return (
    <Modal
      open={open}
      title="Cambiar Contraseña de Administrador"
      onClose={resetAndClose}
      footer={
        <>
          <button type="button" className="btn" onClick={resetAndClose} disabled={saving}>
            Cancelar
          </button>
          <button
            type="submit"
            form="change-password-form"
            className="btn btn-primary"
            disabled={saving}
          >
            {saving ? 'Guardando...' : 'Actualizar Contraseña'}
          </button>
        </>
      }
    >
      {error ? (
        <div className="alert alert--error" role="alert">
          <span>{error}</span>
        </div>
      ) : null}

      <form
        id="change-password-form"
        onSubmit={handleSubmit}
        style={{ display: 'flex', flexDirection: 'column', gap: 12 }}
      >
        <div className="form-field">
          <label className="form-label" htmlFor="cp-current">
            Contraseña actual
          </label>
          <input
            id="cp-current"
            type="password"
            className="input"
            value={currentPassword}
            onChange={(e) => setCurrentPassword(e.target.value)}
            autoComplete="current-password"
          />
        </div>

        <div className="form-field">
          <label className="form-label" htmlFor="cp-new">
            Nueva contraseña (mínimo 10 caracteres)
          </label>
          <input
            id="cp-new"
            type="password"
            className="input"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            autoComplete="new-password"
          />
        </div>

        <div className="form-field">
          <label className="form-label" htmlFor="cp-confirm">
            Confirmar nueva contraseña
          </label>
          <input
            id="cp-confirm"
            type="password"
            className="input"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            autoComplete="new-password"
          />
        </div>
      </form>
    </Modal>
  );
}
