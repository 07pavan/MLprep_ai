import React, { useState, useEffect } from 'react'
import { getTraces, getTraceDetail, clearTraces } from '../api/client'
import {
  Activity, ChevronDown, ChevronRight, Clock, Cpu, Code2,
  CheckCircle, XCircle, Trash2, RefreshCw, Zap, Brain,
} from 'lucide-react'

const TIER_COLORS = { fast: '#3b82f6', smart: '#a855f7' }
const TIER_LABELS = { fast: '⚡ Fast', smart: '🧠 Smart' }

function TierBadge({ tier }) {
  return (
    <span
      style={{
        display: 'inline-flex', alignItems: 'center', gap: 4,
        padding: '2px 8px', borderRadius: 10, fontSize: '0.7rem', fontWeight: 600,
        background: `${TIER_COLORS[tier] || '#666'}22`,
        color: TIER_COLORS[tier] || '#999',
        border: `1px solid ${TIER_COLORS[tier] || '#666'}44`,
      }}
    >
      {TIER_LABELS[tier] || tier}
    </span>
  )
}

function StatusDot({ success }) {
  if (success === null || success === undefined) return <Clock size={14} style={{ color: 'var(--text-muted)' }} />
  return success
    ? <CheckCircle size={14} style={{ color: '#22c55e' }} />
    : <XCircle size={14} style={{ color: '#ef4444' }} />
}

