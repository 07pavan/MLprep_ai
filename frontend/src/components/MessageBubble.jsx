import React, { useState } from 'react'
import { ChevronDown, ChevronUp, Code, AlertTriangle } from 'lucide-react'
import DataTable from './DataTable'
import VegaChart from './VegaChart'
import InsightCard from './InsightCard'

// Intent colour map (for v2 compatibility)
const INTENT_COLORS = {
  analysis_only:              { bg: '#3b82f622', fg: '#60a5fa', label: 'Analysis' },
  analysis_and_visualization: { bg: '#a855f722', fg: '#c084fc', label: 'Visualization' },
  insights:                   { bg: '#22c55e22', fg: '#4ade80', label: 'Insights' },
  cleaning_report:            { bg: '#f59e0b22', fg: '#fbbf24', label: 'Cleaning' },
}

function IntentBadge({ intent }) {
  if (!intent || !INTENT_COLORS[intent]) return null
  const { bg, fg, label } = INTENT_COLORS[intent]
  return (
    <span style={{
      display: 'inline-block', padding: '1px 8px', borderRadius: 8,
      background: bg, color: fg, border: `1px solid ${fg}44`,
      fontSize: '0.68rem', fontWeight: 600, marginBottom: 10,
    }}>
      {label}
    </span>
  )
}

export default function MessageBubble({ message }) {
  const {
    role, question, content, success, answer, data, truncation_meta,
    execution_type, execution_time_ms, code, error, timestamp,
    // v2 compatibility fields
    analysis, visualization, insights, intent
  } = message

  const [showCode, setShowCode] = useState(false)
  const [showData, setShowData] = useState(true)

  // ── User Bubble ──────────────────────────────────────────────────────────
  if (role === 'user') {
    const textContent = content || question
    return (
      <div className="message-row user">
        <div className="message-bubble user">
          <div>{textContent}</div>
          <div className="message-timestamp">{formatTime(timestamp)}</div>
        </div>
      </div>
    )
  }

  // ── Agent Bubble ─────────────────────────────────────────────────────────
  // 1. Check if it's a v3 response structure
  const isV3 = (success !== undefined || answer !== undefined)

  if (isV3) {
    return (
      <div className="message-row agent">
        <div className="message-bubble agent" style={{ maxWidth: '92%' }}>
          
          {/* Main Answer text */}
          <div style={{ fontSize: '0.92rem', whiteSpace: 'pre-wrap' }}>{answer}</div>

          {/* Truncation warning banner */}
          {truncation_meta?.truncated && (
            <div style={{
              marginTop: 10,
              padding: '8px 12px',
              borderRadius: 6,
              background: 'rgba(245,158,11,0.08)',
              border: '1px solid rgba(245,158,11,0.2)',
              fontSize: '0.78rem',
              color: 'var(--warning)',
              display: 'flex',
              alignItems: 'center',
              gap: 8,
            }}>
              <AlertTriangle size={14} style={{ flexShrink: 0 }} />
              <span>Results truncated to 500 rows (total records: {truncation_meta.total_rows}).</span>
            </div>
          )}

          {/* Formatted tabular query data */}
          {data && (
            <div style={{ marginTop: 12 }}>
              <button className="collapsible-header" onClick={() => setShowData(!showData)}>
                {showData ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                {showData ? 'Hide result data' : 'Show result data'}
              </button>
              {showData && <DataTable data={data} />}
            </div>
          )}

          {/* Error Message Card */}
          {!success && error && (
            <div className="error-card" style={{ marginTop: 12 }}>
              {error}
            </div>
          )}

          {/* Executed Code (Collapsible) */}
          {code && (
            <div style={{ marginTop: 12 }}>
              <button className="collapsible-header" onClick={() => setShowCode(!showCode)}>
                <Code size={14} />
                {showCode ? 'Hide executed code' : 'Show executed code'}
              </button>
              {showCode && (
                <div className="code-block" style={{ fontFamily: 'var(--font-mono)', fontSize: '0.8rem' }}>
                  {code}
                </div>
              )}
            </div>
          )}

          {/* Execution Metadata metrics */}
          {(execution_type || execution_time_ms !== undefined) && (
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: 12,
              fontSize: '0.72rem',
              color: 'var(--text-secondary)',
              marginTop: 12,
              borderTop: '1px solid var(--border-subtle)',
              paddingTop: 8,
              opacity: 0.8
            }}>
              {execution_type && (
                <span style={{
                  background: execution_type === 'DETERMINISTIC' ? 'rgba(16,185,129,0.08)' : 'rgba(59,130,246,0.08)',
                  color: execution_type === 'DETERMINISTIC' ? 'var(--success)' : 'var(--info)',
                  padding: '2px 6px',
                  borderRadius: 4,
                  fontWeight: 600,
                  border: execution_type === 'DETERMINISTIC' ? '1px solid rgba(16,185,129,0.15)' : '1px solid rgba(59,130,246,0.15)'
                }}>
                  {execution_type}
                </span>
              )}
              {execution_time_ms !== undefined && (
                <span>⏱️ {execution_time_ms}ms</span>
              )}
            </div>
          )}

          <div className="message-timestamp">{formatTime(timestamp)}</div>
        </div>
      </div>
    )
  }

  // 2. v2 Fallback logic (LangGraph workflow)
  const hasAnalysis = analysis?.success && analysis.resultData
  const hasChart    = visualization?.success && visualization.vegaSpec
  const hasInsights = !!insights
  const hasError    = analysis && !analysis.success && analysis.error

  return (
    <div className="message-row agent">
      <div className="message-bubble agent" style={{ maxWidth: '92%' }}>

        <IntentBadge intent={intent} />

        {hasError && (
          <div className="error-card" style={{ marginBottom: 12 }}>{analysis.error}</div>
        )}

        {hasAnalysis && (
          <div>
            <button className="collapsible-header" onClick={() => setShowData(!showData)}>
              {showData ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
              {showData ? 'Hide data' : 'Show data'}
              {analysis.attempts > 1 && (
                <span className="badge badge-warning" style={{ marginLeft: 8 }}>
                  retry {analysis.attempts}
                </span>
              )}
            </button>
            {showData && <DataTable data={analysis.resultData} />}
          </div>
        )}

        {hasChart && (
          <VegaChart
            spec={visualization.vegaSpec}
            source={visualization.source}
            attempts={visualization.attempts}
          />
        )}

        {hasInsights && <InsightCard insights={insights} />}

        {analysis?.code && (
          <div>
            <button className="collapsible-header" onClick={() => setShowCode(!showCode)}>
              <Code size={14} />
              {showCode ? 'Hide code' : 'Show code'}
            </button>
            {showCode && <div className="code-block">{analysis.code}</div>}
          </div>
        )}

        <div className="message-timestamp">{formatTime(timestamp)}</div>
      </div>
    </div>
  )
}

function formatTime(ts) {
  if (!ts) return ''
  const d = new Date(ts)
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}
