/**
 * CleaningPlannerPage — Phase 2A Intelligent Data Cleaning Planner
 *
 * READ-ONLY: This page ONLY shows the generated plan.
 * It never modifies the dataset. Execution belongs to Phase 2B.
 */
import React, { useState, useEffect, useCallback } from 'react'
import {
  Brain, Zap, CheckCircle, XCircle, AlertTriangle,
  Loader, ChevronDown, ChevronUp, TrendingUp,
  RefreshCw, Sparkles, Target, Trash2, ArrowRight,
  Lock, Info, ShieldCheck,
} from 'lucide-react'
import { getIntelligentPlan, getIntelligentPlanForDataset } from '../api/client'

// ── Issue type metadata ────────────────────────────────────────────────────────
const ISSUE_META = {
  missing_values:    { label: 'Missing Values',   color: '#f59e0b', bg: 'rgba(245,158,11,0.1)',  border: 'rgba(245,158,11,0.3)',  icon: AlertTriangle },
  duplicate_rows:    { label: 'Duplicate Rows',   color: '#8b5cf6', bg: 'rgba(139,92,246,0.1)', border: 'rgba(139,92,246,0.3)', icon: Trash2 },
  outliers:          { label: 'Outliers',          color: '#ef4444', bg: 'rgba(239,68,68,0.1)',  border: 'rgba(239,68,68,0.3)',  icon: Zap },
  high_cardinality:  { label: 'High Cardinality', color: '#06b6d4', bg: 'rgba(6,182,212,0.1)',  border: 'rgba(6,182,212,0.3)',  icon: Target },
  type_mismatch:     { label: 'Type Mismatch',    color: '#10b981', bg: 'rgba(16,185,129,0.1)', border: 'rgba(16,185,129,0.3)', icon: Brain },
  low_variance:      { label: 'Low Variance',     color: '#64748b', bg: 'rgba(100,116,139,0.1)',border: 'rgba(100,116,139,0.3)',icon: Info },
  skewed_distribution:{ label: 'Skewed Dist.',    color: '#f97316', bg: 'rgba(249,115,22,0.1)', border: 'rgba(249,115,22,0.3)', icon: TrendingUp },
}

// ── Action human labels ────────────────────────────────────────────────────────
const ACTION_LABEL = {
  mean_imputation:    'Fill with mean',
  median_imputation:  'Fill with median (outlier-robust)',
  mode_imputation:    'Fill with mode (most frequent)',
  constant_imputation:'Fill with constant',
  drop_column:        'Drop column',
  remove_duplicates:  'Remove duplicate rows',
  clip_outliers:      'Clip outliers to IQR fence',
  remove_outliers:    'Remove outlier rows',
  target_encoding:    'Apply target encoding',
  frequency_encoding: 'Apply frequency encoding',
  cast_numeric:       'Cast to numeric dtype',
  cast_datetime:      'Cast to datetime dtype',
  log_transform:      'Apply log transform',
  no_action:          'No action needed',
}

// ── Severity colors ────────────────────────────────────────────────────────────
const SEVERITY_STYLE = {
  critical: { color: '#ef4444', bg: 'rgba(239,68,68,0.15)' },
  high:     { color: '#f97316', bg: 'rgba(249,115,22,0.15)' },
  medium:   { color: '#f59e0b', bg: 'rgba(245,158,11,0.15)' },
  low:      { color: '#10b981', bg: 'rgba(16,185,129,0.15)' },
}

// ── Score Ring ─────────────────────────────────────────────────────────────────
function ScoreRing({ score, label, size = 84 }) {
  const radius = (size - 10) / 2
  const circ   = 2 * Math.PI * radius
  const dash   = (Math.min(score, 100) / 100) * circ
  const color  = score >= 80 ? '#10b981' : score >= 60 ? '#f59e0b' : '#ef4444'
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4 }}>
      <div style={{ position: 'relative', width: size, height: size }}>
        <svg width={size} height={size} style={{ transform: 'rotate(-90deg)' }}>
          <circle cx={size/2} cy={size/2} r={radius} fill="none"
            stroke="rgba(255,255,255,0.07)" strokeWidth={7} />
          <circle cx={size/2} cy={size/2} r={radius} fill="none"
            stroke={color} strokeWidth={7}
            strokeDasharray={`${dash} ${circ}`} strokeLinecap="round"
            style={{ transition: 'stroke-dasharray 0.8s ease' }} />
        </svg>
        <div style={{
          position: 'absolute', inset: 0, display: 'flex',
          alignItems: 'center', justifyContent: 'center',
          fontSize: '1.05rem', fontWeight: 700, color,
        }}>{score}</div>
      </div>
      <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>{label}</div>
    </div>
  )
}

