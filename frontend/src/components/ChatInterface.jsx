import React, { useState, useRef, useEffect, useMemo } from 'react'
import { Send, Trash2, Brain, ChevronDown, Code, RefreshCw, AlertTriangle } from 'lucide-react'
import { useChat } from '../hooks/useChat'
import MessageBubble from './MessageBubble'

// ── Persona options ───────────────────────────────────────────────────────────
const PERSONAS = [
  { value: 'general',     label: '🧠 General',     desc: 'All-purpose analysis' },
  { value: 'finance',     label: '💰 Finance',     desc: 'Revenue, KPIs, P&L, margins' },
  { value: 'marketing',   label: '📣 Marketing',   desc: 'Campaigns, funnels, segments' },
  { value: 'engineering', label: '⚙️ Engineering', desc: 'Metrics, throughput, errors' },
]

// ── Generic suggestion chips shown when no dataset metadata ──────────────────
const GENERIC_SUGGESTIONS = [
  'Show me the first 5 rows',
  'What are the column types?',
  'Show summary statistics',
  'Which column has the most missing values?',
  'Plot a bar chart of the top categories',
  'Find any outliers in the data',
]

// ── PersonaSelector ──────────────────────────────────────────────────────────
function PersonaSelector({ value, onChange }) {
  const [open, setOpen] = useState(false)
  const ref = useRef(null)
  const active = PERSONAS.find((p) => p.value === value) || PERSONAS[0]

  // Close on outside click
  useEffect(() => {
    const handler = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false) }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  return (
    <div ref={ref} style={{ position: 'relative' }}>
      <button
        className="btn-ghost"
        style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.8rem', padding: '4px 10px' }}
        onClick={() => setOpen((o) => !o)}
        title="Change analysis persona"
      >
        <span>{active.label}</span>
        <ChevronDown size={13} style={{ opacity: 0.6 }} />
      </button>

      {open && (
        <div style={{
          position: 'absolute', bottom: '110%', left: 0, zIndex: 50,
          background: 'var(--surface)', border: '1px solid var(--border)',
          borderRadius: 10, padding: 6, minWidth: 200,
          boxShadow: '0 8px 32px rgba(0,0,0,0.4)',
        }}>
          {PERSONAS.map((p) => (
            <button
              key={p.value}
              style={{
                display: 'block', width: '100%', textAlign: 'left',
                padding: '8px 12px', borderRadius: 7, border: 'none',
                background: p.value === value ? 'var(--surface-alt)' : 'transparent',
                color: 'var(--text-primary)', cursor: 'pointer', fontSize: '0.82rem',
              }}
              onClick={() => { onChange(p.value); setOpen(false) }}
            >
              <div style={{ fontWeight: 600 }}>{p.label}</div>
              <div style={{ color: 'var(--text-muted)', fontSize: '0.72rem' }}>{p.desc}</div>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

// ── SuggestedQuestions (follow-up chips) ──────────────────────────────────────
function SuggestedQuestions({ questions, onSelect }) {
  if (!questions || questions.length === 0) return null
  return (
    <div style={{ padding: '8px 0 4px 0' }}>
      <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginBottom: 6, paddingLeft: 4 }}>
        Suggested follow-ups:
      </div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
        {questions.map((q, i) => (
          <button
            key={i}
            className="suggestion-chip"
            style={{ fontSize: '0.76rem' }}
            onClick={() => onSelect(q)}
          >
            {q}
          </button>
        ))}
      </div>
    </div>
  )
}

// ── SessionLostBanner — shown when session is missing from server ─────────────
function SessionLostBanner({ onClearSession }) {
  return (
    <div style={{
      margin: '16px',
      padding: '16px 20px',
      background: 'rgba(255, 165, 0, 0.08)',
      border: '1px solid rgba(255, 165, 0, 0.3)',
      borderRadius: 12,
      display: 'flex',
      alignItems: 'flex-start',
      gap: 12,
    }}>
      <AlertTriangle size={18} style={{ color: '#f5a623', flexShrink: 0, marginTop: 2 }} />
      <div>
        <div style={{ fontWeight: 600, color: '#f5a623', fontSize: '0.88rem', marginBottom: 4 }}>
          Session expired — dataset not found on server
        </div>
        <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
          The backend server restarted and your session data was cleared. This is normal on free hosting plans.
          Please re-upload your dataset to start a new chat session.
        </div>
        {onClearSession && (
          <button
            onClick={onClearSession}
            style={{
              marginTop: 10,
              padding: '6px 14px',
              borderRadius: 8,
              border: '1px solid rgba(255,165,0,0.4)',
              background: 'rgba(255,165,0,0.12)',
              color: '#f5a623',
              cursor: 'pointer',
              fontSize: '0.8rem',
              display: 'flex',
              alignItems: 'center',
              gap: 6,
            }}
          >
            <RefreshCw size={13} />
            Clear &amp; Re-upload
          </button>
        )}
      </div>
    </div>
  )
}

// ── ChatInterface (main export) ───────────────────────────────────────────────
export default function ChatInterface({ sessionId, datasetMeta, onClearSession }) {
  const { messages, isLoading, sendQuestion, clearHistory, threadId } = useChat(sessionId)
  const [input, setInput] = useState('')
  const [persona, setPersona] = useState('general')
  const [debugMode, setDebugMode] = useState(false)
  const feedRef = useRef(null)

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    if (feedRef.current) {
      feedRef.current.scrollTop = feedRef.current.scrollHeight
    }
  }, [messages])

  // Build dynamic suggestions from dataset column metadata
  const suggestions = useMemo(() => {
    if (!datasetMeta?.columns) return GENERIC_SUGGESTIONS
    const cols = datasetMeta.columns
    const numCols = cols.filter((c) => ['int64', 'float64', 'int32', 'float32'].includes(c.dtype))
    const catCols = cols.filter((c) => c.dtype === 'object')

    const dynamic = []
    dynamic.push('Show me the first 5 rows')
    if (numCols.length > 0) dynamic.push(`Show summary statistics for ${numCols[0].name}`)
    if (catCols.length > 0) dynamic.push(`Show ${catCols[0].name} distribution as a bar chart`)
    if (numCols.length >= 2) dynamic.push(`Scatter plot of ${numCols[0].name} vs ${numCols[1].name}`)
    dynamic.push('Which columns have missing values?')
    if (catCols.length > 0 && numCols.length > 0)
      dynamic.push(`Compare ${numCols[0].name} by ${catCols[0].name}`)
    return dynamic.slice(0, 6)
  }, [datasetMeta])

  const handleSend = (questionOverride) => {
    const q = (questionOverride || input).trim()
    if (!q || isLoading) return
    setInput('')
    sendQuestion(q, persona, debugMode)
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  // Detect if the last error was a session-not-found error
  const lastAgentMsg = [...messages].reverse().find((m) => m.role === 'agent')
  const showSuggested = !isLoading && lastAgentMsg?.suggestedQuestions?.length > 0
  const isSessionLost =
    lastAgentMsg?.error &&
    (lastAgentMsg.error.includes('Session') ||
      lastAgentMsg.error.includes('session') ||
      lastAgentMsg.error.includes('not found on the server') ||
      lastAgentMsg.error.includes('re-upload'))

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      height: '100%',
      width: '100%',
      minHeight: 0,
      overflow: 'hidden',
    }}>
      {/* Memory banner */}
      {messages.length > 0 && threadId && (
        <div className="memory-banner">
          <Brain size={14} />
          Memory active — Copilot thread ID: {threadId?.slice(0, 8)}
        </div>
      )}
      {messages.length > 0 && !threadId && (
        <div className="memory-banner" style={{ background: 'rgba(255,165,0,0.08)', borderColor: 'rgba(255,165,0,0.2)', color: 'var(--text-secondary)' }}>
          <Brain size={14} style={{ opacity: 0.5 }} />
          Threadless mode — chat history not persisted (backend restart)
        </div>
      )}

      {/* Chat feed */}
      <div ref={feedRef} className="chat-feed" style={{ flex: 1, overflowY: 'auto', overflowX: 'hidden', minHeight: 0, width: '100%' }}>
        {messages.length === 0 ? (
          /* Hero / empty state */
          <div className="chat-hero">
            <div className="chat-hero-inner">
              <h1 className="chat-hero-title">
                <span className="gradient-text">Ask anything about your data</span>
              </h1>
              <p className="chat-hero-subtitle">
                I can analyze and summarize your dataset using natural language. Try a question below.
              </p>
              <div className="suggestions-grid">
                {suggestions.map((s, i) => (
                  <button
                    key={i}
                    className="suggestion-chip"
                    onClick={() => handleSend(s)}
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          </div>
        ) : (
          /* Message thread */
          messages.map((msg) => (
            <MessageBubble key={msg.id} message={msg} />
          ))
        )}

        {/* Session lost banner */}
        {isSessionLost && (
          <SessionLostBanner onClearSession={onClearSession} />
        )}

        {/* Suggested follow-up questions below last response */}
        {showSuggested && (
          <div style={{ padding: '0 12px 8px' }}>
            <SuggestedQuestions
              questions={lastAgentMsg.suggestedQuestions}
              onSelect={(q) => handleSend(q)}
            />
          </div>
        )}

        {/* Loading indicator */}
        {isLoading && (
          <div className="message-row agent">
            <div className="message-bubble agent" style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <div className="spinner" style={{ width: 20, height: 20 }} />
              <span style={{ color: 'var(--text-muted)', fontSize: '0.84rem' }}>Analyzing…</span>
            </div>
          </div>
        )}
      </div>

      {/* Quick Action Buttons */}
      <div style={{
        display: 'flex',
        gap: 8,
        padding: '8px 12px',
        overflowX: 'auto',
        overflowY: 'hidden',
        borderTop: '1px solid var(--border-subtle)',
        background: 'rgba(10,10,15,0.4)',
        whiteSpace: 'nowrap',
        scrollbarWidth: 'none',
        flexShrink: 0,
        width: '100%',
        boxSizing: 'border-box',
        WebkitOverflowScrolling: 'touch',
      }}>
        <button className="suggestion-chip" style={{ fontSize: '0.78rem', padding: '6px 12px', cursor: 'pointer', flexShrink: 0, whiteSpace: 'nowrap' }} onClick={() => handleSend("Show dataset summary")}>📊 Summary</button>
        <button className="suggestion-chip" style={{ fontSize: '0.78rem', padding: '6px 12px', cursor: 'pointer', flexShrink: 0, whiteSpace: 'nowrap' }} onClick={() => handleSend("count rows")}>🔢 Count Rows</button>
        <button className="suggestion-chip" style={{ fontSize: '0.78rem', padding: '6px 12px', cursor: 'pointer', flexShrink: 0, whiteSpace: 'nowrap' }} onClick={() => handleSend("Show missing values")}>🔍 Missing Values</button>
        <button className="suggestion-chip" style={{ fontSize: '0.78rem', padding: '6px 12px', cursor: 'pointer', flexShrink: 0, whiteSpace: 'nowrap' }} onClick={() => handleSend("Find correlations")}>📈 Correlations</button>
        <button className="suggestion-chip" style={{ fontSize: '0.78rem', padding: '6px 12px', cursor: 'pointer', flexShrink: 0, whiteSpace: 'nowrap' }} onClick={() => handleSend("Find outliers in data")}>🚨 Outliers</button>
      </div>

      {/* Input bar */}
      <div className="chat-input-bar" style={{
        display: 'flex',
        flexDirection: 'column',
        gap: 8,
        padding: '12px 16px',
        borderTop: '1px solid var(--border-subtle)',
        background: 'var(--bg-surface)',
        flexShrink: 0,
        width: '100%',
        boxSizing: 'border-box',
      }}>
        {/* Control Row */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          width: '100%',
          justifyContent: 'space-between',
        }}>
          <PersonaSelector value={persona} onChange={setPersona} />

          <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
            <button 
              className="btn-ghost"
              style={{ 
                display: 'flex', 
                alignItems: 'center', 
                gap: 6, 
                fontSize: '0.78rem', 
                padding: '4px 10px',
                borderRadius: 'var(--radius-sm)',
                border: debugMode ? '1px solid var(--color-vermillion-signal)' : '1px solid var(--border-subtle)',
                background: debugMode ? 'rgba(204, 145, 102, 0.08)' : 'transparent',
                color: debugMode ? 'var(--text-primary)' : 'var(--text-secondary)'
              }}
              onClick={() => setDebugMode(!debugMode)}
              title="Toggle developer mode to inspect executed code"
            >
              <Code size={14} style={{ color: debugMode ? 'var(--color-vermillion-signal)' : 'inherit' }} />
              <span>Dev Mode</span>
            </button>

            {messages.length > 0 && (
              <button className="btn-icon" onClick={clearHistory} title="Clear history" style={{ width: 32, height: 32 }}>
                <Trash2 size={15} />
              </button>
            )}
          </div>
        </div>

        {/* Input Textbox & Send Button Row */}
        <div style={{
          display: 'flex',
          gap: 8,
          width: '100%',
          alignItems: 'flex-end',
        }}>
          <textarea
            className="input-field"
            placeholder="Ask a question about your data…"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            rows={1}
            style={{
              flex: 1,
              borderRadius: 'var(--radius-sm)',
              minHeight: 44,
              maxHeight: 120,
              resize: 'none',
              border: '1px solid var(--border-subtle)',
              padding: '12px 14px',
              fontSize: '0.9rem',
            }}
          />
          <button
            className="chat-send-btn"
            onClick={() => handleSend()}
            disabled={!input.trim() || isLoading}
            style={{
              width: 44,
              height: 44,
              borderRadius: 'var(--radius-full)',
              background: input.trim() && !isLoading ? 'var(--color-ink)' : 'var(--color-mist)',
              color: input.trim() && !isLoading ? 'var(--color-white)' : 'var(--color-dove)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              border: 'none',
              cursor: input.trim() && !isLoading ? 'pointer' : 'not-allowed',
            }}
          >
            <Send size={18} />
          </button>
        </div>
      </div>
    </div>
  )
}
