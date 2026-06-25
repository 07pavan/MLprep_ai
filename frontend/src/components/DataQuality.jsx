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
      <div className="p-8 text-center text-[#8E9AAF] text-sm bg-[rgba(255,255,255,0.02)] rounded-lg border border-[rgba(255,255,255,0.06)] max-w-lg mx-auto my-12 animate-fade-in">
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
      <div className="p-6 rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-elevated)] text-center max-w-lg mx-auto my-8">
        <h3 className="text-[var(--text-primary)] font-bold mb-2">Inspection Failed</h3>
        <p className="text-[var(--text-secondary)] text-sm">{error}</p>
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
        <div className="p-8 border border-[var(--border-subtle)] bg-[var(--bg-surface)] flex flex-col items-center text-center max-w-xl mx-auto my-8" style={{ borderRadius: 'var(--radius-lg)' }}>
          <div className="p-4 rounded-full bg-[rgba(204,145,102,0.08)] text-[var(--color-ember-gold)] mb-4">
            <CheckCircle2 size={36} />
          </div>
          <h3 className="text-[var(--text-primary)] font-semibold text-lg mb-2">No Issues Detected!</h3>
          <p className="text-[var(--text-secondary)] text-sm leading-relaxed">
            Your dataset is clean and ready for analysis. No missing values, duplicate rows, outlier issues, or type mismatches were found.
          </p>
        </div>
      ) : (
        <div className="space-y-6">
          {/* Summary Banner */}
          <div className="p-6 border border-[var(--border-subtle)] bg-[var(--bg-surface)] flex items-center gap-4" style={{ borderRadius: 'var(--radius-lg)' }}>
            <div className="p-3 rounded-lg bg-[rgba(204,145,102,0.08)] text-[var(--color-ember-gold)]">
              <ShieldAlert size={24} />
            </div>
            <div>
              <h3 className="text-base font-semibold text-[var(--text-primary)]">Quality Scan Completed</h3>
              <p className="text-sm text-[var(--text-secondary)]">
                Found <span className="text-[var(--color-ember-gold)] font-semibold">{total_issues}</span> potential quality issues requiring review.
              </p>
            </div>
          </div>

          {/* Tab Selection */}
          <div className="flex gap-2 border-b border-[var(--border-subtle)] overflow-x-auto pb-1">
            {CATEGORY_TABS.map(({ id, label }) => {
              const count = counts[id] || 0
              if (id !== 'all' && count === 0) return null // Hide tab if no issues

              const isActive = id === activeTab
              return (
                <button
                  key={id}
                  onClick={() => setActiveTab(id)}
                  className="px-4 py-2 text-sm font-medium border-b-2 transition-all duration-150 whitespace-nowrap flex items-center gap-2"
                  style={{
                    borderColor: isActive ? 'var(--color-ember-gold)' : 'transparent',
                    color: isActive ? 'var(--color-ember-gold)' : 'var(--text-secondary)',
                    background: 'none',
                    fontWeight: isActive ? 600 : 500
                  }}
                >
                  {label}
                  <span 
                    className="px-1.5 py-0.2 text-[10px] font-semibold"
                    style={{
                      borderRadius: 'var(--radius-full)',
                      background: isActive ? 'rgba(204, 145, 102, 0.12)' : 'rgba(255, 255, 255, 0.06)',
                      color: isActive ? 'var(--color-ember-gold)' : 'var(--text-secondary)'
                    }}
                  >
                    {count}
                  </span>
                </button>
              )
            })}
          </div>

          {/* Issues List */}
          <div className="grid grid-cols-1 gap-4">
            {filteredIssues.length > 0 ? (
              filteredIssues.map((issue, idx) => (
                <QualityIssueCard key={idx} issue={issue} />
              ))
            ) : (
              <div className="p-6 text-center text-[#8E9AAF] text-sm bg-[rgba(255,255,255,0.01)] rounded-lg border border-[rgba(255,255,255,0.03)]">
                No issues found for this category.
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
