import React, { useState, useEffect, Suspense } from 'react'
import { Sparkles, Play, Loader, AlertCircle, FileText, RefreshCw, BarChart2, ShieldCheck, Brain, History, HelpCircle, Search, SlidersHorizontal } from 'lucide-react'
import { generateVisualizations } from '../api/client'

// Lazy-load the heavy VegaChart component
const VegaChart = React.lazy(() => import('./VegaChart'))

const CATEGORIES = [
  { value: 'general', label: '🧠 General Overview', desc: 'All automatically recommended visualization charts for this dataset.', icon: HelpCircle },
  { value: 'distribution', label: '📊 Distribution', desc: 'Histograms and outlier box plots showing numerical spreads.', icon: BarChart2 },
  { value: 'categorical', label: '🛡️ Categorical', desc: 'Part-to-whole segment comparisons using bar and pie charts.', icon: ShieldCheck },
  { value: 'correlation', label: '⚙️ Correlation', desc: 'Scatter plots and feature collinearity heatmaps.', icon: Brain },
  { value: 'time_series', label: '⏳ Time Series', desc: 'Trend paths, cyclical sequences, and date/time tracking.', icon: History },
  { value: 'quality', label: '🧹 Data Quality', desc: 'Missing value ratios and quality metric progressions.', icon: AlertCircle }
]

const CHART_TYPES = ['all', 'bar', 'pie', 'line', 'histogram', 'scatter', 'heatmap', 'box', 'quality_chart']