function EventRow({ event }) {
  const [open, setOpen] = useState(false)
  const data = event.data || {}
  const icon = open ? <ChevronDown size={14} /> : <ChevronRight size={14} />

  const typeColors = {
    llm_call: '#a855f7', llm_response: '#3b82f6',
    code_exec: '#22c55e', error: '#ef4444', warning: '#f59e0b',
    intent: '#06b6d4', spec_valid: '#22c55e', spec_invalid: '#ef4444',
    schema_compressed: '#8b5cf6',
  }

  return (
    <div style={{ borderLeft: `2px solid ${typeColors[event.type] || '#555'}`, paddingLeft: 12, marginBottom: 8 }}>
      <div
        onClick={() => setOpen(!open)}
        style={{
          display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer',
          fontSize: '0.78rem', color: 'var(--text-secondary)',
        }}
      >
        {icon}
        <span style={{ color: typeColors[event.type] || '#999', fontWeight: 600 }}>{event.type}</span>
        <span style={{ color: 'var(--text-muted)' }}>· {event.node}</span>
        {data.latency_ms && (
          <span style={{ marginLeft: 'auto', color: 'var(--text-muted)', fontSize: '0.72rem' }}>
            {data.latency_ms}ms
          </span>
        )}
        {data.tier && <TierBadge tier={data.tier} />}
      </div>

      {open && (
        <div style={{
          marginTop: 6, padding: '8px 12px',
          background: 'var(--surface-alt)', borderRadius: 8,
          fontSize: '0.75rem', color: 'var(--text-secondary)',
          fontFamily: "'JetBrains Mono', monospace",
          whiteSpace: 'pre-wrap', wordBreak: 'break-all',
          maxHeight: 300, overflowY: 'auto',
        }}>
          {data.code && (
            <div style={{ marginBottom: 8 }}>
              <div style={{ color: 'var(--text-muted)', marginBottom: 4, fontFamily: 'var(--font)' }}>Generated Code:</div>
              <div style={{ background: '#0d1117', padding: 10, borderRadius: 6, color: '#e6edf3' }}>
                {data.code}
              </div>
            </div>
          )}
          {data.prompt_preview && (
            <div style={{ marginBottom: 8 }}>
              <div style={{ color: 'var(--text-muted)', marginBottom: 4, fontFamily: 'var(--font)' }}>Prompt Preview:</div>
              <div style={{ opacity: 0.8 }}>{data.prompt_preview}</div>
            </div>
          )}
          {data.error && (
            <div style={{ color: '#ef4444' }}>Error: {data.error}</div>
          )}
          {data.intent && (
            <div>Intent: <strong>{data.intent}</strong> (source: {data.source}){data.reasoning ? ` — ${data.reasoning}` : ''}</div>
          )}
          {data.model && <div>Model: {data.model}</div>}
          {data.selected_cols !== undefined && (
            <div>Columns: {data.selected_cols}/{data.total_cols} selected</div>
          )}
          {data.success !== undefined && !data.code && (
            <div>Success: {data.success ? '✓' : '✗'}</div>
          )}
          {data.attempt !== undefined && <div>Attempt: #{data.attempt}</div>}
          {data.prompt_chars && <div>Prompt size: {data.prompt_chars.toLocaleString()} chars</div>}
          {data.response_chars && <div>Response size: {data.response_chars.toLocaleString()} chars</div>}
          {data.message && !data.error && <div>{data.message}</div>}
        </div>
      )}
    </div>
  )
}

function TraceCard({ trace, onSelect }) {
  return (
    <div
      className="metric-card"
      onClick={() => onSelect(trace.traceId)}
      style={{ cursor: 'pointer', padding: '14px 18px' }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
        <StatusDot success={trace.success} />
        <span style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-primary)', flex: 1 }}>
          {trace.question?.slice(0, 60)}{trace.question?.length > 60 ? '…' : ''}
        </span>
      </div>
      <div style={{ display: 'flex', gap: 12, fontSize: '0.72rem', color: 'var(--text-muted)' }}>
        {trace.intent && (
          <span style={{
            padding: '1px 6px', borderRadius: 6,
            background: 'var(--surface-alt)', color: 'var(--accent)',
          }}>{trace.intent}</span>
        )}
        {trace.durationMs !== null && <span><Clock size={11} /> {trace.durationMs}ms</span>}
        {trace.model && <span><Cpu size={11} /> {trace.model.split('/').pop()}</span>}
        {trace.attempts > 0 && <span>🔄 {trace.attempts} retries</span>}
        <span>{trace.eventCount} events</span>
      </div>
    </div>
  )
}

export default function TraceViewer({ sessionId }) {
  const [traces, setTraces] = useState([])
  const [detail, setDetail] = useState(null)
  const [loading, setLoading] = useState(false)

  const fetchTraces = async () => {
    setLoading(true)
    try {
      const data = await getTraces(50)
      setTraces(data.traces || [])
    } catch (err) {
      console.error('Failed to fetch traces:', err)
    }
    setLoading(false)
  }

  const fetchDetail = async (traceId) => {
    try {
      const data = await getTraceDetail(traceId)
      setDetail(data)
    } catch (err) {
      console.error('Failed to fetch trace detail:', err)
    }
  }

  const handleClear = async () => {
    await clearTraces()
    setTraces([])
    setDetail(null)
  }

  useEffect(() => { fetchTraces() }, [])

  // Detail view
  if (detail) {
    return (
      <div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 20 }}>
          <button className="btn-ghost" onClick={() => setDetail(null)}>← Back</button>
          <h2 style={{ fontSize: '1rem', fontWeight: 600, margin: 0 }}>
            <span className="gradient-text">Trace {detail.traceId}</span>
          </h2>
          <StatusDot success={detail.success} />
          {detail.durationMs !== null && (
            <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
              {detail.durationMs}ms total
            </span>
          )}
        </div>

        <div className="metric-card" style={{ marginBottom: 20, padding: '14px 18px' }}>
          <div style={{ fontSize: '0.85rem', color: 'var(--text-primary)', fontWeight: 500 }}>
            "{detail.question}"
          </div>
        </div>

        <h3 style={{ fontSize: '0.85rem', fontWeight: 600, marginBottom: 12, color: 'var(--text-secondary)' }}>
          <Activity size={14} style={{ verticalAlign: -2 }} /> Event Timeline ({detail.events?.length || 0} events)
        </h3>

        <div style={{ paddingLeft: 4 }}>
          {(detail.events || []).map((evt, i) => (
            <EventRow key={i} event={evt} />
          ))}
        </div>
      </div>
    )
  }

  // List view
  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 20 }}>
        <h1 style={{ margin: 0 }}>
          <span className="gradient-text">Agent Traces</span>
        </h1>
        <button className="btn-ghost" onClick={fetchTraces} disabled={loading}>
          <RefreshCw size={14} className={loading ? 'spinner' : ''} /> Refresh
        </button>
        {traces.length > 0 && (
          <button className="btn-ghost" onClick={handleClear} style={{ color: '#ef4444' }}>
            <Trash2 size={14} /> Clear
          </button>
        )}
      </div>

      {traces.length === 0 ? (
        <div className="chat-hero">
          <Activity size={48} style={{ color: 'var(--text-muted)', marginBottom: 16 }} />
          <h2 className="chat-hero-title">
            <span className="gradient-text">No Traces Yet</span>
          </h2>
          <p className="chat-hero-subtitle">
            Ask a question in the Chat tab. Every query will be traced here with full internal details —
            prompts, generated code, model latency, self-correction retries, and more.
          </p>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {traces.map((t) => (
            <TraceCard key={t.traceId} trace={t} onSelect={fetchDetail} />
          ))}
        </div>
      )}
    </div>
  )
}
