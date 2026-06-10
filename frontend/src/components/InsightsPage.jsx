import React, { useState, useCallback } from 'react'
import { Sparkles, RefreshCw, ChevronDown, ChevronUp, Table2, MessageSquarePlus } from 'lucide-react'
import { getInsights } from '../api/client'

// ── Preset insight categories ─────────────────────────────────────────────────
const PRESET_PROMPTS = [
  {
    emoji: '🔍',
    label: 'Full Dataset Insights',
    question: 'Give me the most important patterns, trends, and anomalies in this dataset',
  },
  {
    emoji: '📈',
    label: 'Trends & Anomalies',
    question: 'What are the notable trends and outliers in this dataset?',
  },
  {
    emoji: '❓',
    label: 'Missing Values & Quality',
    question: 'Summarize the data quality issues, missing values, and data completeness',
  },
  {
    emoji: '🏆',
    label: 'Top & Bottom Performers',
    question: 'Who are the top and bottom performers in this dataset?',
  },
  {
    emoji: '🔗',
    label: 'Correlations',
    question: 'What are the strongest correlations between columns in this data?',
  },
  {
    emoji: '📊',
    label: 'Distribution Summary',
    question: 'Describe the distribution and spread of the numeric columns in detail',
  },
]

// ── Single insight bullet card ────────────────────────────────────────────────
function InsightBulletCard({ text, index }) {
  // Strip leading ✦ if present
  const clean = text.startsWith('✦') ? text.slice(1).trim() : text.trim()
  return (
    <div style={{
      display: 'flex',
      alignItems: 'flex-start',
      gap: 14,
      padding: '14px 18px',
      borderRadius: 10,
      background: 'var(--surface)',
      border: '1px solid var(--border)',
      transition: 'border-color 0.2s',
    }}
    onMouseEnter={e => e.currentTarget.style.borderColor = 'var(--accent)'}
    onMouseLeave={e => e.currentTarget.style.borderColor = 'var(--border)'}
    >
      {/* Index badge */}
      <div style={{
        flexShrink: 0,
        width: 28, height: 28,
        borderRadius: '50%',
        background: 'linear-gradient(135deg, var(--accent), #a855f7)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: '0.72rem', fontWeight: 700, color: '#fff',
      }}>
        {index + 1}
      </div>
      <p style={{
        margin: 0,
        fontSize: '0.88rem',
        color: 'var(--text-primary)',
        lineHeight: 1.6,
        fontWeight: 450,
      }}>
        {clean}
      </p>
    </div>
  )
}

