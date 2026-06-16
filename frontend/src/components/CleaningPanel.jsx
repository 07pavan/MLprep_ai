import React, { useState, useEffect } from 'react'
import {
  AlertTriangle, CheckCircle, Loader, Download,
  RotateCcw, ShieldCheck, ArrowRight, CheckSquare, Square
} from 'lucide-react'
import {
  getIntelligentPlan,
  executeCleaningPlan,
  resetCleaningSession,
  downloadCleaned
} from '../api/client'

export default function CleaningPanel({ sessionId }) {
  const [plan, setPlan] = useState(null)
  const [options, setOptions] = useState({})
  const [loading, setLoading] = useState(true)
  const [cleaning, setCleaning] = useState(false)
  const [resetting, setResetting] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [successMsg, setSuccessMsg] = useState(null)

  // Fetch plan and quality summary
  const fetchPlan = async () => {
    try {
      const data = await getIntelligentPlan(sessionId)
      setPlan(data)
      // Populate selected actions mapping: default all to true initially
      const initialOptions = {}
      if (data && data.actions) {
        data.actions.forEach((act) => {
          initialOptions[act.action_id] = true
        })
      }
      setOptions(initialOptions)
    } catch (err) {
      setError(err.response?.data?.detail || err.message)
    }
  }

  useEffect(() => {
    if (!sessionId) return
    setLoading(true)
    setError(null)
    setSuccessMsg(null)
    setResult(null)
    fetchPlan().finally(() => setLoading(false))
  }, [sessionId])

  const toggleOption = (actionId) => {
    setOptions((prev) => ({ ...prev, [actionId]: !prev[actionId] }))
  }

  const toggleAll = (select) => {
    const nextOptions = {}
    if (plan && plan.actions) {
      plan.actions.forEach((act) => {
        nextOptions[act.action_id] = select
      })
    }
    setOptions(nextOptions)
  }

  const handleClean = async () => {
    if (!plan) return
    setCleaning(true)
    setError(null)
    setSuccessMsg(null)
    try {
      const selectedIds = Object.keys(options).filter((id) => options[id])
      if (selectedIds.length === 0) {
        throw new Error("Please select at least one recommended action to execute.")
      }
      
      const resData = await executeCleaningPlan({
        sessionId,
        plan,
        action_ids: selectedIds
      })
      
      setResult(resData)
      setSuccessMsg("Intelligent cleaning actions applied successfully!")
      
      // Re-fetch updated plan to show remaining/resolved issues and new quality score
      await fetchPlan()
    } catch (err) {
      setError(err.response?.data?.detail || err.message)
    } finally {
      setCleaning(false)
    }
  }

  const handleReset = async () => {
    setResetting(true)
    setError(null)
    setSuccessMsg(null)
    try {
      await resetCleaningSession(sessionId)
      setResult(null)
      setSuccessMsg("Session reset: Rolled back to original uncleaned dataset.")
      
      // Re-fetch original baseline plan
      await fetchPlan()
    } catch (err) {
      setError(err.response?.data?.detail || err.message)
    } finally {
      setResetting(false)
    }
  }

  const handleDownload = () => {
    downloadCleaned(sessionId)
  }

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', padding: 60 }}>
        <div className="spinner" />
      </div>
    )
  }

  const severityBadge = (score) => {
    if (score >= 90) return <span className="badge badge-success">✓ Quality Grade A</span>
    if (score >= 75) return <span className="badge badge-success">✓ Quality Grade B</span>
    if (score >= 60) return <span className="badge badge-warning">⚠ Quality Grade C</span>
    if (score >= 40) return <span className="badge badge-warning">⚠ Quality Grade D</span>
    return <span className="badge badge-error">⚠ Quality Grade F</span>
  }

  const getSeverityColor = (sev) => {
    if (sev === 'critical' || sev === 'high') return '#ef4444'
    if (sev === 'medium') return '#f59e0b'
    return '#10b981'
  }

  const hasActions = plan?.actions && plan.actions.length > 0
  const selectedCount = Object.values(options).filter(Boolean).length

  return (
    <div>
      <div className="clean-header" style={{ marginBottom: 20 }}>
        <h1 style={{ fontSize: '1.4rem', fontWeight: 700, marginBottom: 8 }}>
          <span className="gradient-text">Intelligent Data Cleaning</span>
        </h1>
        {plan?.summary && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            {severityBadge(plan.summary.overall_quality_score)}
            <span style={{ color: 'var(--text-secondary)', fontSize: '0.86rem' }}>
              Score: <strong>{plan.summary.overall_quality_score} / 100</strong>
            </span>
            <span style={{ color: 'var(--text-muted)', fontSize: '0.84rem' }}>
              • {plan.summary.total_issues} issue{plan.summary.total_issues !== 1 ? 's' : ''} detected
            </span>
          </div>
        )}
      </div>

      {error && <div className="error-card" style={{ marginBottom: 16 }}>{error}</div>}
      {successMsg && (
        <div className="glass-card" style={{
          padding: '10px 16px',
          borderColor: 'rgba(16,185,129,0.3)',
          backgroundColor: 'rgba(16,185,129,0.05)',
          color: '#10b981',
          fontSize: '0.84rem',
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          marginBottom: 16
        }}>
          <CheckCircle size={16} />
          {successMsg}
        </div>
      )}

      {/* Recommended Actions */}
      <div style={{ display: 'flex', justifyContent: 'between', alignItems: 'center', marginBottom: 12 }}>
        <h3 style={{ fontSize: '0.9rem', fontWeight: 600 }}>Recommended Cleaning Actions</h3>
        {hasActions && (
          <div style={{ display: 'flex', gap: 10, fontSize: '0.76rem' }}>
            <button className="btn-link" onClick={() => toggleAll(true)} style={{ background: 'none', border: 'none', color: '#3b82f6', cursor: 'pointer', padding: 0 }}>Select All</button>
            <span style={{ color: 'var(--text-muted)' }}>|</span>
            <button className="btn-link" onClick={() => toggleAll(false)} style={{ background: 'none', border: 'none', color: '#64748b', cursor: 'pointer', padding: 0 }}>Clear All</button>
          </div>
        )}
      </div>

      {!hasActions ? (
        <div className="glass-card" style={{ padding: 24, textAlign: 'center', marginBottom: 20 }}>
          <CheckCircle size={36} color="#10b981" style={{ marginBottom: 8, display: 'inline-block' }} />
          <h3 style={{ fontSize: '0.96rem', fontWeight: 600, color: 'var(--text-primary)' }}>Your dataset is in top shape!</h3>
          <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)', marginTop: 4 }}>
            No remaining data quality recommendations. Everything is clean.
          </p>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12, marginBottom: 20 }}>
          {plan.actions.map((act) => (
            <div key={act.action_id} className="glass-card" style={{
              padding: 14,
              display: 'flex',
              alignItems: 'flex-start',
              gap: 12,
              borderLeft: `3px solid ${getSeverityColor(act.severity)}`
            }}>
              <input
                type="checkbox"
                style={{ marginTop: 4, cursor: 'pointer' }}
                checked={!!options[act.action_id]}
                onChange={() => toggleOption(act.action_id)}
              />
              <div style={{ flex: 1 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                  <span style={{ fontSize: '0.84rem', fontWeight: 600 }}>
                    {act.column_name ? `Column: ${act.column_name}` : 'Dataset Level'}
                  </span>
                  <span className={`badge badge-${
                    act.severity === 'critical' || act.severity === 'high' ? 'error' :
                    act.severity === 'medium' ? 'warning' : 'success'
                  }`} style={{ fontSize: '0.7rem', padding: '1px 6px' }}>
                    {act.severity}
                  </span>
                  {act.auto_applicable && (
                    <span style={{ fontSize: '0.7rem', color: '#10b981', display: 'flex', alignItems: 'center', gap: 2 }}>
                      <ShieldCheck size={12} /> Auto-applicable
                    </span>
                  )}
                </div>
                
                <div style={{ fontSize: '0.8rem', marginTop: 4, color: 'var(--text-primary)' }}>
                  {act.current_state}
                </div>
                
                <div style={{ fontSize: '0.76rem', color: 'var(--text-muted)', marginTop: 2 }}>
                  <strong>Action:</strong> {act.recommendation.replace('_', ' ')} — {act.reason}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Buttons */}
      <div style={{ display: 'flex', gap: 12, marginTop: 20, flexWrap: 'wrap' }}>
        <button
          className="btn-primary"
          onClick={handleClean}
          disabled={cleaning || !hasActions}
        >
          {cleaning ? <><Loader size={16} className="spinner-inline" /> Cleaning…</> : `Apply Selected (${selectedCount})`}
        </button>
        
        <button
          className="btn-secondary"
          onClick={handleReset}
          disabled={resetting || cleaning}
          style={{ display: 'flex', alignItems: 'center', gap: 6 }}
        >
          {resetting ? <Loader size={16} className="spinner-inline" /> : <RotateCcw size={16} />}
          Undo / Reset
        </button>

        <button className="btn-secondary" onClick={handleDownload} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <Download size={16} /> Download CSV
        </button>
      </div>

      {/* Execution Results */}
      {result && (
        <div style={{ marginTop: 28, borderTop: '1px solid var(--border-subtle)', paddingTop: 24 }}>
          <h3 style={{ fontSize: '1.05rem', fontWeight: 700, marginBottom: 12 }}>
            <span className="gradient-text">Execution Summary</span>
          </h3>

          <div className="stat-grid" style={{ marginBottom: 16 }}>
            <div className="metric-card">
              <div className="metric-value">{result.metrics.rowsBefore.toLocaleString()}</div>
              <div className="metric-label">Rows Before</div>
            </div>
            <div className="metric-card">
              <div className="metric-value gradient-text">{result.metrics.rowsAfter.toLocaleString()}</div>
              <div className="metric-label">Rows After</div>
            </div>
            <div className="metric-card">
              <div className="metric-value">{result.metrics.colsBefore}</div>
              <div className="metric-label">Cols Before</div>
            </div>
            <div className="metric-card">
              <div className="metric-value gradient-text">{result.metrics.colsAfter}</div>
              <div className="metric-label">Cols After</div>
            </div>
          </div>
          
          <div className="metric-card" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', padding: 16, marginBottom: 16 }}>
            <span style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>ML Readiness Improvement</span>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginTop: 6 }}>
              <span style={{ fontSize: '1.4rem', fontWeight: 600, color: 'var(--text-secondary)' }}>{result.original_score}</span>
              <ArrowRight size={18} color="var(--text-muted)" />
              <span className="gradient-text" style={{ fontSize: '2.0rem', fontWeight: 800 }}>{result.new_score}</span>
            </div>
          </div>

          <div className="glass-card" style={{ padding: 16 }}>
            <h4 style={{ fontSize: '0.84rem', fontWeight: 600, marginBottom: 8 }}>Audit Log</h4>
            {result.applied_actions && result.applied_actions.length > 0 ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                {result.applied_actions.map((act, i) => (
                  <div key={i} style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: 6 }}>
                    <span style={{ color: '#10b981' }}>✔</span>
                    <span>
                      <strong>{act.action.replace('_', ' ')}</strong> on {act.column ? `column '${act.column}'` : 'dataset level'} — {act.details}
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>No transformations applied.</div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
