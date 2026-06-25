import React from 'react'
import { AlertCircle, AlertTriangle, Info, ShieldAlert } from 'lucide-react'

const SEVERITY_COLORS = {
  critical: { bg: 'bg-red-500/10', border: 'border-red-500/25', text: 'text-red-500', icon: ShieldAlert },
  high: { bg: 'bg-orange-500/10', border: 'border-orange-500/25', text: 'text-orange-500', icon: AlertCircle },
  medium: { bg: 'bg-yellow-500/10', border: 'border-yellow-500/25', text: 'text-yellow-500', icon: AlertTriangle },
  low: { bg: 'bg-blue-500/10', border: 'border-blue-500/25', text: 'text-blue-500', icon: Info },
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
    <div className={`p-5 rounded-xl border ${config.border} ${config.bg} flex gap-4 transition-all duration-200 hover:scale-[1.01]`}>
      <div className={`flex-shrink-0 ${config.text} mt-0.5`}>
        <Icon size={22} />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap mb-1">
          <h4 className="text-sm font-semibold text-[#F0F0F8] truncate">
            {ISSUE_TYPE_LABELS[type] || type}
          </h4>
          {column && (
            <span className="px-2 py-0.5 text-xs rounded bg-[rgba(255,255,255,0.06)] text-[#8E9AAF] border border-[rgba(255,255,255,0.06)] font-mono">
              {column}
            </span>
          )}
          <span className={`px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider rounded ${config.bg} ${config.text} border ${config.border}`}>
            {severity}
          </span>
        </div>
        <p className="text-sm text-[#8E9AAF] mb-3">{details}</p>
        {recommendation && (
          <div className="p-3 rounded-lg bg-[rgba(0,0,0,0.2)] border border-[rgba(255,255,255,0.04)]">
            <span className="text-xs font-bold text-black block mb-1 uppercase tracking-wider">Recommendation</span>
            <p className="text-xs text-[#8E9AAF] leading-relaxed">{recommendation}</p>
          </div>
        )}
      </div>
    </div>
  )
}