// ── Summary Cards ──────────────────────────────────────────────────────────────
function SummaryStrip({ summary }) {
  if (!summary) return null
  const items = [
    { value: summary.total_issues,       label: 'Total Issues',    color: 'var(--text-primary)' },
    { value: summary.critical_issues,    label: 'Critical',        color: SEVERITY_STYLE.critical.color },
    { value: summary.high_risk_issues,   label: 'High Risk',       color: SEVERITY_STYLE.high.color },
    { value: summary.medium_risk_issues, label: 'Medium',          color: SEVERITY_STYLE.medium.color },
    { value: summary.low_risk_issues,    label: 'Low',             color: SEVERITY_STYLE.low.color },
    { value: summary.auto_applicable_count, label: 'Auto-fixable', color: '#06b6d4' },
  ]
  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: 'repeat(auto-fit, minmax(90px, 1fr))',
      gap: 10, marginBottom: 20,
    }}>
      {items.map(({ value, label, color }) => (
        <div key={label} className="metric-card" style={{ padding: '12px 10px', textAlign: 'center' }}>
          <div style={{ fontSize: '1.4rem', fontWeight: 800, color }}>{value}</div>
          <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)', marginTop: 2 }}>{label}</div>
        </div>
      ))}
    </div>
  )
}

// ── Action Card ────────────────────────────────────────────────────────────────
function ActionCard({ action, index }) {
  const meta     = ISSUE_META[action.issue_type] || ISSUE_META.missing_values
  const IssueIcon = meta.icon
  const sevStyle = SEVERITY_STYLE[action.severity] || SEVERITY_STYLE.low
  const actionLabel = ACTION_LABEL[action.recommendation] || action.recommendation
  const confidence = Math.round((action.confidence_score ?? 0) * 100)

  return (
    <div style={{
      display: 'flex', alignItems: 'flex-start', gap: 14,
      padding: '14px 16px',
      background: meta.bg,
      border: `1px solid ${meta.border}`,
      borderRadius: 10,
      transition: 'box-shadow 0.2s ease',
    }}>
      {/* Issue icon */}
      <div style={{
        width: 38, height: 38, borderRadius: 9, flexShrink: 0,
        background: 'rgba(0,0,0,0.2)', border: `1px solid ${meta.border}`,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        color: meta.color,
      }}>
        <IssueIcon size={17} />
      </div>

      {/* Content */}
      <div style={{ flex: 1, minWidth: 0 }}>
        {/* Tags row */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap', marginBottom: 5 }}>
          {/* Issue type badge */}
          <span style={{
            fontSize: '0.68rem', fontWeight: 700, letterSpacing: '0.05em',
            textTransform: 'uppercase', color: meta.color,
            background: 'rgba(0,0,0,0.15)', padding: '2px 7px', borderRadius: 4,
          }}>
            {meta.label}
          </span>

          {/* Severity badge */}
          <span style={{
            fontSize: '0.68rem', fontWeight: 600, textTransform: 'uppercase',
            color: sevStyle.color, background: sevStyle.bg,
            padding: '2px 7px', borderRadius: 4,
          }}>
            {action.severity}
          </span>

          {/* Column name */}
          {action.column_name && (
            <code style={{
              fontSize: '0.72rem', padding: '1px 6px', borderRadius: 4,
              background: 'rgba(255,255,255,0.07)', color: 'var(--text-secondary)',
              border: '1px solid var(--border-subtle)',
            }}>
              {action.column_name}
            </code>
          )}

          {/* Auto/Manual badge */}
          <span style={{
            fontSize: '0.65rem', fontWeight: 600, textTransform: 'uppercase',
            color: action.auto_applicable ? '#10b981' : '#f59e0b',
            background: action.auto_applicable ? 'rgba(16,185,129,0.12)' : 'rgba(245,158,11,0.12)',
            padding: '2px 7px', borderRadius: 4,
            display: 'flex', alignItems: 'center', gap: 3,
          }}>
            {action.auto_applicable ? '⚡ Auto' : '👁 Review'}
          </span>
        </div>

        {/* Recommended action */}
        <div style={{ fontSize: '0.86rem', fontWeight: 700, color: 'var(--text-primary)', marginBottom: 4 }}>
          {actionLabel}
        </div>

        {/* Current state */}
        <div style={{ fontSize: '0.77rem', color: 'var(--text-secondary)', marginBottom: 3 }}>
          <span style={{ color: 'var(--text-muted)', fontWeight: 600 }}>Found: </span>
          {action.current_state}
        </div>

        {/* Reason */}
        <div style={{ fontSize: '0.76rem', color: 'var(--text-muted)', lineHeight: 1.5 }}>
          {action.reason}
        </div>
      </div>

      {/* Confidence */}
      <div style={{
        display: 'flex', flexDirection: 'column', alignItems: 'center',
        flexShrink: 0, gap: 2,
      }}>
        <div style={{
          width: 38, height: 38, borderRadius: '50%',
          background: `conic-gradient(${meta.color} ${confidence * 3.6}deg, rgba(255,255,255,0.08) 0deg)`,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: '0.65rem', fontWeight: 700, color: meta.color,
          position: 'relative',
        }}>
          <div style={{
            width: 28, height: 28, borderRadius: '50%',
            background: 'var(--bg-card)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: '0.65rem', fontWeight: 700,
          }}>
            {confidence}%
          </div>
        </div>
        <div style={{ fontSize: '0.6rem', color: 'var(--text-muted)' }}>conf.</div>
      </div>
    </div>
  )
}

// ── Main Page ──────────────────────────────────────────────────────────────────
export default function CleaningPlannerPage({ sessionId, currentDatasetId }) {
  const [plan, setPlan] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [showAll, setShowAll] = useState(false)

  const fetchPlan = useCallback(async () => {
    if (!sessionId && !currentDatasetId) return
    setLoading(true)
    setError(null)
    try {
      let data
      if (currentDatasetId) {
        data = await getIntelligentPlanForDataset(currentDatasetId)
      } else {
        data = await getIntelligentPlan(sessionId)
      }
      setPlan(data)
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to generate cleaning plan')
    } finally {
      setLoading(false)
    }
  }, [sessionId, currentDatasetId])

  useEffect(() => { fetchPlan() }, [fetchPlan])

  const actions  = plan?.actions  || []
  const summary  = plan?.summary  || null
  const visible  = showAll ? actions : actions.slice(0, 6)

  // ── Loading ────────────────────────────────────────────────────────────────
  if (loading) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 16, padding: '80px 0' }}>
        <div className="spinner" style={{ width: 44, height: 44 }} />
        <div style={{ color: 'var(--text-secondary)', fontSize: '0.88rem' }}>
          Analysing dataset and building intelligent cleaning plan…
        </div>
      </div>
    )
  }

  return (
    <div>

      {/* ── Header ──────────────────────────────────────────────────────────── */}
      <div style={{ marginBottom: 20 }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
          <div>
            <h1 style={{ fontSize: '1.5rem', fontWeight: 700, margin: 0 }}>
              <span className="gradient-text">Intelligent Cleaning Planner</span>
            </h1>
            <p style={{ color: 'var(--text-muted)', fontSize: '0.82rem', margin: '5px 0 0' }}>
              AI-generated recommendations based on data quality analysis · Read-only · Phase 2A
            </p>
          </div>
          <div style={{ display: 'flex', gap: 8, flexShrink: 0 }}>
            {/* Read-only badge */}
            <span style={{
              display: 'flex', alignItems: 'center', gap: 5,
              fontSize: '0.72rem', fontWeight: 700, color: '#10b981',
              background: 'rgba(16,185,129,0.1)', border: '1px solid rgba(16,185,129,0.3)',
              padding: '5px 10px', borderRadius: 6,
            }}>
              <ShieldCheck size={12} /> Plan Only · No Data Modified
            </span>
            <button
              className="btn-secondary"
              onClick={fetchPlan}
              style={{ display: 'flex', alignItems: 'center', gap: 6 }}
            >
              <RefreshCw size={13} /> Regenerate
            </button>
          </div>
        </div>
      </div>

      {/* ── Error ───────────────────────────────────────────────────────────── */}
      {error && (
        <div className="error-card" style={{ marginBottom: 20, display: 'flex', gap: 8, alignItems: 'center' }}>
          <XCircle size={16} /> {error}
        </div>
      )}

      {/* ── Score comparison ─────────────────────────────────────────────────── */}
      {summary && (
        <div className="glass-card" style={{ padding: '18px 20px', marginBottom: 20 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 24, flexWrap: 'wrap' }}>
            <ScoreRing score={summary.overall_quality_score} label="Current Score" />
            <ArrowRight size={18} color="var(--text-muted)" />
            <ScoreRing score={summary.estimated_score_after_cleaning} label="Estimated After" />
            {summary.estimated_score_after_cleaning > summary.overall_quality_score && (
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: '#10b981', fontWeight: 700, fontSize: '1.1rem' }}>
                <TrendingUp size={18} />
                +{summary.estimated_score_after_cleaning - summary.overall_quality_score} pts estimated gain
              </div>
            )}
            <div style={{ marginLeft: 'auto' }}>
              <div style={{ fontSize: '2rem', fontWeight: 900, color: 'var(--text-primary)', lineHeight: 1 }}>
                {summary.quality_grade}
              </div>
              <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Current Grade</div>
            </div>
          </div>
        </div>
      )}

      {/* ── Summary strip ────────────────────────────────────────────────────── */}
      {summary && <SummaryStrip summary={summary} />}

      {/* ── Empty plan ───────────────────────────────────────────────────────── */}
      {!loading && actions.length === 0 && !error && (
        <div style={{
          background: 'rgba(16,185,129,0.06)', border: '1px solid rgba(16,185,129,0.2)',
          borderRadius: 12, padding: '40px 24px', textAlign: 'center',
        }}>
          <CheckCircle size={44} color="#10b981" style={{ margin: '0 auto 12px' }} />
          <div style={{ fontWeight: 700, fontSize: '1.1rem', color: '#10b981', marginBottom: 6 }}>
            Your dataset is clean!
          </div>
          <div style={{ color: 'var(--text-muted)', fontSize: '0.84rem' }}>
            No cleaning recommendations were generated. Your dataset is ready for ML.
          </div>
        </div>
      )}

      {/* ── Actions list ─────────────────────────────────────────────────────── */}
      {actions.length > 0 && (
        <>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14, flexWrap: 'wrap', gap: 8 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <Sparkles size={15} color="var(--accent-1)" />
              <span style={{ fontSize: '0.9rem', fontWeight: 600 }}>
                {actions.length} recommendation{actions.length !== 1 ? 's' : ''} generated
              </span>
              <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                · {summary?.auto_applicable_count ?? 0} auto-fixable · {(actions.length - (summary?.auto_applicable_count ?? 0))} require review
              </span>
            </div>
            <div style={{
              fontSize: '0.72rem', color: 'var(--text-muted)',
              display: 'flex', alignItems: 'center', gap: 4,
            }}>
              <Lock size={11} /> Phase 2B will execute these steps
            </div>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginBottom: 12 }}>
            {visible.map((action, i) => (
              <ActionCard key={action.action_id || i} action={action} index={i} />
            ))}
          </div>

          {actions.length > 6 && (
            <button
              className="btn-ghost"
              onClick={() => setShowAll(v => !v)}
              style={{ width: '100%', justifyContent: 'center', marginBottom: 20, gap: 6 }}
            >
              {showAll
                ? <><ChevronUp size={14} /> Show less</>
                : <><ChevronDown size={14} /> Show {actions.length - 6} more recommendations</>
              }
            </button>
          )}

          {/* Phase 2B notice */}
          <div style={{
            display: 'flex', alignItems: 'center', gap: 12,
            padding: '14px 18px',
            background: 'rgba(139,92,246,0.06)', border: '1px solid rgba(139,92,246,0.2)',
            borderRadius: 10, marginTop: 4,
          }}>
            <Lock size={18} color="#8b5cf6" style={{ flexShrink: 0 }} />
            <div>
              <div style={{ fontSize: '0.84rem', fontWeight: 600, color: '#8b5cf6', marginBottom: 2 }}>
                Phase 2B — Cleaning Execution (coming next)
              </div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                Review the plan above, then use the Data Cleaning page to selectively apply these steps and create a cleaned dataset version.
              </div>
            </div>
          </div>
        </>
      )}

      {/* ── Plan metadata ─────────────────────────────────────────────────────── */}
      {plan && (
        <div style={{ marginTop: 20, display: 'flex', gap: 16, flexWrap: 'wrap' }}>
          {[
            { label: 'Plan ID', value: plan.plan_id?.slice(0, 8) + '…' },
            { label: 'Phase', value: plan.phase },
            { label: 'Generated', value: plan.generated_at ? new Date(plan.generated_at).toLocaleTimeString() : '—' },
            { label: 'Read-only', value: plan.readonly ? 'Yes ✓' : 'No' },
          ].map(({ label, value }) => (
            <div key={label} style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
              <span style={{ fontWeight: 600 }}>{label}: </span>{value}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
