import React from 'react';
import { 
  Bot, 
  Activity, 
  Database, 
  Cpu, 
  RefreshCw, 
  BarChart3, 
  ShieldCheck, 
  Terminal,
  Server
} from 'lucide-react';

export default function Header({ 
  statusInfo, 
  backendOnline, 
  onRefreshStatus, 
  activeTab, 
  setActiveTab,
  showTelemetry,
  setShowTelemetry
}) {
  return (
    <header className="app-header">
      <div className="brand-section">
        <div className="brand-logo-glow">
          <Bot size={24} />
        </div>
        <div className="brand-title">
          <h1>
            SaaS Core Chat & Gateway
            <span className="brand-badge">Front Mock</span>
          </h1>
          <div className="brand-subtitle">
            Asistente Técnico de Formularios, Formatos y Reglamentos • RAG Multi-Cliente
          </div>
        </div>
      </div>

      {/* Middle Navigation Tabs */}
      <nav className="nav-tabs">
        <button 
          className={`nav-tab-btn ${activeTab === 'chat' ? 'active' : ''}`}
          onClick={() => setActiveTab('chat')}
        >
          <Bot size={15} />
          Simulador Chat
        </button>
        <button 
          className={`nav-tab-btn ${activeTab === 'metrics' ? 'active' : ''}`}
          onClick={() => setActiveTab('metrics')}
        >
          <BarChart3 size={15} />
          Consumo & Tokens
        </button>
        <button 
          className={`nav-tab-btn ${activeTab === 'security' ? 'active' : ''}`}
          onClick={() => setActiveTab('security')}
        >
          <ShieldCheck size={15} />
          Auditoría Ley 1581
        </button>
      </nav>

      {/* Right System Status */}
      <div className="header-status-group">
        <div className="status-pill" title={`Backend: ${backendOnline ? 'Conectado a FastAPI (Puerto 8000)' : 'Desconectado'}`}>
          <span className={`status-dot ${backendOnline ? 'online' : ''}`} />
          <Server size={13} />
          <span>{backendOnline ? 'Back Central Online' : 'Desconectado'}</span>
        </div>

        {statusInfo && (
          <>
            <div className="status-pill" title={`Auth Service (:8002): ${statusInfo.auth_service_status || 'not_probed'}`}>
              <span className={`status-dot ${statusInfo.auth_service_status === 'connected' ? 'online' : ''}`} />
              <span>Auth:8002</span>
            </div>
            <div className="status-pill" title={`LLM Gateway (:8003): ${statusInfo.llm_gateway_status || 'not_probed'}`}>
              <span className={`status-dot ${statusInfo.llm_gateway_status === 'connected' ? 'online' : ''}`} />
              <span>Gateway:8003</span>
            </div>
          </>
        )}

        <button 
          className={`btn-secondary ${showTelemetry ? 'active' : ''}`}
          onClick={() => setShowTelemetry(!showTelemetry)}
          title="Ver o cerrar panel de eventos SSE en vivo"
        >
          <Terminal size={14} />
          <span>Inspector SSE</span>
        </button>

        <button 
          className="btn-secondary" 
          onClick={onRefreshStatus}
          title="Verificar estado del backend"
        >
          <RefreshCw size={14} />
        </button>
      </div>
    </header>
  );
}
