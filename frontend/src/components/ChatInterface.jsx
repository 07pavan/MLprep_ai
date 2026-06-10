import React, { useState, useRef, useEffect, useMemo } from 'react'
import { Send, Trash2, Brain, ChevronDown, HelpCircle } from 'lucide-react'
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

// ── ClarificationCard ────────────────────────────────────────────────────────
function ClarificationCard({ question, onAnswer }) {
  const [answer, setAnswer] = useState('')

  const handleSubmit = () => {
    const q = answer.trim()
    if (!q) return
    setAnswer('')
    onAnswer(q)
  }

  return (
    <div className="message-row agent">
      <div className="message-bubble agent" style={{ maxWidth: '92%' }}>
        <div style={{
          display: 'flex', alignItems: 'flex-start', gap: 10,
          padding: '12px 14px', borderRadius: 8,
          background: 'var(--surface-alt)',
          border: '1px solid var(--accent)',
          marginBottom: 12,
        }}>
          <HelpCircle size={18} style={{ color: 'var(--accent)', flexShrink: 0, marginTop: 2 }} />
          <div>
            <div style={{ fontWeight: 600, fontSize: '0.84rem', color: 'var(--accent)', marginBottom: 4 }}>
              Clarification needed
            </div>
            <div style={{ fontSize: '0.84rem', color: 'var(--text-primary)' }}>{question}</div>
          </div>
        </div>

        {/* Inline reply box */}
        <div style={{ display: 'flex', gap: 8 }}>
          <input
            type="text"
            className="input-field"
            style={{ flex: 1, fontSize: '0.84rem', padding: '7px 12px' }}
            placeholder="Type your clarification…"
            value={answer}
            onChange={(e) => setAnswer(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') handleSubmit() }}
            autoFocus
          />
          <button className="chat-send-btn" onClick={handleSubmit} disabled={!answer.trim()}>
            <Send size={15} />
          </button>
        </div>
      </div>
    </div>
  )
}

// ── SuggestedQuestions ───────────────────────────────────────────────────────
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

// ── ChatInterface (main export) ───────────────────────────────────────────────
export default function ChatInterface({ sessionId, datasetMeta }) {
  const { messages, isLoading, sendQuestion, clearHistory } = useChat()
  const [input, setInput] = useState('')
  const [persona, setPersona] = useState('general')
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
    sendQuestion(sessionId, q, persona)
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  // Find the last agent message (for suggested questions display)
  const lastAgentMsg = [...messages].reverse().find((m) => m.role === 'agent')
  const showSuggested = !isLoading && lastAgentMsg?.suggestedQuestions?.length > 0
  const showClarification = !isLoading && lastAgentMsg?.clarificationNeeded

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', minHeight: 0 }}>
      {/* Memory banner */}
      {messages.length > 0 && (
        <div className="memory-banner">
          <Brain size={14} />
          Memory active — agent remembers last {Math.min(Math.floor(messages.length / 2), 4)} question{messages.length > 2 ? 's' : ''}
        </div>
      )}

      {/* Chat feed */}
      <div ref={feedRef} className="chat-feed" style={{ flex: 1, overflowY: 'auto' }}>
        {messages.length === 0 ? (
          /* Hero / empty state */
          <div className="chat-hero">
            <h1 className="chat-hero-title">
              <span className="gradient-text">Ask anything about your data</span>
            </h1>
            <p className="chat-hero-subtitle">
              I can analyze, visualize, and discover insights from your dataset. Try a question below.
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
        ) : (
          /* Message thread */
          messages.map((msg) => {
            // Render clarification card instead of normal bubble when flagged
            if (msg.role === 'agent' && msg.clarificationNeeded) {
              return (
                <ClarificationCard
                  key={msg.id}
                  question={msg.clarificationQuestion}
                  onAnswer={(answer) => sendQuestion(sessionId, answer, persona)}
                />
              )
            }
            return <MessageBubble key={msg.id} message={msg} />
          })
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

      {/* Input bar */}
      <div className="chat-input-bar">
        {/* Persona selector (left side) */}
        <PersonaSelector value={persona} onChange={setPersona} />

        {/* Clear history icon */}
        {messages.length > 0 && (
          <button className="btn-icon" onClick={clearHistory} title="Clear history">
            <Trash2 size={16} />
          </button>
        )}

        <textarea
          className="input-field"
          placeholder="Ask a question about your data…"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          rows={1}
        />
        <button
          className="chat-send-btn"
          onClick={() => handleSend()}
          disabled={!input.trim() || isLoading}
        >
          <Send size={18} />
        </button>
      </div>
    </div>
  )
}
