import React, { useState, useEffect, useCallback } from 'react';
import Header from './components/Header';
import ContextSidebar, { SITE_PRESETS } from './components/ContextSidebar';
import ChatWindow from './components/ChatWindow';
import TelemetryDrawer from './components/TelemetryDrawer';
import ObservabilityModal from './components/ObservabilityModal';
import {
  fetchSystemStatus,
  createSession,
  streamChat,
  queryChat,
} from './services/api';

const DEFAULT_UI_CONTEXT = {
  url: 'https://portal.empresa.com/operaciones',
  view: 'PORTAL_OPERATIVO',
  module: 'OPERACIONES',
  status: '',
  file_format: '',
  active_button_id: '',
  field_in_focus: '',
};

const DEFAULT_USER_CONTEXT = {
  id: 'ana.martinez',
  organization: 'División Operativa Central',
  unit_code: 'CORP-01',
  role: 'ANALISTA_OPERACIONES',
};

function pruneEmpty(obj) {
  if (!obj || typeof obj !== 'object') return {};
  const cleaned = {};
  for (const [key, value] of Object.entries(obj)) {
    if (value === null || value === undefined) continue;
    if (typeof value === 'string') {
      const trimmed = value.trim();
      if (!trimmed) continue;
      cleaned[key] = trimmed;
    } else {
      cleaned[key] = value;
    }
  }
  return cleaned;
}

export default function App() {
  // System & Health
  const [statusInfo, setStatusInfo] = useState(null);
  const [backendOnline, setBackendOnline] = useState(false);
  const [activeTab, setActiveTab] = useState('chat');
  const [showTelemetry, setShowTelemetry] = useState(true);

  // Organization, Site & Session (Generic organization by default)
  const [siteKey, setSiteKey] = useState('otra_empresa');
  const [sessionData, setSessionData] = useState(null);
  const [isSessionLoading, setIsSessionLoading] = useState(false);

  // Request Mode & Optional Enriched Context
  const [minimalMode, setMinimalMode] = useState(true);
  const [uiContext, setUiContext] = useState(DEFAULT_UI_CONTEXT);
  const [userContext, setUserContext] = useState(DEFAULT_USER_CONTEXT);
  const [systemLogs, setSystemLogs] = useState('');
  const [extrasText, setExtrasText] = useState('');
  const [extrasError, setExtrasError] = useState('');

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
    const preset = SITE_PRESETS[siteKey];
    if (!preset) return;

    setIsSessionLoading(true);
    try {
      const session = await createSession({
        origin: window.location.origin,
        apiKey: preset.api_key,
        orgId: preset.org_id,
        metadata: preset.metadata,
        siteCode: preset.site_code,
      });
      setSessionData(session);
    } catch (err) {
      console.error('Error al inicializar sesión:', err);
      alert(`Error al inicializar sesión con el backend: ${err.message}`);
    } finally {
      setIsSessionLoading(false);
    }
  }, [siteKey]);

  // Initial status check & polling
  useEffect(() => {
    checkStatus();
    const interval = setInterval(checkStatus, 15000);
    return () => clearInterval(interval);
  }, [checkStatus]);

  // Initialize session whenever organization/site preset changes
  useEffect(() => {
    initSession();
  }, [initSession]);

  // Scenario Selector
  const handleSelectScenario = (scenario) => {
    setActiveScenarioId(scenario.id);
    setQueryInput(scenario.query);
    setMinimalMode(Boolean(scenario.minimalMode));
    setSystemLogs(scenario.system_logs || '');
    setExtrasText(scenario.extras_json || '');
    setExtrasError('');

    if (scenario.target_site && siteKey !== scenario.target_site) {
      setSiteKey(scenario.target_site);
    } else if (
      scenario.target_org === 'sigires' &&
      !['sura', 'sanitas', 'nuevaeps'].includes(siteKey)
    ) {
      setSiteKey('sura');
    }

    if (scenario.context) {
      setUiContext(scenario.context);
    }
    if (scenario.user) {
      setUserContext(scenario.user);
    }
  };

  // Send Message Handler
  const handleSendMessage = async (textToSend) => {
    const text = (textToSend ?? queryInput).trim();
    if (!text || isStreaming) return;

    // Validate extras JSON before sending if enriched mode is active
    let parsedExtras = null;
    if (!minimalMode && extrasText && extrasText.trim().length > 0) {
      try {
        const parsed = JSON.parse(extrasText);
        if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
          setExtrasError('Extras debe ser un objeto JSON válido (ej. {"clave": "valor"}).');
          return;
        }
        if (Object.keys(parsed).length > 0) {
          parsedExtras = parsed;
        }
        setExtrasError('');
      } catch {
        setExtrasError('JSON inválido en Extras para Búsqueda.');
        return;
      }
    }

    // Check session
    let token = sessionData?.session_token;
    if (!token) {
      try {
        const preset = SITE_PRESETS[siteKey];
        const newSession = await createSession({
          origin: window.location.origin,
          apiKey: preset.api_key,
          orgId: preset.org_id,
          metadata: preset.metadata,
          siteCode: preset.site_code,
        });
        setSessionData(newSession);
        token = newSession.session_token;
      } catch {
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

    const historyPayload = messages.map((m) => ({
      role: m.role,
      content: m.content,
    }));

    setMessages((prev) => [...prev, userMsg]);
    setQueryInput('');

    // 2. Build clean generic payload
    const requestPayload = {
      query: text,
    };

    if (historyPayload.length > 0) {
      requestPayload.conversation_history = historyPayload;
    }

    if (!minimalMode) {
      const cleanUser = pruneEmpty(userContext);
      if (Object.keys(cleanUser).length > 0) {
        requestPayload.user = cleanUser;
      }

      const cleanContext = pruneEmpty(uiContext);
      if (Object.keys(cleanContext).length > 0) {
        requestPayload.context = cleanContext;
      }

      if (systemLogs && systemLogs.trim().length > 0) {
        requestPayload.logs = systemLogs.trim();
      }

      if (parsedExtras) {
        requestPayload.extras = parsedExtras;
      }
    }

    setIsStreaming(true);
    setActiveDiagnostic(null);
    setActiveSources([]);

    if (useStreaming) {
      // Streaming SSE
      let accumulatedText = '';
      let detectedDiagnostic = null;
      let detectedSources = [];

      setStreamingMessage({ role: 'assistant', content: '' });

      await streamChat({
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
        onDone: () => {
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
              timestamp: new Date().toLocaleTimeString([], {
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit',
              }),
            },
            ...prev.slice(0, 49),
          ]);
        },
      });
    } else {
      // Synchronous Query
      try {
        const resp = await queryChat({
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
          siteKey={siteKey}
          setSiteKey={setSiteKey}
          minimalMode={minimalMode}
          setMinimalMode={setMinimalMode}
          sessionData={sessionData}
          onInitSession={initSession}
          isSessionLoading={isSessionLoading}
          uiContext={uiContext}
          setUiContext={setUiContext}
          userContext={userContext}
          setUserContext={setUserContext}
          systemLogs={systemLogs}
          setSystemLogs={setSystemLogs}
          extrasText={extrasText}
          setExtrasText={setExtrasText}
          extrasError={extrasError}
          setExtrasError={setExtrasError}
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
