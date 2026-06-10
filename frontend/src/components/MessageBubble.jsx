import React, { useState } from 'react'
import { ChevronDown, ChevronUp, Code } from 'lucide-react'
import DataTable from './DataTable'
import VegaChart from './VegaChart'
import InsightCard from './InsightCard'

// Intent colour map — matches orchestrator categories
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
    role, question, analysis, visualization,
    insights, intent, timestamp,
  } = message

  const [showCode, setShowCode] = useState(false)
  const [showData, setShowData] = useState(true)

  // ── User bubble ──────────────────────────────────────────────────────────
  if (role === 'user') {
    return (
      <div className="message-row user">
        <div className="message-bubble user">
          <div>{question}</div>
          <div className="message-timestamp">{formatTime(timestamp)}</div>
        </div>
      </div>
    )
  }

  // ── Agent bubble ─────────────────────────────────────────────────────────
  const hasAnalysis = analysis?.success && analysis.resultData
  const hasChart    = visualization?.success && visualization.vegaSpec
  const hasInsights = !!insights
  const hasError    = analysis && !analysis.success && analysis.error

  return (
    <div className="message-row agent">
      <div className="message-bubble agent" style={{ maxWidth: '92%' }}>

        {/* Intent badge */}
        <IntentBadge intent={intent} />

        {/* Error state */}
        {hasError && (
          <div className="error-card" style={{ marginBottom: 12 }}>{analysis.error}</div>
        )}

        {/* Data table (collapsible) */}
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

        {/* Vega-Lite chart */}
        {hasChart && (
          <VegaChart
            spec={visualization.vegaSpec}
            source={visualization.source}
            attempts={visualization.attempts}
          />
        )}

        {/* Insights */}
        {hasInsights && <InsightCard insights={insights} />}

        {/* Generated code (collapsible) */}
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
