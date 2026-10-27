import React from 'react';
import { Terminal, Trash2, X, Activity } from 'lucide-react';

export default function TelemetryDrawer({ 
  events, 
  onClearEvents, 
  onClose 
}) {
  return (
    <aside className="telemetry-panel">
      <div className="panel-header">
        <div className="panel-title">
          <Terminal size={17} style={{ color: '#818cf8' }} />
          <span>Inspector SSE ({events.length})</span>
        </div>
        <div style={{ display: 'flex', gap: '6px' }}>
          <button 
            className="btn-secondary" 
            style={{ padding: '4px 8px' }}
            onClick={onClearEvents}
            title="Limpiar eventos"
          >
            <Trash2 size={13} />
          </button>
          <button 
            className="btn-secondary" 
            style={{ padding: '4px 8px' }}
            onClick={onClose}
            title="Cerrar panel"
          >
            <X size={13} />
          </button>
        </div>
      </div>

      <div style={{ padding: '16px', overflowY: 'auto', flex: 1 }}>
        <p style={{ fontSize: '0.74rem', color: 'var(--text-dim)', marginBottom: '12px' }}>
          Eventos Server-Sent Events recibidos en tiempo real desde <code>POST /api/v1/diagnostic/stream</code>:
        </p>

        {events.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '40px 10px', color: 'var(--text-dim)', fontSize: '0.78rem' }}>
            <Activity size={24} style={{ margin: '0 auto 8px', opacity: 0.4 }} />
            No hay eventos SSE aún. Envía una consulta para inspeccionar los eventos.
          </div>
        ) : (
          events.map((evt, idx) => (
            <div key={idx} className="telemetry-item">
              <div className="telemetry-item-header">
                <span className={`event-type-badge ${evt.event}`}>
                  {evt.event}
                </span>
                <span style={{ color: 'var(--text-dim)', fontSize: '0.68rem', fontFamily: 'var(--font-mono)' }}>
                  {evt.timestamp}
                </span>
              </div>
              <div className="telemetry-code">
                {typeof evt.data === 'object' ? JSON.stringify(evt.data, null, 2) : evt.data}
              </div>
            </div>
          ))
        )}
      </div>
    </aside>
  );
}
