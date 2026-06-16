import React, { useState } from 'react'
import { HelpCircle, Play, Loader, AlertCircle, FileText, Sparkles, RefreshCw, BarChart2, ShieldCheck, Brain, History } from 'lucide-react'
import { generateExplanation } from '../api/client'

const ASPECTS = [
  { value: 'general', label: '🧠 General Overview', desc: 'A broad summary of the dataset and its key characteristics.', icon: HelpCircle },
  { value: 'profiling', label: '📊 Profiling & Stats', desc: 'Detailed statistics, cardinality, data distributions, and column analysis.', icon: BarChart2 },
  { value: 'quality', label: '🛡️ Data Quality', desc: 'Analysis of missing values, anomalies, outliers, and duplicates.', icon: ShieldCheck },
  { value: 'ml_readiness', label: '⚙️ ML Readiness', desc: 'Evaluation of dataset suitability for model training and recommendations.', icon: Brain },
  { value: 'cleaning_history', label: '⏳ Cleaning History', desc: 'Trace of transformations applied and version progression over time.', icon: History }
]

export default function ExplanationPanel({ sessionId }) {
  const [selectedAspect, setSelectedAspect] = useState('general')
  const [isLoading, setIsLoading] = useState(false)
  const [explanation, setExplanation] = useState(null)
  const [error, setError] = useState(null)

  const handleGenerate = async () => {
    setIsLoading(true)
    setError(null)
    setExplanation(null)

    try {
      const data = await generateExplanation(sessionId, selectedAspect, 'general')
      if (data && data.success) {
        setExplanation(data)
      } else {
        setError(data?.error || 'Failed to generate explanation. Please try again.')
      }
    } catch (err) {
      console.error(err)
      setError(err.response?.data?.detail || err.message || 'Network error generating explanation.')
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24, paddingBottom: 40 }}>
      {/* Header */}
      <div>
        <h1 style={{ fontSize: '1.8rem', fontWeight: 700, marginBottom: 6 }}>
          <span className="gradient-text">AI Dataset Explainer</span>
        </h1>
        <p style={{ color: 'var(--text-secondary)', fontSize: '0.92rem' }}>
          Select an aspect and generate high-level semantic explanations of your data structure and health.
        </p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: 24 }}>
        
        {/* Selection Card */}
        <div className="card" style={{ padding: 20 }}>
          <h2 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: 16, display: 'flex', alignItems: 'center', gap: 8 }}>
            <Sparkles size={16} className="text-accent-1" style={{ color: 'var(--accent-1)' }} />
            <span>Select Explanation Aspect</span>
          </h2>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {ASPECTS.map((aspect) => {
              const Icon = aspect.icon
              const isSelected = selectedAspect === aspect.value
              return (
                <button
                  key={aspect.value}
                  onClick={() => setSelectedAspect(aspect.value)}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 16,
                    padding: '12px 16px',
                    borderRadius: 'var(--radius-md)',
                    border: isSelected ? '1px solid var(--accent-1)' : '1px solid var(--border-subtle)',
                    background: isSelected ? 'rgba(255,0,127,0.06)' : 'var(--bg-glass)',
                    textAlign: 'left',
                    width: '100%',
                    cursor: 'pointer',
                    transition: 'var(--transition)',
                  }}
                  className="aspect-btn"
                >
                  <div style={{
                    width: 36, height: 36, borderRadius: 'var(--radius-sm)',
                    background: isSelected ? 'linear-gradient(135deg, var(--accent-1), var(--accent-2))' : 'var(--border-subtle)',
                    display: 'flex', alignItems: 'center',
                    color: '#fff', flexShrink: 0, justifyContent: 'center'
                  }}>
                    <Icon size={18} />
                  </div>
                  <div>
                    <div style={{ fontWeight: 600, fontSize: '0.88rem', color: isSelected ? 'var(--text-primary)' : 'var(--text-secondary)' }}>
                      {aspect.label}
                    </div>
                    <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                      {aspect.desc}
                    </div>
                  </div>
                </button>
              )
            })}
          </div>

          <button
            className="chat-send-btn"
            style={{
              marginTop: 20, width: '100%', height: 44, borderRadius: 'var(--radius-md)',
              display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
              fontWeight: 600, fontSize: '0.9rem', color: '#fff', border: 'none',
              background: 'linear-gradient(135deg, var(--accent-1), var(--accent-2))',
              cursor: isLoading ? 'not-allowed' : 'pointer'
            }}
            onClick={handleGenerate}
            disabled={isLoading}
          >
            {isLoading ? <Loader className="spinner" size={18} /> : <Play size={16} />}
            <span>{isLoading ? 'Processing Explanation…' : 'Generate Explanation'}</span>
          </button>
        </div>

        {/* Results Card */}
        <div className="card" style={{ padding: 24, minHeight: 200, display: 'flex', flexDirection: 'column' }}>
          
          {/* Empty State */}
          {!isLoading && !explanation && !error && (
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', textAlign: 'center', padding: '40px 20px', opacity: 0.7 }}>
              <FileText size={48} style={{ color: 'var(--text-muted)', marginBottom: 16 }} />
              <h3 style={{ fontSize: '0.94rem', fontWeight: 600, marginBottom: 4 }}>No Explanation Generated</h3>
              <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)', maxWidth: 300 }}>
                Select an aspect and trigger the AI explainer to analyze your dataset structure.
              </p>
            </div>
          )}

          {/* Loading state */}
          {isLoading && (
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', textAlign: 'center', padding: '60px 20px' }}>
              <Loader size={36} className="spinner" style={{ color: 'var(--accent-1)', marginBottom: 16 }} />
              <h3 style={{ fontSize: '0.94rem', fontWeight: 600 }}>Analyzing Dataset Aspects</h3>
              <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)', marginTop: 4 }}>
                Please wait while the AI compiles and summarizes statistical metrics…
              </p>
            </div>
          )}

          {/* Error State */}
          {!isLoading && error && (
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', textAlign: 'center', padding: '40px 20px' }}>
              <AlertCircle size={36} style={{ color: 'var(--error)', marginBottom: 16 }} />
              <h3 style={{ fontSize: '0.94rem', fontWeight: 600, color: 'var(--error)' }}>Failed to Explain Aspect</h3>
              <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)', marginTop: 4, maxWidth: 400 }}>
                {error}
              </p>
              <button
                className="btn-ghost"
                style={{ marginTop: 16, display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.82rem', border: '1px solid var(--border-subtle)', borderRadius: 8, padding: '6px 14px' }}
                onClick={handleGenerate}
              >
                <RefreshCw size={14} />
                <span>Retry Generation</span>
              </button>
            </div>
          )}

          {/* Success / Explanation State */}
          {!isLoading && explanation && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
              
              {/* Metadata row */}
              <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 12, borderBottom: '1px solid var(--border-subtle)', paddingBottom: 12 }}>
                <span style={{
                  background: 'rgba(121,40,202,0.08)',
                  color: 'var(--accent-1)',
                  padding: '2px 8px',
                  borderRadius: 4,
                  fontWeight: 600,
                  fontSize: '0.72rem',
                  border: '1px solid rgba(121,40,202,0.15)'
                }}>
                  {selectedAspect.toUpperCase().replace('_', ' ')}
                </span>
                
                {explanation.confidence && (
                  <span style={{ fontSize: '0.74rem', color: 'var(--text-secondary)' }}>
                    🎯 Confidence: <strong>{Math.round(explanation.confidence * 100)}%</strong>
                  </span>
                )}
                
                {explanation.timestamp && (
                  <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginLeft: 'auto' }}>
                    ⏰ {new Date(explanation.timestamp).toLocaleTimeString()}
                  </span>
                )}
              </div>

              {/* Summary */}
              <div>
                <h3 style={{ fontSize: '0.92rem', fontWeight: 600, color: 'var(--text-primary)', marginBottom: 8 }}>Overview Summary</h3>
                <div style={{
                  fontSize: '0.88rem',
                  lineHeight: 1.6,
                  color: 'var(--text-primary)',
                  background: 'var(--bg-glass)',
                  padding: 16,
                  borderRadius: 'var(--radius-md)',
                  border: '1px solid var(--border-subtle)'
                }}>
                  {explanation.summary}
                </div>
              </div>

              {/* Insights */}
              {explanation.insights && explanation.insights.length > 0 && (
                <div>
                  <h3 style={{ fontSize: '0.92rem', fontWeight: 600, color: 'var(--text-primary)', marginBottom: 10 }}>Key Insights</h3>
                  <ul style={{ display: 'flex', flexDirection: 'column', gap: 8, paddingLeft: 16 }}>
                    {explanation.insights.map((insight, idx) => (
                      <li key={idx} style={{ fontSize: '0.84rem', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
                        {insight}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Sources */}
              {explanation.sources && explanation.sources.length > 0 && (
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 12 }}>
                  <span style={{ fontSize: '0.74rem', color: 'var(--text-muted)' }}>Source Tools:</span>
                  <div style={{ display: 'flex', gap: 6 }}>
                    {explanation.sources.map((src) => (
                      <span
                        key={src}
                        style={{
                          fontSize: '0.68rem',
                          background: 'var(--border-subtle)',
                          color: 'var(--text-secondary)',
                          padding: '2px 6px',
                          borderRadius: 4,
                          border: '1px solid var(--border-subtle)'
                        }}
                      >
                        {src}
                      </span>
                    ))}
                  </div>
                </div>
              )}

            </div>
          )}

        </div>

      </div>
    </div>
  )
}