// ── Data table (simple, for supporting evidence) ──────────────────────────────
function SupportingDataTable({ data }) {
  if (!Array.isArray(data) || data.length === 0) return null
  const cols = Object.keys(data[0])
  const rows = data.slice(0, 10)

  return (
    <div style={{ overflowX: 'auto', borderRadius: 8, border: '1px solid var(--border)', marginTop: 4 }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.76rem' }}>
        <thead>
          <tr style={{ background: 'var(--surface-alt)' }}>
            {cols.map(c => (
              <th key={c} style={{
                padding: '7px 12px', textAlign: 'left',
                color: 'var(--text-muted)', fontWeight: 600,
                borderBottom: '1px solid var(--border)',
                whiteSpace: 'nowrap',
              }}>{c}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i} style={{ borderBottom: '1px solid var(--border)' }}>
              {cols.map(c => (
                <td key={c} style={{
                  padding: '6px 12px',
                  color: 'var(--text-primary)',
                  fontFamily: 'var(--font-mono, monospace)',
                  fontSize: '0.74rem',
                }}>
                  {row[c] === null || row[c] === undefined ? (
                    <span style={{ color: 'var(--text-muted)', fontStyle: 'italic' }}>null</span>
                  ) : String(row[c])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {data.length > 10 && (
        <div style={{ padding: '6px 12px', fontSize: '0.72rem', color: 'var(--text-muted)' }}>
          Showing 10 of {data.length} rows
        </div>
      )}
    </div>
  )
}

// ── Follow-up question chips ──────────────────────────────────────────────────
function FollowUpChips({ questions, onAsk }) {
  if (!questions || questions.length === 0) return null
  return (
    <div style={{ marginTop: 20 }}>
      <div style={{
        display: 'flex', alignItems: 'center', gap: 6,
        fontSize: '0.76rem', color: 'var(--text-muted)', marginBottom: 10,
      }}>
        <MessageSquarePlus size={13} /> Suggested follow-ups:
      </div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
        {questions.map((q, i) => (
          <button
            key={i}
            className="suggestion-chip"
            style={{ fontSize: '0.78rem' }}
            onClick={() => onAsk(q)}
          >
            {q}
          </button>
        ))}
      </div>
    </div>
  )
}

// ── Results section ───────────────────────────────────────────────────────────
function InsightsResult({ result, onAsk }) {
  const [showData, setShowData] = useState(false)

  // Parse insight bullets — split on newlines, filter ✦ lines, preserve others
  const rawInsights = result.insights || ''
  const bulletLines = rawInsights
    .split('\n')
    .map(l => l.trim())
    .filter(l => l.length > 0 && (l.startsWith('✦') || (l.length > 10 && !l.startsWith('{'))))

  const hasData = result.analysis?.success && Array.isArray(result.analysis.resultData) && result.analysis.resultData.length > 0

  return (
    <div>
      {/* Insight bullets */}
      {bulletLines.length > 0 ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginBottom: 20 }}>
          {bulletLines.map((line, i) => (
            <InsightBulletCard key={i} text={line} index={i} />
          ))}
        </div>
      ) : (
        <div className="error-card" style={{ marginBottom: 16 }}>
          No insight bullets were returned. Check Traces for details.
        </div>
      )}

      {/* Supporting data toggle */}
      {hasData && (
        <div style={{
          borderRadius: 10,
          border: '1px solid var(--border)',
          overflow: 'hidden',
          marginBottom: 16,
        }}>
          <button
            className="collapsible-header"
            style={{ width: '100%', padding: '10px 14px' }}
            onClick={() => setShowData(s => !s)}
          >
            <Table2 size={14} />
            {showData ? 'Hide' : 'Show'} supporting data
            {showData ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
          </button>
          {showData && (
            <div style={{ padding: '0 14px 14px' }}>
              <SupportingDataTable data={result.analysis.resultData} />
            </div>
          )}
        </div>
      )}

      {/* Follow-up chips */}
      <FollowUpChips
        questions={result.suggestedQuestions || []}
        onAsk={onAsk}
      />
    </div>
  )
}

// ── Preset button ─────────────────────────────────────────────────────────────
function PresetButton({ emoji, label, question, active, disabled, onClick }) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      style={{
        cursor: disabled ? 'not-allowed' : 'pointer',
        padding: '14px 16px',
        borderRadius: 10,
        border: `1px solid ${active ? 'var(--accent)' : 'var(--border)'}`,
        background: active ? 'var(--surface-alt)' : 'var(--surface)',
        textAlign: 'left',
        transition: 'all 0.18s',
        opacity: disabled ? 0.55 : 1,
        outline: 'none',
      }}
      onMouseEnter={e => { if (!disabled && !active) e.currentTarget.style.borderColor = 'var(--accent)44' }}
      onMouseLeave={e => { if (!active) e.currentTarget.style.borderColor = 'var(--border)' }}
    >
      <div style={{ fontSize: '1.1rem', marginBottom: 4 }}>{emoji}</div>
      <div style={{ fontWeight: 600, fontSize: '0.84rem', color: 'var(--text-primary)', marginBottom: 3 }}>
        {label}
      </div>
      <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', lineHeight: 1.4 }}>
        {question.slice(0, 55)}…
      </div>
    </button>
  )
}

// ── Main InsightsPage component ───────────────────────────────────────────────
export default function InsightsPage({ sessionId }) {
  const [loading, setLoading]       = useState(false)
  const [result, setResult]         = useState(null)
  const [activeQuestion, setActive] = useState(null)
  const [customQ, setCustomQ]       = useState('')
  const [error, setError]           = useState(null)

  const runInsight = useCallback(async (question) => {
    if (!sessionId || loading) return
    setLoading(true)
    setError(null)
    setResult(null)
    setActive(question)

    try {
      const data = await getInsights(sessionId, question)
      if (data.error && !data.insights) {
        setError(data.error)
      } else {
        setResult(data)
      }
    } catch (err) {
      const msg = err.response?.data?.detail || err.message || 'Something went wrong'
      setError(msg)
    } finally {
      setLoading(false)
    }
  }, [sessionId, loading])

  const handleCustomSubmit = (e) => {
    e.preventDefault()
    const q = customQ.trim()
    if (q) { setCustomQ(''); runInsight(q) }
  }

  return (
    <div style={{ maxWidth: 860, margin: '0 auto' }}>

      {/* Header */}
      <div style={{ marginBottom: 28 }}>
        <h1 style={{ margin: '0 0 6px', fontSize: '1.6rem' }}>
          <span className="gradient-text">Auto Insights</span>
        </h1>
        <p style={{ margin: 0, color: 'var(--text-muted)', fontSize: '0.88rem' }}>
          Select a category or type a custom question. The AI analyst computes real data first, then narrates the findings.
        </p>
      </div>

      {/* Preset grid */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))',
        gap: 10,
        marginBottom: 20,
      }}>
        {PRESET_PROMPTS.map(p => (
          <PresetButton
            key={p.label}
            {...p}
            active={activeQuestion === p.question && !!result}
            disabled={loading}
            onClick={() => runInsight(p.question)}
          />
        ))}
      </div>

      {/* Custom question */}
      <form onSubmit={handleCustomSubmit} style={{ display: 'flex', gap: 8, marginBottom: 28 }}>
        <input
          type="text"
          className="input-field"
          style={{ flex: 1, fontSize: '0.85rem', padding: '10px 14px' }}
          placeholder="Or type a custom insight question…"
          value={customQ}
          onChange={e => setCustomQ(e.target.value)}
          disabled={loading}
        />
        <button
          type="submit"
          className="chat-send-btn"
          style={{ padding: '10px 18px', minWidth: 48 }}
          disabled={!customQ.trim() || loading}
        >
          {loading
            ? <RefreshCw size={16} className="spinner" />
            : <Sparkles size={16} />
          }
        </button>
      </form>

      {/* Divider */}
      <div style={{ borderTop: '1px solid var(--border)', marginBottom: 24 }} />

      {/* Loading */}
      {loading && (
        <div style={{
          display: 'flex', flexDirection: 'column',
          alignItems: 'center', gap: 12, padding: '40px 0',
        }}>
          <div className="spinner" style={{ width: 32, height: 32 }} />
          <div style={{ color: 'var(--text-muted)', fontSize: '0.88rem' }}>
            Analyzing your data and generating insights…
          </div>
          <div style={{ color: 'var(--text-muted)', fontSize: '0.74rem' }}>
            The analyst is running pandas code against your dataset — this may take 10–30 seconds.
          </div>
        </div>
      )}

      {/* Error */}
      {!loading && error && (
        <div className="error-card">⚠ {error}</div>
      )}

      {/* Results */}
      {!loading && result && (
        <InsightsResult
          result={result}
          onAsk={q => { setCustomQ(''); runInsight(q) }}
        />
      )}

      {/* Empty state */}
      {!loading && !result && !error && (
        <div className="chat-hero" style={{ marginTop: 0, paddingTop: 24 }}>
          <Sparkles size={40} style={{ color: 'var(--accent)', opacity: 0.5, marginBottom: 12 }} />
          <p className="chat-hero-subtitle" style={{ maxWidth: 480 }}>
            Pick a category above. The AI will first compute data with pandas, then narrate
            what it found in clear, numbered insight bullets — grounded in your actual values.
          </p>
        </div>
      )}
    </div>
  )
}
