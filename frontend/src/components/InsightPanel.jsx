import React, { useState, useEffect } from 'react'
import { Sparkles, Play, Loader, AlertCircle, FileText, RefreshCw, BarChart2, ShieldCheck, Brain, History, HelpCircle, Search, SlidersHorizontal } from 'lucide-react'
import { generateInsights } from '../api/client'

const CATEGORIES = [
  { value: 'all', label: '🧠 All Insights', desc: 'Complete set of statistical, quality, ML readiness, and lineage findings.', icon: HelpCircle },
  { value: 'statistical', label: '📊 Statistical', desc: 'Distributions, outliers, variance, correlation, and relationships.', icon: BarChart2 },
  { value: 'quality', label: '🛡️ Data Quality', desc: 'Missing value ratios, anomalies, duplicates, and patterns.', icon: ShieldCheck },
  { value: 'ml_readiness', label: '⚙️ ML Readiness', desc: 'Feature suitability, target balance, cardianality, and leakage.', icon: Brain },
  { value: 'business', label: '⏳ Lineage & Business', desc: 'Versions history progress, categories size and variance.', icon: History }
]

export default function InsightPanel({ sessionId }) {
  const [activeCategory, setActiveCategory] = useState('all')
  const [minSeverity, setMinSeverity] = useState('LOW')
  const [minConfidence, setMinConfidence] = useState(0.0)
  const [searchQuery, setSearchQuery] = useState('')
  
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState(null)
  
  // Cache of results by category
  const [resultsCache, setResultsCache] = useState({})

  const handleGenerate = async (force = false) => {
    // If not forcing regeneration and we have cached results for this category, skip network request
    if (!force && resultsCache[activeCategory]) {
      return
    }

    setIsLoading(true)
    setError(null)

    try {
      const insight_type_map = {
        'all': 'general',
        'statistical': 'statistical',
        'quality': 'quality',
        'ml_readiness': 'ml_readiness',
        'business': 'business'
      }
      const type = insight_type_map[activeCategory] || 'general'
      
      const data = await generateInsights(sessionId, type, 'general')
      if (data && data.success) {
        setResultsCache(prev => ({
          ...prev,
          [activeCategory]: data
        }))
      } else {
        setError(data?.error || 'Failed to generate insights. Please try again.')
      }
    } catch (err) {
      console.error(err)
      setError(err.response?.data?.detail || err.message || 'Network error generating dataset insights.')
    } finally {
      setIsLoading(false)
    }
  }

  // Automatically fetch if active category changes and not loaded yet
  useEffect(() => {
    if (sessionId) {
      handleGenerate(false)
    }
  }, [activeCategory, sessionId])

  const currentResult = resultsCache[activeCategory]
  const rawInsights = currentResult?.insights || []

  // Client-side filtering & searching
  const filteredInsights = rawInsights.filter(item => {
    // 1. Severity filter matching
    const severityValues = { 'LOW': 1, 'MEDIUM': 2, 'HIGH': 3, 'CRITICAL': 4 }
    const itemSevVal = severityValues[item.severity?.toUpperCase() || 'LOW'] || 1
    const targetSevVal = severityValues[minSeverity.toUpperCase()] || 1
    if (itemSevVal < targetSevVal) return false

    // 2. Confidence slider matching
    if (item.confidence_score < minConfidence) return false

    // 3. Search text matching
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase()
      const titleMatch = item.title?.toLowerCase().includes(q)
      const descMatch = item.description?.toLowerCase().includes(q)
      return titleMatch || descMatch
    }

    return true
  })

  // Colors for severity indicators
  const getSeverityStyle = (severity) => {
    switch (severity?.toUpperCase()) {
      case 'CRITICAL':
        return { background: 'rgba(239,68,68,0.12)', color: '#f87171', border: '1px solid rgba(239,68,68,0.2)' }
      case 'HIGH':
        return { background: 'rgba(249,115,22,0.12)', color: '#fb923c', border: '1px solid rgba(249,115,22,0.2)' }
      case 'MEDIUM':
        return { background: 'rgba(234,179,8,0.12)', color: '#facc15', border: '1px solid rgba(234,179,8,0.2)' }
      case 'LOW':
      default:
        return { background: 'rgba(34,197,94,0.12)', color: '#4ade80', border: '1px solid rgba(34,197,94,0.2)' }
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24, paddingBottom: 40 }}>
      {/* Header */}
      <div style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'space-between', alignItems: 'flex-start', gap: 16 }}>
        <div>
          <h1 style={{ fontSize: '1.8rem', fontWeight: 700, margin: '0 0 6px 0' }}>
            <span className="gradient-text">Proactive AI Insights</span>
          </h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.92rem', margin: 0 }}>
            Automatically discover data health patterns, statistical anomalies, ML indicators, and business performance metrics.
          </p>
        </div>
        <button
          className="chat-send-btn"
          style={{
            height: 40, padding: '0 18px', borderRadius: 'var(--radius-md)',
            display: 'flex', alignItems: 'center', gap: 8,
            fontWeight: 600, fontSize: '0.88rem', color: '#fff', border: 'none',
            background: 'linear-gradient(135deg, var(--accent-1), var(--accent-2))',
            cursor: isLoading ? 'not-allowed' : 'pointer'
          }}
          onClick={() => handleGenerate(true)}
          disabled={isLoading}
        >
          {isLoading ? <Loader className="spinner" size={16} /> : <Play size={14} />}
          <span>{isLoading ? 'Processing...' : 'Run Proactive Scan'}</span>
        </button>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '280px 1fr', gap: 24 }}>
        
        {/* Navigation Sidebar */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
          
          {/* Category Selector Card */}
          <div className="card" style={{ padding: 16 }}>
            <h3 style={{ fontSize: '0.88rem', fontWeight: 600, marginBottom: 12, color: 'var(--text-primary)' }}>Categories</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {CATEGORIES.map((cat) => {
                const Icon = cat.icon
                const isSelected = activeCategory === cat.value
                return (
                  <button
                    key={cat.value}
                    onClick={() => setActiveCategory(cat.value)}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 12,
                      padding: '10px 12px',
                      borderRadius: 'var(--radius-sm)',
                      border: isSelected ? '1px solid var(--accent-1)' : '1px solid transparent',
                      background: isSelected ? 'rgba(255,0,127,0.05)' : 'transparent',
                      textAlign: 'left',
                      width: '100%',
                      cursor: 'pointer',
                      transition: 'all 0.15s',
                    }}
                  >
                    <Icon size={16} style={{ color: isSelected ? 'var(--accent-1)' : 'var(--text-secondary)' }} />
                    <span style={{ fontWeight: isSelected ? 600 : 500, fontSize: '0.84rem', color: isSelected ? 'var(--text-primary)' : 'var(--text-secondary)' }}>
                      {cat.label.split(' ')[1] || cat.label}
                    </span>
                  </button>
                )
              })}
            </div>
          </div>

          {/* Filtering Card */}
          <div className="card" style={{ padding: 16 }}>
            <h3 style={{ fontSize: '0.88rem', fontWeight: 600, marginBottom: 12, display: 'flex', alignItems: 'center', gap: 6, color: 'var(--text-primary)' }}>
              <SlidersHorizontal size={14} />
              <span>Filters</span>
            </h3>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              {/* Severity Filter */}
              <div>
                <label style={{ display: 'block', fontSize: '0.74rem', color: 'var(--text-muted)', marginBottom: 6 }}>Minimum Severity</label>
                <select
                  value={minSeverity}
                  onChange={e => setMinSeverity(e.target.value)}
                  style={{
                    width: '100%', padding: '6px 10px', borderRadius: 6,
                    background: 'var(--bg-glass)', border: '1px solid var(--border-subtle)',
                    color: 'var(--text-primary)', fontSize: '0.82rem'
                  }}
                >
                  <option value="LOW">LOW</option>
                  <option value="MEDIUM">MEDIUM</option>
                  <option value="HIGH">HIGH</option>
                  <option value="CRITICAL">CRITICAL</option>
                </select>
              </div>

              {/* Confidence Slider */}
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.74rem', color: 'var(--text-muted)', marginBottom: 6 }}>
                  <span>Min Confidence</span>
                  <strong>{Math.round(minConfidence * 100)}%</strong>
                </div>
                <input
                  type="range"
                  min="0.0"
                  max="1.0"
                  step="0.05"
                  value={minConfidence}
                  onChange={e => setMinConfidence(parseFloat(e.target.value))}
                  style={{ width: '100%', accentColor: 'var(--accent-1)' }}
                />
              </div>
            </div>
          </div>

        </div>

        {/* Content Panel */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          
          {/* Search bar */}
          <div className="card" style={{ padding: 10, display: 'flex', alignItems: 'center', gap: 10 }}>
            <Search size={16} style={{ color: 'var(--text-muted)', marginLeft: 6 }} />
            <input
              type="text"
              placeholder="Search insights by title or description..."
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              style={{
                flex: 1, border: 'none', background: 'transparent',
                outline: 'none', color: 'var(--text-primary)', fontSize: '0.85rem'
              }}
            />
          </div>

          {/* Loading display */}
          {isLoading && (
            <div className="card" style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '80px 20px', textAlign: 'center' }}>
              <Loader size={36} className="spinner" style={{ color: 'var(--accent-1)', marginBottom: 16 }} />
              <h3 style={{ fontSize: '0.94rem', fontWeight: 600 }}>Analyzing Dataset Patterns</h3>
              <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)', marginTop: 4 }}>
                Please wait while the AI proactively scans statistical variance, imbalances, and metadata lineage...
              </p>
            </div>
          )}

          {/* Error display */}
          {!isLoading && error && (
            <div className="card" style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '60px 20px', textAlign: 'center' }}>
              <AlertCircle size={36} style={{ color: 'var(--error)', marginBottom: 16 }} />
              <h3 style={{ fontSize: '0.94rem', fontWeight: 600, color: 'var(--error)' }}>Analysis Failed</h3>
              <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)', marginTop: 4, maxWidth: 400 }}>
                {error}
              </p>
              <button
                className="btn-ghost"
                style={{ marginTop: 16, display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.82rem', border: '1px solid var(--border-subtle)', borderRadius: 8, padding: '6px 14px' }}
                onClick={() => handleGenerate(true)}
              >
                <RefreshCw size={14} />
                <span>Retry Scan</span>
              </button>
            </div>
          )}

          {/* Empty Display */}
          {!isLoading && !currentResult && !error && (
            <div className="card" style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '80px 20px', textAlign: 'center', opacity: 0.7 }}>
              <FileText size={48} style={{ color: 'var(--text-muted)', marginBottom: 16 }} />
              <h3 style={{ fontSize: '0.94rem', fontWeight: 600 }}>No Insights Scan Run</h3>
              <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)', marginTop: 4, maxWidth: 320 }}>
                Select a category and trigger the proactive AI scanner to generate analysis cards.
              </p>
            </div>
          )}

          {/* Result Display */}
          {!isLoading && currentResult && !error && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              
              {/* Overall Summary Card */}
              {currentResult.metadata?.summary && (
                <div className="card" style={{ padding: 16, background: 'rgba(255,255,255,0.02)' }}>
                  <h3 style={{ fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-muted)', marginBottom: 6, textTransform: 'uppercase', tracking: '0.05em' }}>Dataset Proactive Summary</h3>
                  <p style={{ fontSize: '0.88rem', lineHeight: 1.5, margin: 0, color: 'var(--text-primary)' }}>
                    {currentResult.metadata.summary}
                  </p>
                </div>
              )}

              {/* Insights List */}
              {filteredInsights.length > 0 ? (
                filteredInsights.map((item) => (
                  <div key={item.insight_id} className="card" style={{ padding: 20, display: 'flex', flexDirection: 'column', gap: 14 }}>
                    
                    {/* Card Title Header */}
                    <div style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'space-between', alignItems: 'center', gap: 12 }}>
                      <h3 style={{ fontSize: '0.96rem', fontWeight: 650, margin: 0, color: 'var(--text-primary)' }}>
                        {item.title}
                      </h3>
                      
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <span style={{
                          fontSize: '0.7rem',
                          background: 'rgba(255,255,255,0.05)',
                          padding: '2px 6px',
                          borderRadius: 4,
                          color: 'var(--text-muted)'
                        }}>
                          {item.category.toUpperCase()}
                        </span>
                        
                        <span style={{
                          fontSize: '0.7rem',
                          padding: '2px 6px',
                          borderRadius: 4,
                          fontWeight: 600,
                          ...getSeverityStyle(item.severity)
                        }}>
                          {item.severity}
                        </span>

                        <span style={{ fontSize: '0.74rem', color: 'var(--text-muted)' }}>
                          🎯 {Math.round(item.confidence_score * 100)}%
                        </span>
                      </div>
                    </div>

                    {/* Card Description */}
                    <p style={{ fontSize: '0.85rem', lineHeight: 1.5, margin: 0, color: 'var(--text-secondary)' }}>
                      {item.description}
                    </p>

                    {/* Recommended actions */}
                    {item.recommended_actions && item.recommended_actions.length > 0 && (
                      <div style={{ borderTop: '1px solid var(--border-subtle)', paddingTop: 10 }}>
                        <h4 style={{ fontSize: '0.78rem', fontWeight: 600, color: 'var(--text-primary)', margin: '0 0 6px 0' }}>Recommended Actions:</h4>
                        <ul style={{ margin: 0, paddingLeft: 16, display: 'flex', flexDirection: 'column', gap: 4 }}>
                          {item.recommended_actions.map((act, idx) => (
                            <li key={idx} style={{ fontSize: '0.78rem', color: 'var(--text-muted)', lineHeight: 1.4 }}>
                              {act}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {/* Sources row */}
                    {item.source_metrics && item.source_metrics.length > 0 && (
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.7rem', color: 'var(--text-muted)' }}>
                        <span>Metrics Source:</span>
                        {item.source_metrics.map(src => (
                          <span key={src} style={{ background: 'var(--border-subtle)', padding: '1px 5px', borderRadius: 3 }}>{src}</span>
                        ))}
                      </div>
                    )}

                  </div>
                ))
              ) : (
                <div className="card" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '40px 20px', textAlign: 'center', opacity: 0.6 }}>
                  <HelpCircle size={32} style={{ color: 'var(--text-muted)', marginBottom: 10 }} />
                  <h4 style={{ fontSize: '0.88rem', fontWeight: 600, margin: 0 }}>No Matching Insights</h4>
                  <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginTop: 4 }}>
                    Try relaxing your severity filters or changing search terms.
                  </p>
                </div>
              )}

            </div>
          )}

        </div>

      </div>
    </div>
  )
}
