import React from 'react'
import { AlertCircle, AlertTriangle, Info, ShieldAlert } from 'lucide-react'

const SEVERITY_COLORS = {
  critical: { bg: 'bg-[rgba(204,145,102,0.06)]', border: 'border-[rgba(204,145,102,0.2)]', text: 'text-[var(--color-ember-gold)]', icon: ShieldAlert },
  high: { bg: 'bg-[rgba(204,145,102,0.06)]', border: 'border-[rgba(204,145,102,0.2)]', text: 'text-[var(--color-ember-gold)]', icon: AlertCircle },
  medium: { bg: 'bg-[rgba(255,255,255,0.02)]', border: 'border-[var(--border-subtle)]', text: 'text-[var(--color-silver)]', icon: AlertTriangle },
  low: { bg: 'bg-[rgba(255,255,255,0.02)]', border: 'border-[var(--border-subtle)]', text: 'text-[var(--color-silver)]', icon: Info },
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
      className={`p-5 border ${config.border} ${config.bg} flex gap-4 transition-all duration-200`}
      style={{ borderRadius: 'var(--radius-lg)', boxShadow: 'none' }}
    >
      <div className={`flex-shrink-0 ${config.text} mt-0.5`}>
        <Icon size={22} />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap mb-1">
          <h4 className="text-sm font-semibold text-[var(--text-primary)] truncate">
            {ISSUE_TYPE_LABELS[type] || type}
          </h4>
          {column && (
            <span 
              className="px-2 py-0.5 text-xs font-mono"
              style={{
                borderRadius: 'var(--radius-sm)',
                background: 'var(--color-slate)',
                color: 'var(--color-pearl)',
                border: '1px solid var(--border-subtle)'
              }}
            >
              {column}
            </span>
          )}
          <span 
            className={`px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider ${config.bg} ${config.text} border ${config.border}`}
            style={{ borderRadius: 'var(--radius-full)' }}
          >
            {severity}
          </span>
        </div>
        <p className="text-sm text-[var(--text-secondary)] mb-3">{details}</p>
        {recommendation && (
          <div className="p-3 bg-[var(--color-carbon)] border border-[var(--border-subtle)]" style={{ borderRadius: 'var(--radius-sm)' }}>
            <span className="text-xs font-semibold text-[var(--color-ember-gold)] block mb-1 uppercase tracking-wider">Recommendation</span>
            <p className="text-xs text-[var(--text-secondary)] leading-relaxed">{recommendation}</p>
          </div>
        )}
      </div>
    </div>
  )
}
