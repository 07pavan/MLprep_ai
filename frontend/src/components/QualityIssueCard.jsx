import React from 'react'
import { AlertCircle, AlertTriangle, Info, ShieldAlert } from 'lucide-react'

const SEVERITY_COLORS = {
  critical: {
    bg: '#fbe1d1', border: 'rgba(93, 42, 26, 0.25)', text: '#5d2a1a',
    icon: ShieldAlert, iconBg: 'rgba(93, 42, 26, 0.1)',
  },
  high: {
    bg: '#fbe1d1', border: 'rgba(93, 42, 26, 0.2)', text: '#5d2a1a',
    icon: AlertCircle, iconBg: 'rgba(93, 42, 26, 0.08)',
  },
  medium: {
    bg: '#d3e3fc', border: 'rgba(74, 122, 200, 0.25)', text: '#4a7ac8',
    icon: AlertTriangle, iconBg: 'rgba(74, 122, 200, 0.1)',
  },
  low: {
    bg: '#f7f7f8', border: 'rgba(163, 166, 175, 0.4)', text: '#777b86',
    icon: Info, iconBg: 'rgba(119, 123, 134, 0.08)',
  },
}

const ISSUE_TYPE_LABELS = {
  missing_values: 'Missing Values',
  duplicate_rows: 'Duplicate Rows',
  outliers: 'Outliers',
  high_cardinality: 'High Cardinality',
  type_mismatch: 'Type Mismatch',
}

export default function QualityIssueCard({ issue }) {
  const { type, column, severity, details, recommendation } = issue
  const config = SEVERITY_COLORS[severity] || SEVERITY_COLORS.low
  const Icon = config.icon

  return (
    <div
      style={{
        padding: 20,
        borderRadius: 'var(--radius-lg)',
        background: config.bg,
        border: `1px solid ${config.border}`,
        display: 'flex', gap: 16,
        transition: 'box-shadow 0.2s ease',
        boxShadow: 'var(--shadow-card)',
      }}
      onMouseEnter={e => { e.currentTarget.style.boxShadow = 'var(--shadow-subtle)' }}
      onMouseLeave={e => { e.currentTarget.style.boxShadow = 'var(--shadow-card)' }}
    >
      {/* Icon */}
      <div style={{
        flexShrink: 0, marginTop: 2,
        width: 38, height: 38, borderRadius: 'var(--radius-sm)',
        background: config.iconBg,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        color: config.text,
      }}>
        <Icon size={20} />
      </div>

      {/* Content */}
      <div style={{ flex: 1, minWidth: 0 }}>
        {/* Title row */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', marginBottom: 4 }}>
          <h4 style={{ fontSize: '0.88rem', fontWeight: 600, color: 'var(--color-ink)', margin: 0 }}>
            {ISSUE_TYPE_LABELS[type] || type}
          </h4>

          {column && (
            <span style={{
              padding: '2px 8px',
              borderRadius: 'var(--radius-sm)',
              background: 'rgba(255,255,255,0.6)',
              color: 'var(--color-ash)',
              border: '1px solid rgba(163, 166, 175, 0.35)',
              fontSize: '0.72rem', fontFamily: 'var(--font-mono)',
            }}>
              {column}
            </span>
          )}

          <span style={{
            padding: '2px 10px',
            borderRadius: 'var(--radius-full)',
            background: 'rgba(255,255,255,0.5)',
            border: `1px solid ${config.border}`,
            color: config.text,
            fontSize: '0.65rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em',
          }}>
            {severity}
          </span>
        </div>

        <p style={{ fontSize: '0.84rem', color: 'var(--color-ash)', marginBottom: recommendation ? 12 : 0, lineHeight: 1.6 }}>
          {details}
        </p>

        {recommendation && (
          <div style={{
            padding: '10px 14px',
            borderRadius: 'var(--radius-sm)',
            background: 'rgba(255,255,255,0.65)',
            border: '1px solid rgba(163, 166, 175, 0.3)',
          }}>
            <span style={{
              fontSize: '0.65rem', fontWeight: 700, textTransform: 'uppercase',
              letterSpacing: '0.06em', color: 'var(--color-rust)', display: 'block', marginBottom: 4,
            }}>
              Recommendation
            </span>
            <p style={{ fontSize: '0.8rem', color: 'var(--color-ash)', lineHeight: 1.55, margin: 0 }}>
              {recommendation}
            </p>
          </div>
        )}
      </div>
    </div>
  )
}
