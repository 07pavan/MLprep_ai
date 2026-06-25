import React, { useState, useEffect } from 'react'
import { getQualityReport } from '../services/mlApi'
import QualityIssueCard from './QualityIssueCard'
import { AlertCircle, CheckCircle2, ShieldAlert } from 'lucide-react'

const CATEGORY_TABS = [
  { id: 'all', label: 'All Issues' },
  { id: 'missing_values', label: 'Missing Values' },
  { id: 'duplicate_rows', label: 'Duplicates' },
  { id: 'outliers', label: 'Outliers' },
  { id: 'high_cardinality', label: 'High Cardinality' },
  { id: 'type_mismatch', label: 'Type Mismatch' },
]

export default function DataQuality({ sessionId }) {
  if (!sessionId) {
    return (
      <div style={{
        padding: 32, textAlign: 'center', color: 'var(--color-graphite)', fontSize: '0.88rem',
        background: 'var(--color-white)', borderRadius: 'var(--radius-lg)',
        border: '1px solid rgba(163, 166, 175, 0.25)',
        maxWidth: 480, margin: '48px auto',
        boxShadow: 'var(--shadow-card)',
      }}>
        No active dataset. Please upload a dataset file or select one from the Datasets page.
      </div>
    )
  }

  const [report, setReport] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [activeTab, setActiveTab] = useState('all')

  useEffect(() => {
    async function loadQuality() {
      setLoading(true)
      setError(null)
      try {
        const data = await getQualityReport(sessionId)
        setReport(data)
      } catch (err) {
        setError(err.response?.data?.detail || err.message || 'Failed to load quality report')
      } finally {
        setLoading(false)
      }
    }
    loadQuality()
  }, [sessionId])

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[400px] gap-3">
        <div className="spinner" style={{ width: 40, height: 40 }} />
        <span className="text-[#8E9AAF] text-sm">Inspecting data quality...</span>
      </div>
    )
  }

  if (error) {
    return (
      <div style={{
        padding: 24, borderRadius: 'var(--radius-lg)',
        border: '1px solid rgba(163, 166, 175, 0.25)',
        background: 'var(--color-white)',
        textAlign: 'center', maxWidth: 480, margin: '32px auto',
        boxShadow: 'var(--shadow-card)',
      }}>
        <h3 style={{ color: 'var(--color-ink)', fontWeight: 700, marginBottom: 8 }}>Inspection Failed</h3>
        <p style={{ color: 'var(--color-ash)', fontSize: '0.875rem' }}>{error}</p>
      </div>
    )
  }

  if (!report) return null

  const { total_issues, issues } = report

  // Filter issues based on selected tab
  const filteredIssues = activeTab === 'all' 
    ? issues 
    : issues.filter(issue => issue.type === activeTab)

  // Count issues in each tab for badges
  const counts = issues.reduce((acc, curr) => {
    acc[curr.type] = (acc[curr.type] || 0) + 1
    return acc
  }, { all: issues.length })

  return (
    <div className="space-y-8 animate-fade-in">
      <div className="overview-header">
        <h1><span className="gradient-text">Data Quality Report</span></h1>
        <p>Comprehensive scan of missing data, outlier thresholds, duplicate rows, and schema anomalies.</p>
      </div>

      {total_issues === 0 ? (
        <div style={{
          padding: 32, borderRadius: 'var(--radius-lg)',
          background: 'var(--color-white)',
          border: '1px solid rgba(163, 166, 175, 0.25)',
          display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center',
          maxWidth: 520, margin: '32px auto',
          boxShadow: 'var(--shadow-card)',
        }}>
          <div style={{
            padding: 16, borderRadius: 'var(--radius-full)',
            background: 'var(--color-apricot)', color: 'var(--color-rust)', marginBottom: 16,
          }}>
            <CheckCircle2 size={36} />
          </div>
          <h3 style={{ color: 'var(--color-ink)', fontWeight: 600, fontSize: '1.1rem', marginBottom: 8 }}>No Issues Detected!</h3>
          <p style={{ color: 'var(--color-ash)', fontSize: '0.875rem', lineHeight: 1.6, maxWidth: 360 }}>
            Your dataset is clean and ready for analysis. No missing values, duplicate rows, outlier issues, or type mismatches were found.
          </p>
        </div>
      ) : (
        <div className="space-y-6">
          {/* Summary Banner */}
          <div style={{
            padding: 24, borderRadius: 'var(--radius-lg)',
            background: 'var(--color-white)',
            border: '1px solid rgba(163, 166, 175, 0.25)',
            display: 'flex', alignItems: 'center', gap: 16,
            boxShadow: 'var(--shadow-card)',
          }}>
            <div style={{
              padding: 12, borderRadius: 'var(--radius-sm)',
              background: 'var(--color-apricot)', color: 'var(--color-rust)',
            }}>
              <ShieldAlert size={24} />
            </div>
            <div>
              <h3 style={{ fontSize: '0.95rem', fontWeight: 600, color: 'var(--color-ink)' }}>Quality Scan Completed</h3>
              <p style={{ fontSize: '0.84rem', color: 'var(--color-ash)' }}>
                Found <span style={{ color: 'var(--color-rust)', fontWeight: 600 }}>{total_issues}</span> potential quality issues requiring review.
              </p>
            </div>
          </div>

          {/* Tab Selection */}
          <div style={{ display: 'flex', gap: 4, borderBottom: '1px solid rgba(163, 166, 175, 0.3)', overflowX: 'auto', paddingBottom: 1 }}>
            {CATEGORY_TABS.map(({ id, label }) => {
              const count = counts[id] || 0
              if (id !== 'all' && count === 0) return null

              const isActive = id === activeTab
              return (
                <button
                  key={id}
                  onClick={() => setActiveTab(id)}
                  style={{
                    padding: '8px 16px',
                    fontSize: '0.84rem', fontWeight: isActive ? 600 : 500,
                    borderBottom: isActive ? '2px solid var(--color-rust)' : '2px solid transparent',
                    color: isActive ? 'var(--color-rust)' : 'var(--color-graphite)',
                    background: 'none', cursor: 'pointer', fontFamily: 'inherit',
                    display: 'flex', alignItems: 'center', gap: 6,
                    whiteSpace: 'nowrap', transition: 'color 0.15s ease',
                  }}
                >
                  {label}
                  <span style={{
                    padding: '1px 7px', borderRadius: 'var(--radius-full)',
                    background: isActive ? 'var(--color-apricot)' : 'var(--color-mist)',
                    color: isActive ? 'var(--color-rust)' : 'var(--color-graphite)',
                    fontSize: '0.68rem', fontWeight: 700,
                  }}>
                    {count}
                  </span>
                </button>
              )
            })}
          </div>

          {/* Issues List */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: 14 }}>
            {filteredIssues.length > 0 ? (
              filteredIssues.map((issue, idx) => (
                <QualityIssueCard key={idx} issue={issue} />
              ))
            ) : (
              <div style={{
                padding: 24, textAlign: 'center',
                color: 'var(--color-graphite)', fontSize: '0.84rem',
                background: 'var(--color-fog)',
                borderRadius: 'var(--radius-sm)',
                border: '1px solid rgba(163, 166, 175, 0.25)',
              }}>
                No issues found for this category.
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
