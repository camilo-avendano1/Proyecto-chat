import React, { useRef, useEffect, useState } from 'react';
import { 
  Send, 
  Bot, 
  User, 
  Sparkles, 
  Trash2, 
  Copy, 
  Check, 
  BookOpen, 
  AlertTriangle,
  Radio,
  FileCheck,
  ChevronDown,
  ChevronRight,
  ShieldAlert,
  Zap
} from 'lucide-react';

function SimpleMarkdown({ content }) {
  if (!content) return null;

  // Split into lines for basic markdown rendering
  const lines = content.split('\n');
  const rendered = [];

  let inList = false;
  let listItems = [];

  const flushList = () => {
    if (inList && listItems.length > 0) {
      rendered.push(
        <ul key={`ul-${rendered.length}`} style={{ paddingLeft: '20px', marginBottom: '8px' }}>
          {listItems.map((item, idx) => (
            <li key={idx} dangerouslySetInnerHTML={{ __html: item }} />
          ))}
        </ul>
      );
      inList = false;
      listItems = [];
    }
  };

  const formatInline = (text) => {
    return text
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      .replace(/`([^`]+)`/g, '<code>$1</code>');
  };

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];

    if (line.startsWith('### ')) {
      flushList();
      rendered.push(
        <h3 key={i} dangerouslySetInnerHTML={{ __html: formatInline(line.replace('### ', '')) }} />
      );
    } else if (line.startsWith('## ')) {
      flushList();
      rendered.push(
        <h2 key={i} dangerouslySetInnerHTML={{ __html: formatInline(line.replace('## ', '')) }} />
      );
    } else if (line.startsWith('# ')) {
      flushList();
      rendered.push(
        <h1 key={i} dangerouslySetInnerHTML={{ __html: formatInline(line.replace('# ', '')) }} />
      );
    } else if (line.trim().startsWith('- ') || line.trim().startsWith('* ')) {
      inList = true;
      listItems.push(formatInline(line.trim().replace(/^[-*]\s+/, '')));
    } else if (/^\d+\.\s+/.test(line.trim())) {
      flushList();
      rendered.push(
        <p key={i} style={{ paddingLeft: '14px', marginBottom: '4px' }} dangerouslySetInnerHTML={{ __html: formatInline(line.trim()) }} />
      );
    } else if (line.trim() === '') {
      flushList();
    } else {
      flushList();
      rendered.push(
        <p key={i} dangerouslySetInnerHTML={{ __html: formatInline(line) }} />
      );
    }
  }

  flushList();

  return <div className="markdown-body">{rendered}</div>;
}

export default function ChatWindow({
  messages,
  streamingMessage,
  isStreaming,
  onSendMessage,
  onClearChat,
  useStreaming,
  setUseStreaming,
  queryInput,
  setQueryInput,
  activeDiagnostic,
  activeSources,
  onQuickPrompt,
}) {
  const messagesEndRef = useRef(null);
  const [copiedId, setCopiedId] = useState(null);
  const [sourcesOpen, setSourcesOpen] = useState(true);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, streamingMessage]);

  const handleCopy = (id, text) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (!isStreaming && queryInput.trim()) {
        onSendMessage(queryInput);
      }
    }
  };

  return (
    <main className="chat-panel">
      {/* Banner / Info Bar */}
      <div className="chat-banner">
        <div className="chat-banner-item">
          <Bot size={15} style={{ color: '#10b981' }} />
          <span>Asistente Técnico de Formularios y Reglamentos • Búsqueda RAG Dinámica</span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
          <label className="mode-toggle" title="Alternar entre streaming en tiempo real (SSE) o consulta síncrona">
            <Radio size={13} style={{ color: useStreaming ? '#10b981' : '#64748b' }} />
            <span>Modo: {useStreaming ? 'Streaming SSE' : 'Síncrono (JSON)'}</span>
            <input
              type="checkbox"
              style={{ display: 'none' }}
              checked={useStreaming}
              onChange={(e) => setUseStreaming(e.target.checked)}
            />
          </label>

          {messages.length > 0 && (
            <button 
              className="btn-secondary" 
              onClick={onClearChat}
              title="Limpiar historial de conversación"
            >
              <Trash2 size={13} />
              <span>Limpiar</span>
            </button>
          )}
        </div>
      </div>

      {/* Message Timeline */}
      <div className="chat-messages">
        {messages.length === 0 && !streamingMessage && (
          <div style={{ 
            textAlign: 'center', 
            margin: 'auto', 
            maxWidth: '520px', 
            padding: '30px 20px',
            color: 'var(--text-muted)' 
          }}>
            <div style={{
              width: '64px',
              height: '64px',
              borderRadius: '20px',
              background: 'linear-gradient(135deg, rgba(16, 185, 129, 0.2) 0%, rgba(99, 102, 241, 0.2) 100%)',
              border: '1px solid var(--border-medium)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              margin: '0 auto 18px',
              color: '#34d399'
            }}>
              <Sparkles size={32} />
            </div>
            <h2 style={{ color: 'var(--text-bright)', fontSize: '1.25rem', marginBottom: '8px' }}>
              Simulador del Asistente Técnico de Formularios y Reglamentos
            </h2>
            <p style={{ fontSize: '0.85rem', lineHeight: '1.6', marginBottom: '20px' }}>
              Consulta sobre el diligenciamiento y validación de formularios clínicos, de enfermería o administrativos
              en diferentes formatos (CSV, TXT, XML, JSON, ZIP). Los documentos y reglamentos se recuperan dinámicamente desde la búsqueda.
            </p>
            <div style={{ display: 'flex', justifyContent: 'center', gap: '8px', flexWrap: 'wrap' }}>
              <button 
                className="chip-btn"
                onClick={() => onQuickPrompt('Tengo un error al subir el formulario de enfermería en el campo de signos vitales')}
              >
                🩺 Formulario Enfermería (CSV/Web)
              </button>
              <button 
                className="chip-btn"
                onClick={() => onQuickPrompt('¿Cómo subsano la inconsistencia de códigos en el formato RIPS?')}
              >
                📋 Formato RIPS / Facturación
              </button>
              <button 
                className="chip-btn"
                onClick={() => onQuickPrompt('Hola, ¿qué funciones tienes disponibles?')}
              >
                ⚡ Fast-Path Saludo
              </button>
            </div>
          </div>
        )}

        {messages.map((msg, index) => {
          const isUser = msg.role === 'user';
          return (
            <div key={index} className={`message-bubble ${isUser ? 'user' : 'assistant'}`}>
              <div className={`avatar ${isUser ? 'user-avatar' : 'assistant-avatar'}`}>
                {isUser ? <User size={18} /> : <Bot size={18} />}
              </div>

              <div className="bubble-content-wrap">
                <div className="bubble-header">
                  <span>{isUser ? 'Usuario IPS' : 'Core Back Central'}</span>
                  <span>•</span>
                  <span>{msg.timestamp || 'Ahora'}</span>
                  {!isUser && (
                    <button
                      className="btn-secondary"
                      style={{ padding: '2px 6px', fontSize: '0.68rem', marginLeft: 'auto' }}
                      onClick={() => handleCopy(index, msg.content)}
                      title="Copiar texto"
                    >
                      {copiedId === index ? <Check size={11} /> : <Copy size={11} />}
                    </button>
                  )}
                </div>

                <div className="bubble-card">
                  {isUser ? (
                    <div>{msg.content}</div>
                  ) : (
                    <SimpleMarkdown content={msg.content} />
                  )}

                  {/* Diagnostic Badge Card */}
                  {msg.error_diagnostic && (
                    <div className="diagnostic-badge-card">
                      <div className="diag-title">
                        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                          <AlertTriangle size={15} style={{ color: '#f59e0b' }} />
                          <span className="diag-code">{msg.error_diagnostic.detected_code}</span>
                        </div>
                        <span className={`phase-pill ${msg.error_diagnostic.error_phase}`}>
                          {msg.error_diagnostic.error_phase}
                        </span>
                      </div>

                      <div className="diag-grid">
                        <div>
                          <div className="diag-item-label">Variable</div>
                          <div style={{ color: 'var(--text-bright)', fontWeight: 600 }}>
                            {msg.error_diagnostic.affected_variable_number 
                              ? `Var ${msg.error_diagnostic.affected_variable_number}: ${msg.error_diagnostic.affected_variable_name || ''}`
                              : 'No especificada'}
                          </div>
                        </div>
                        <div>
                          <div className="diag-item-label">Fila Afectada</div>
                          <div style={{ color: 'var(--text-bright)', fontWeight: 600 }}>
                            {msg.error_diagnostic.affected_row ? `Fila #${msg.error_diagnostic.affected_row}` : 'General'}
                          </div>
                        </div>
                        <div>
                          <div className="diag-item-label">Severidad</div>
                          <div style={{ 
                            color: msg.error_diagnostic.severity === 'BLOCKING' ? '#ef4444' : '#f59e0b',
                            fontWeight: 600 
                          }}>
                            {msg.error_diagnostic.severity}
                          </div>
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Sources Accordion */}
                  {msg.sources && msg.sources.length > 0 && (
                    <div className="sources-card">
                      <div 
                        className="sources-header" 
                        onClick={() => setSourcesOpen(!sourcesOpen)}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                          <BookOpen size={13} />
                          <span>Fuentes Normativas Consultadas ({msg.sources.length})</span>
                        </div>
                        {sourcesOpen ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                      </div>

                      {sourcesOpen && (
                        <div className="sources-list">
                          {msg.sources.map((s, sIdx) => (
                            <div key={sIdx} className="source-item">
                              <div>
                                <span style={{ fontWeight: 600, color: 'var(--text-bright)' }}>{s.document_title}</span>
                                <span style={{ color: 'var(--text-dim)', marginLeft: '6px' }}>({s.section})</span>
                              </div>
                              <span className="source-scope">{s.scope}</span>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            </div>
          );
        })}

        {/* Live Streaming Message Bubble */}
        {streamingMessage && (
          <div className="message-bubble assistant">
            <div className="avatar assistant-avatar">
              <Bot size={18} />
            </div>

            <div className="bubble-content-wrap">
              <div className="bubble-header">
                <span>Core Back Central (Transmitiendo SSE...)</span>
              </div>

              <div className="bubble-card">
                <SimpleMarkdown content={streamingMessage.content} />
                <span className="cursor-blink" />

                {/* Live Diagnostic if received during stream */}
                {activeDiagnostic && (
                  <div className="diagnostic-badge-card" style={{ marginTop: '12px' }}>
                    <div className="diag-title">
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <AlertTriangle size={15} style={{ color: '#f59e0b' }} />
                        <span className="diag-code">{activeDiagnostic.detected_code}</span>
                      </div>
                      <span className={`phase-pill ${activeDiagnostic.error_phase}`}>
                        {activeDiagnostic.error_phase}
                      </span>
                    </div>
                    <div className="diag-grid">
                      <div>
                        <div className="diag-item-label">Variable</div>
                        <div style={{ color: 'var(--text-bright)', fontWeight: 600 }}>
                          {activeDiagnostic.affected_variable_number 
                            ? `Var ${activeDiagnostic.affected_variable_number}: ${activeDiagnostic.affected_variable_name || ''}`
                            : 'N/A'}
                        </div>
                      </div>
                      <div>
                        <div className="diag-item-label">Fila</div>
                        <div style={{ color: 'var(--text-bright)', fontWeight: 600 }}>
                          {activeDiagnostic.affected_row ? `Fila #${activeDiagnostic.affected_row}` : 'N/A'}
                        </div>
                      </div>
                      <div>
                        <div className="diag-item-label">Severidad</div>
                        <div style={{ color: '#ef4444', fontWeight: 600 }}>
                          {activeDiagnostic.severity || 'BLOCKING'}
                        </div>
                      </div>
                    </div>
                  </div>
                )}

                {/* Live Sources */}
                {activeSources && activeSources.length > 0 && (
                  <div className="sources-card">
                    <div className="sources-header">
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <BookOpen size={13} />
                        <span>Fuentes Normativas Identificadas ({activeSources.length})</span>
                      </div>
                    </div>
                    <div className="sources-list">
                      {activeSources.map((s, sIdx) => (
                        <div key={sIdx} className="source-item">
                          <span>{s.document_title} - {s.section}</span>
                          <span className="source-scope">{s.scope}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      <div className="chat-input-area">
        {/* Quick Prompts Row */}
        <div className="quick-prompts-row">
          <button 
            className="quick-prompt-btn"
            onClick={() => onQuickPrompt('Tengo un error en el formulario de enfermería en los signos vitales')}
          >
            <Sparkles size={12} style={{ color: '#10b981' }} />
            Formulario Enfermería
          </button>
          <button 
            className="quick-prompt-btn"
            onClick={() => onQuickPrompt('El validador me rechaza el formato de fecha en el registro 45')}
          >
            <AlertTriangle size={12} style={{ color: '#0ea5e9' }} />
            Error Formato Fecha
          </button>
          <button 
            className="quick-prompt-btn"
            onClick={() => onQuickPrompt('Hola, ¿cómo estás?')}
          >
            <Zap size={12} style={{ color: '#f59e0b' }} />
            Fast-Path (0 Tokens)
          </button>
          <button 
            className="quick-prompt-btn"
            onClick={() => onQuickPrompt('¿Cómo preparo arroz con mariscos?')}
          >
            <ShieldAlert size={12} style={{ color: '#ef4444' }} />
            Prueba Guardrail (Fuera Dominio)
          </button>
        </div>

        {/* Input Text Box */}
        <div className="input-box-wrapper">
          <textarea
            className="chat-input-textarea"
            placeholder="Escribe tu consulta sobre formularios, formatos o reglamentos técnicos... (Presiona Enter para enviar)"
            value={queryInput}
            onChange={(e) => setQueryInput(e.target.value)}
            onKeyDown={handleKeyDown}
            rows={1}
            disabled={isStreaming}
          />
          <div className="input-controls">
            <button
              className="send-btn"
              onClick={() => onSendMessage(queryInput)}
              disabled={isStreaming || !queryInput.trim()}
              title="Enviar consulta al Back Central"
            >
              <Send size={16} />
            </button>
          </div>
        </div>
      </div>
    </main>
  );
}