export default function VisualizationPanel({ sessionId }) {
  const [activeCategory, setActiveCategory] = useState('general')
  const [selectedChartType, setSelectedChartType] = useState('all')
  const [minConfidence, setMinConfidence] = useState(0.0)
  const [searchQuery, setSearchQuery] = useState('')
  
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState(null)
  
  // Cache of results by category
  const [resultsCache, setResultsCache] = useState({})

  const handleGenerate = async (force = false) => {
    if (!sessionId) return
    // Skip request if we already have it cached and aren't forcing refresh
    if (!force && resultsCache[activeCategory]) {
      return
    }

    setIsLoading(true)
    setError(null)

    try {
      const data = await generateVisualizations(sessionId, activeCategory, 'general')
      if (data && data.success) {
        setResultsCache(prev => ({
          ...prev,
          [activeCategory]: data
        }))
      } else {
        setError(data?.errors?.[0] || 'Failed to generate visualizations. Please try again.')
      }
    } catch (err) {
      console.error(err)
      setError(err.response?.data?.detail || err.message || 'Network error generating dataset visualizations.')
    } finally {
      setIsLoading(false)
    }
  }

  // Fetch when category or session changes
  useEffect(() => {
    handleGenerate(false)
  }, [activeCategory, sessionId])

  const currentResult = resultsCache[activeCategory]
  const rawVisuals = currentResult?.visualizations || []

  // Client-side filtering & searching
  const filteredVisuals = rawVisuals.filter(item => {
    // 1. Chart type filter
    if (selectedChartType !== 'all' && item.chart_type !== selectedChartType) {
      return false
    }

    // 2. Confidence slider matching
    if (item.confidence_score < minConfidence) {
      return false
    }

    // 3. Search text matching
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase()
      const titleMatch = item.title?.toLowerCase().includes(q)
      const descMatch = item.description?.toLowerCase().includes(q)
      const reasonMatch = item.business_reason?.toLowerCase().includes(q)
      return titleMatch || descMatch || reasonMatch
    }

    return true
  })

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24, paddingBottom: 40 }}>
      {/* Header */}
      <div style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'space-between', alignItems: 'flex-start', gap: 16 }}>
        <div>
          <h1 style={{ fontSize: '1.8rem', fontWeight: 700, margin: '0 0 6px 0' }}>
            <span className="gradient-text">AI Auto Visualizations</span>
          </h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.92rem', margin: 0 }}>
            Automatically selects, shapes, and explains the most suitable visualizations for your dataset columns.
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
          <span>{isLoading ? 'Regenerating...' : 'Refresh Charts'}</span>
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
                    onClick={() => {
                      setActiveCategory(cat.value)
                      // Reset local sub-filters when swapping main tabs
                      setSelectedChartType('all')
                    }}
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
                      {cat.label}
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
              {/* Chart Type Filter */}
              <div>
                <label style={{ display: 'block', fontSize: '0.74rem', color: 'var(--text-muted)', marginBottom: 6 }}>Chart Type</label>
                <select
                  value={selectedChartType}
                  onChange={e => setSelectedChartType(e.target.value)}
                  style={{
                    width: '100%', padding: '6px 10px', borderRadius: 6,
                    background: 'var(--bg-glass)', border: '1px solid var(--border-subtle)',
                    color: 'var(--text-primary)', fontSize: '0.82rem'
                  }}
                >
                  {CHART_TYPES.map(type => (
                    <option key={type} value={type}>
                      {type.charAt(0).toUpperCase() + type.slice(1).replace('_', ' ')}
                    </option>
                  ))}
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
              placeholder="Search charts by title, description, or target columns..."
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
              <h3 style={{ fontSize: '0.94rem', fontWeight: 600 }}>Analyzing Schema & Formulating Vega Specs</h3>
              <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)', marginTop: 4 }}>
                Please wait while the system checks distributions, outliers, and applies LLM explanations...
              </p>
            </div>
          )}

          {/* Error display */}
          {!isLoading && error && (
            <div className="card" style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '60px 20px', textAlign: 'center' }}>
              <AlertCircle size={36} style={{ color: 'var(--error)', marginBottom: 16 }} />
              <h3 style={{ fontSize: '0.94rem', fontWeight: 600, color: 'var(--error)' }}>Generation Failed</h3>
              <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)', marginTop: 4, maxWidth: 400 }}>
                {error}
              </p>
              <button
                className="btn-ghost"
                style={{ marginTop: 16, display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.82rem', border: '1px solid var(--border-subtle)', borderRadius: 8, padding: '6px 14px' }}
                onClick={() => handleGenerate(true)}
              >
                <RefreshCw size={14} />
                <span>Retry Generation</span>
              </button>
            </div>
          )}

          {/* Empty Display */}
          {!isLoading && !currentResult && !error && (
            <div className="card" style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '80px 20px', textAlign: 'center', opacity: 0.7 }}>
              <FileText size={48} style={{ color: 'var(--text-muted)', marginBottom: 16 }} />
              <h3 style={{ fontSize: '0.94rem', fontWeight: 600 }}>No Charts Rendered</h3>
              <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)', marginTop: 4, maxWidth: 320 }}>
                Select a category and trigger the proactive AI visualizer to construct charts.
              </p>
            </div>
          )}

          {/* Result Display */}
          {!isLoading && currentResult && !error && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
              
              {/* Category description header */}
              <div className="card" style={{ padding: 16, background: 'rgba(255,255,255,0.02)' }}>
                <p style={{ fontSize: '0.88rem', lineHeight: 1.5, margin: 0, color: 'var(--text-primary)' }}>
                  {CATEGORIES.find(c => c.value === activeCategory)?.desc} Total recommendations in current scope: <strong>{filteredVisuals.length}</strong>.
                </p>
              </div>

              {/* Grid Layout of Visualizations */}
              {filteredVisuals.length > 0 ? (
                <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: 24 }}>
                  {filteredVisuals.map((item) => (
                    <div key={item.visualization_id} className="card" style={{ padding: 24, display: 'flex', flexDirection: 'column', gap: 20 }}>
                      
                      {/* Title and metadata bar */}
                      <div style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'space-between', alignItems: 'center', gap: 12 }}>
                        <h3 style={{ fontSize: '1.1rem', fontWeight: 700, margin: 0, color: 'var(--text-primary)' }}>
                          {item.title}
                        </h3>
                        
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <span style={{
                            fontSize: '0.7rem',
                            background: 'rgba(255,255,255,0.05)',
                            padding: '2px 6px',
                            borderRadius: 4,
                            color: 'var(--text-muted)',
                            textTransform: 'uppercase'
                          }}>
                            {item.chart_type.replace('_', ' ')}
                          </span>
                          
                          <span style={{
                            fontSize: '0.7rem',
                            background: 'rgba(121,40,202,0.12)',
                            color: '#a78bfa',
                            border: '1px solid rgba(121,40,202,0.2)',
                            padding: '2px 6px',
                            borderRadius: 4,
                            fontWeight: 600
                          }}>
                            🎯 {Math.round(item.confidence_score * 100)}% Confidence
                          </span>
                        </div>
                      </div>

                      {/* Interactive Chart Vega Embed */}
                      <div style={{ background: 'rgba(0,0,0,0.2)', borderRadius: 'var(--radius-md)', padding: 16, border: '1px solid var(--border-subtle)' }}>
                        <Suspense fallback={
                          <div style={{ height: 280, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                            <Loader className="spinner" size={24} />
                          </div>
                        }>
                          <VegaChart 
                            spec={item.rendering_config} 
                            source={item.rendering_config?.data?.values ? "auto" : "llm"} 
                          />
                        </Suspense>
                      </div>

                      {/* Description & Explanation tabs/layout */}
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                        <div>
                          <h4 style={{ fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-muted)', margin: '0 0 4px 0', textTransform: 'uppercase' }}>AI Analysis Explanation:</h4>
                          <p style={{ fontSize: '0.86rem', lineHeight: 1.5, margin: 0, color: 'var(--text-secondary)' }}>
                            {item.explanation || item.description}
                          </p>
                        </div>

                        {item.expected_insight && (
                          <div style={{ background: 'rgba(255,0,127,0.02)', padding: '10px 14px', borderRadius: 8, borderLeft: '3px solid var(--accent-1)' }}>
                            <h5 style={{ fontSize: '0.78rem', fontWeight: 650, color: 'var(--accent-1)', margin: '0 0 3px 0' }}>Expected Pattern Insight:</h5>
                            <p style={{ fontSize: '0.82rem', margin: 0, color: 'var(--text-muted)', lineHeight: 1.4 }}>
                              {item.expected_insight}
                            </p>
                          </div>
                        )}

                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, borderTop: '1px solid var(--border-subtle)', paddingTop: 14 }}>
                          <div>
                            <h5 style={{ fontSize: '0.78rem', fontWeight: 600, color: 'var(--text-muted)', margin: '0 0 4px 0' }}>Business Decision Value:</h5>
                            <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', margin: 0, lineHeight: 1.4 }}>
                              {item.business_reason}
                            </p>
                          </div>
                          <div>
                            <h5 style={{ fontSize: '0.78rem', fontWeight: 600, color: 'var(--text-muted)', margin: '0 0 4px 0' }}>Source Attributes:</h5>
                            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 4 }}>
                              {item.columns.map(col => (
                                <span key={col} style={{ background: 'var(--bg-glass)', border: '1px solid var(--border-subtle)', padding: '2px 8px', borderRadius: 4, fontSize: '0.74rem', color: 'var(--text-primary)' }}>
                                  {col}
                                </span>
                              ))}
                            </div>
                          </div>
                        </div>

                      </div>

                    </div>
                  ))}
                </div>
              ) : (
                <div className="card" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '40px 20px', textAlign: 'center', opacity: 0.6 }}>
                  <HelpCircle size={32} style={{ color: 'var(--text-muted)', marginBottom: 10 }} />
                  <h4 style={{ fontSize: '0.88rem', fontWeight: 600, margin: 0 }}>No Matching Recommended Charts</h4>
                  <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginTop: 4 }}>
                    Try relaxing your confidence filters, searching other columns, or regenerating.
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
