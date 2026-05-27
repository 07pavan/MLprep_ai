import React, { useState, useEffect } from 'react'
import {
  AlertTriangle, CheckCircle, Loader, Download,
  Circle,
} from 'lucide-react'
import { getCleanReport, applyClean, downloadCleaned } from '../api/client'

const CLEAN_OPTIONS = [
  { key: 'fill_missing_numeric', label: 'Fill numeric NaNs (median)' },
  { key: 'fill_missing_categorical', label: "Fill text NaNs ('Unknown')" },
  { key: 'drop_high_missing', label: 'Drop >50% missing columns' },
  { key: 'drop_duplicates', label: 'Remove duplicates' },
  { key: 'drop_constant_cols', label: 'Drop constant columns' },
  { key: 'drop_all_null_cols', label: 'Drop empty columns' },
  { key: 'convert_numeric', label: 'Convert numeric text' },
  { key: 'parse_dates', label: 'Parse dates' },
  { key: 'strip_whitespace', label: 'Strip whitespace' },
  { key: 'standardise_col_names', label: 'Standardise column names' },
]

export default function CleaningPanel({ sessionId }) {
  const [report, setReport] = useState(null)
  const [defaults, setDefaults] = useState({})
  const [options, setOptions] = useState({})
  const [loading, setLoading] = useState(true)
  const [cleaning, setCleaning] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  // Fetch report on mount
  useEffect(() => {
    if (!sessionId) return
    setLoading(true)
    getCleanReport(sessionId)
      .then((data) => {
        setReport(data.report)
        setDefaults(data.suggestedDefaults)
        setOptions(data.suggestedDefaults)
      })
      .catch((err) => setError(err.response?.data?.detail || err.message))
      .finally(() => setLoading(false))
  }, [sessionId])

  const toggleOption = (key) => {
    setOptions((prev) => ({ ...prev, [key]: !prev[key] }))
  }

  const handleClean = async () => {
    setCleaning(true)
    setError(null)
    try {
      const data = await applyClean(sessionId, options)
      setResult(data)
      // Re-fetch report after cleaning
      const updated = await getCleanReport(sessionId)
      setReport(updated.report)
    } catch (err) {
      setError(err.response?.data?.detail || err.message)
    } finally {
      setCleaning(false)
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

  const severityBadge = (severity) => {
    if (severity === 'clean') return <span className="badge badge-success">✓ Clean</span>
    if (severity === 'minor') return <span className="badge badge-warning">⚠ Minor Issues</span>
    return <span className="badge badge-error">⚠ Major Issues</span>
  }

  const issueSeverityIcon = (severity) => {
    if (severity === 'high') return <Circle size={10} fill="#ef4444" color="#ef4444" />
    if (severity === 'medium') return <Circle size={10} fill="#f59e0b" color="#f59e0b" />
    return <Circle size={10} fill="#10b981" color="#10b981" />
  }

  return (
    <div>
      <div className="clean-header">
        <h1 style={{ fontSize: '1.4rem', fontWeight: 700, marginBottom: 8 }}>
          <span className="gradient-text">Data Cleaning</span>
        </h1>
        {report && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            {severityBadge(report.severity)}
            <span style={{ color: 'var(--text-muted)', fontSize: '0.84rem' }}>
              {report.issue_count} issue{report.issue_count !== 1 ? 's' : ''} detected
            </span>
          </div>
        )}
      </div>

      {error && <div className="error-card" style={{ marginBottom: 16 }}>{error}</div>}

      {/* Issues list */}
      {report?.issues?.length > 0 && (
        <div className="glass-card" style={{ padding: 16, marginBottom: 20 }}>
          <h3 style={{ fontSize: '0.9rem', fontWeight: 600, marginBottom: 12 }}>Detected Issues</h3>
          {report.issues.map((issue, i) => (
            <div key={i} style={{
              display: 'flex', alignItems: 'flex-start', gap: 10,
              padding: '8px 0', borderBottom: i < report.issues.length - 1 ? '1px solid var(--border-subtle)' : 'none',
            }}>
              {issueSeverityIcon(issue.severity)}
              <div>
                <div style={{ fontSize: '0.84rem' }}>{issue.description}</div>
                {issue.column && (
                  <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: 2 }}>
                    Column: {issue.column}
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Cleaning options */}
      <h3 style={{ fontSize: '0.9rem', fontWeight: 600, marginBottom: 12 }}>Cleaning Options</h3>
      <div className="clean-options-grid">
        {CLEAN_OPTIONS.map(({ key, label }) => (
          <label key={key} className="clean-option">
            <input
              type="checkbox"
              checked={!!options[key]}
              onChange={() => toggleOption(key)}
            />
            <span>{label}</span>
          </label>
        ))}
      </div>

      <div style={{ display: 'flex', gap: 12, marginTop: 20 }}>
        <button className="btn-primary" onClick={handleClean} disabled={cleaning}>
          {cleaning ? <><Loader size={16} className="spinner-inline" /> Cleaning…</> : 'Apply Cleaning'}
        </button>
        <button className="btn-secondary" onClick={handleDownload}>
          <Download size={16} /> Download CSV
        </button>
      </div>

      {/* Results */}
      {result && (
        <div style={{ marginTop: 24 }}>
          <h3 style={{ fontSize: '0.9rem', fontWeight: 600, marginBottom: 12 }}>Results</h3>

          <div className="stat-grid">
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

          <div className="glass-card" style={{ padding: 16, marginTop: 12 }}>
            <h4 style={{ fontSize: '0.84rem', fontWeight: 600, marginBottom: 8 }}>Audit Log</h4>
            {result.changeLog.map((line, i) => (
              <div key={i} style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', padding: '3px 0' }}>
                {line}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
