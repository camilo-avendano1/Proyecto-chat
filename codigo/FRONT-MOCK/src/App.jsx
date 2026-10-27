import React, { useState, useEffect, useCallback } from 'react';
import Header from './components/Header';
import ContextSidebar, { TENANT_PRESETS, SCENARIO_PRESETS } from './components/ContextSidebar';
import ChatWindow from './components/ChatWindow';
import TelemetryDrawer from './components/TelemetryDrawer';
import ObservabilityModal from './components/ObservabilityModal';
import { 
  fetchSystemStatus, 
  createSession, 
  streamDiagnostic, 
  queryDiagnostic 
} from './services/api';

export default function App() {
  // System & Health
  const [statusInfo, setStatusInfo] = useState(null);
  const [backendOnline, setBackendOnline] = useState(false);
  const [activeTab, setActiveTab] = useState('chat');
  const [showTelemetry, setShowTelemetry] = useState(true);

  // Tenant & Session
  const [tenantKey, setTenantKey] = useState('sura');
  const [sessionData, setSessionData] = useState(null);
  const [isSessionLoading, setIsSessionLoading] = useState(false);

  // Clinical & UI Context
  const [uiContext, setUiContext] = useState({
    url: 'https://plataforma.salud.co/formularios/validacion',
    pagina_actual: 'REGISTRO_FORMULARIOS',
    modulo: 'FORMULARIOS_CLINICOS',
    active_button_id: 'btn_validar_formulario',
    field_in_focus: 'campo_signos_vitales',
    estado_cargue_actual: 'CON_ERRORES',
    formato_archivo: 'FORMULARIO_CLINICO_CSV',
  });

  const [userContext, setUserContext] = useState({
    usuario: 'dr.juan.perez',
    filial: 'EPS Sura - Regional Nor-Occidente',
    eps: 'EPS_SURA',
    ips_code: '631300040301',
    ips_nombre: 'Clínica Las Américas',
    permisos: 'PERFIL_IPS_MEDICO',
  });

  const [systemLogs, setSystemLogs] = useState('');

  // Chat State
  const [messages, setMessages] = useState([]);
  const [queryInput, setQueryInput] = useState('');
  const [useStreaming, setUseStreaming] = useState(true);
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamingMessage, setStreamingMessage] = useState(null);
  const [activeDiagnostic, setActiveDiagnostic] = useState(null);
  const [activeSources, setActiveSources] = useState([]);
  const [activeScenarioId, setActiveScenarioId] = useState(null);

  // Live SSE Events Inspector
  const [events, setEvents] = useState([]);

  // Check Backend Status
  const checkStatus = useCallback(async () => {
    try {
      const res = await fetchSystemStatus();
      if (res && res.status === 'healthy') {
        setStatusInfo(res);
        setBackendOnline(true);
      } else {
        setBackendOnline(false);
      }
    } catch {
      setBackendOnline(false);
    }
  }, []);

  // Handshake to create or renew session
  const initSession = useCallback(async () => {
    const preset = TENANT_PRESETS[tenantKey];
    if (!preset) return;

    setIsSessionLoading(true);
    try {
      const session = await createSession({
        clientId: preset.client_id,
        origin: window.location.origin,
        epsId: preset.eps_id,
        ipsCode: preset.ips_code,
        apiKey: preset.api_key,
      });
      setSessionData(session);
    } catch (err) {
      console.error('Error al inicializar sesión:', err);
      alert(`Error al inicializar sesión con el backend: ${err.message}`);
    } finally {
      setIsSessionLoading(false);
    }
  }, [tenantKey]);

  // Initial Load
  useEffect(() => {
    checkStatus();
    initSession();
    const interval = setInterval(checkStatus, 15000);
    return () => clearInterval(interval);
  }, [checkStatus, initSession]);

  // Scenario Selector
  const handleSelectScenario = (scenario) => {
    setActiveScenarioId(scenario.id);
    setQueryInput(scenario.query);
    setSystemLogs(scenario.system_logs);
    setUiContext((prev) => ({
      ...prev,
      pagina_actual: scenario.pagina_actual,
      modulo: scenario.modulo,
      formato_archivo: scenario.formato_archivo,
      estado_cargue_actual: scenario.estado_cargue_actual,
      active_button_id: scenario.active_button_id,
      field_in_focus: scenario.field_in_focus,
    }));
  };

  // Send Message Handler
  const handleSendMessage = async (textToSend) => {
    const text = textToSend || queryInput;
    if (!text.trim() || isStreaming) return;

    // Check session
    let token = sessionData?.session_token;
    if (!token) {
      try {
        const preset = TENANT_PRESETS[tenantKey];
        const newSession = await createSession({
          clientId: preset.client_id,
          origin: window.location.origin,
          epsId: preset.eps_id,
          ipsCode: preset.ips_code,
          apiKey: preset.api_key,
        });
        setSessionData(newSession);
        token = newSession.session_token;
      } catch (e) {
        alert('No se pudo establecer la sesión con el backend. Verifica que el puerto 8000 esté activo.');
        return;
      }
    }

    const timestamp = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

    // 1. Append User Message
    const userMsg = {
      role: 'user',
      content: text,
      timestamp,
    };

    setMessages((prev) => [...prev, userMsg]);
    setQueryInput('');

    // Prepare History for Back Central
    const historyPayload = messages.map((m) => ({
      role: m.role,
      content: m.content,
    }));

    // Build Payload
    const requestPayload = {
      query: text,
      system_logs: systemLogs && systemLogs.trim().length > 0 ? systemLogs : null,
      ui_context: uiContext,
      user_context: userContext,
      conversation_history: historyPayload,
    };

    setIsStreaming(true);
    setActiveDiagnostic(null);
    setActiveSources([]);

    if (useStreaming) {
      // Streaming SSE
      let accumulatedText = '';
      let detectedDiagnostic = null;
      let detectedSources = [];

      setStreamingMessage({ role: 'assistant', content: '' });

      await streamDiagnostic({
        token,
        payload: requestPayload,
        onChunk: (chunk) => {
          accumulatedText += chunk;
          setStreamingMessage({
            role: 'assistant',
            content: accumulatedText,
          });
        },
        onErrorDiagnostic: (diag) => {
          if (diag) {
            detectedDiagnostic = diag;
            setActiveDiagnostic(diag);
          }
        },
        onSources: (sources) => {
          if (Array.isArray(sources) && sources.length > 0) {
            detectedSources = sources;
            setActiveSources(sources);
          }
        },
        onDone: (doneData) => {
          setMessages((prev) => [
            ...prev,
            {
              role: 'assistant',
              content: accumulatedText,
              error_diagnostic: detectedDiagnostic,
              sources: detectedSources,
              timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
            },
          ]);
          setStreamingMessage(null);
          setIsStreaming(false);
          checkStatus();
        },
        onError: (err) => {
          setMessages((prev) => [
            ...prev,
            {
              role: 'assistant',
              content: `⚠️ Error de comunicación: ${err}`,
              timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
            },
          ]);
          setStreamingMessage(null);
          setIsStreaming(false);
        },
        onRawEvent: ({ event, data }) => {
          setEvents((prev) => [
            {
              event,
              data,
              timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
            },
            ...prev.slice(0, 49), // Keep latest 50 events
          ]);
        },
      });
    } else {
      // Synchronous Query
      try {
        const resp = await queryDiagnostic({
          token,
          payload: requestPayload,
        });

        setMessages((prev) => [
          ...prev,
          {
            role: 'assistant',
            content: resp.response,
            error_diagnostic: resp.error_diagnostic,
            sources: resp.sources,
            timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          },
        ]);
        checkStatus();
      } catch (err) {
        setMessages((prev) => [
          ...prev,
          {
            role: 'assistant',
            content: `⚠️ Error en consulta síncrona: ${err.message}`,
            timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          },
        ]);
      } finally {
        setIsStreaming(false);
      }
    }
  };

  const handleClearChat = () => {
    setMessages([]);
    setStreamingMessage(null);
  };

  const handleQuickPrompt = (promptText) => {
    setQueryInput(promptText);
    handleSendMessage(promptText);
  };

  return (
    <div className="app-container">
      {/* Top Header */}
      <Header
        statusInfo={statusInfo}
        backendOnline={backendOnline}
        onRefreshStatus={checkStatus}
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        showTelemetry={showTelemetry}
        setShowTelemetry={setShowTelemetry}
      />

      {/* Main Split Grid */}
      <div className={`main-workspace ${!showTelemetry ? 'drawer-collapsed' : ''}`}>
        {/* Left: Simulation & Context Panel */}
        <ContextSidebar
          tenantKey={tenantKey}
          setTenantKey={setTenantKey}
          sessionData={sessionData}
          onInitSession={initSession}
          isSessionLoading={isSessionLoading}
          uiContext={uiContext}
          setUiContext={setUiContext}
          userContext={userContext}
          setUserContext={setUserContext}
          systemLogs={systemLogs}
          setSystemLogs={setSystemLogs}
          onSelectScenario={handleSelectScenario}
          activeScenarioId={activeScenarioId}
        />

        {/* Center: Live Chat Window */}
        <ChatWindow
          messages={messages}
          streamingMessage={streamingMessage}
          isStreaming={isStreaming}
          onSendMessage={handleSendMessage}
          onClearChat={handleClearChat}
          useStreaming={useStreaming}
          setUseStreaming={setUseStreaming}
          queryInput={queryInput}
          setQueryInput={setQueryInput}
          activeDiagnostic={activeDiagnostic}
          activeSources={activeSources}
          onQuickPrompt={handleQuickPrompt}
        />

        {/* Right: Live SSE Events Inspector */}
        {showTelemetry && (
          <TelemetryDrawer
            events={events}
            onClearEvents={() => setEvents([])}
            onClose={() => setShowTelemetry(false)}
          />
        )}
      </div>

      {/* Observability & Security Modal */}
      {(activeTab === 'metrics' || activeTab === 'security') && (
        <ObservabilityModal
          activeTab={activeTab}
          onClose={() => setActiveTab('chat')}
        />
      )}
    </div>
  );
}
