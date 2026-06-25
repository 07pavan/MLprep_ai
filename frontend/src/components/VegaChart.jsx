import React, { useRef, useEffect, useState } from 'react'
import vegaEmbed from 'vega-embed'

export default function VegaChart({ spec, source = 'auto', attempts = 0 }) {
  const containerRef = useRef(null)
  const viewRef = useRef(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!spec || !containerRef.current) return

    setLoading(true)
    setError(null)

    // Clean up previous view
    if (viewRef.current) {
      viewRef.current.finalize()
      viewRef.current = null
    }

    const embedSpec = {
      ...spec,
      config: {
        background: 'transparent',
        axis: {
          labelColor: '#364153',
          titleColor: '#101828',
          gridColor: 'rgba(0, 0, 0, 0.05)',
          domainColor: 'rgba(0, 0, 0, 0.1)',
        },
        legend: {
          labelColor: '#364153',
          titleColor: '#101828',
        },
        title: {
          color: '#101828',
          fontSize: 14,
          font: 'Outfit',
        },
        view: {
          stroke: 'transparent',
        },
        range: {
          category: ['#FF007F', '#7928CA', '#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#ec4899', '#8b5cf6'],
        },
      },
    }

    vegaEmbed(containerRef.current, embedSpec, {
      renderer: 'svg',
      actions: false,
    })
      .then((result) => {
        viewRef.current = result.view
        setLoading(false)
      })
      .catch((err) => {
        setError(err.message || 'Failed to render chart')
        setLoading(false)
      })

    return () => {
      if (viewRef.current) {
        viewRef.current.finalize()
        viewRef.current = null
      }
    }
  }, [spec])

  const sourceBadge = () => {
    if (source === 'auto') return <span className="badge badge-success">⚡ Rule-based</span>
    if (source === 'llm')
      return (
        <span className="badge badge-accent">
          🤖 AI Generated{attempts > 1 ? ` (retry ${attempts})` : ''}
        </span>
      )
    if (source === 'failsafe') return <span className="badge badge-warning">🛡️ Fallback</span>
    return null
  }

  if (!spec) return null

  return (
    <div className="vega-chart-container">
      <div className="vega-source-badge">{sourceBadge()}</div>
      {loading && (
        <div style={{ display: 'flex', justifyContent: 'center', padding: 40 }}>
          <div className="spinner" />
        </div>
      )}
      {error && <div className="error-card">{error}</div>}
      <div ref={containerRef} style={{ opacity: loading ? 0 : 1, transition: 'opacity 0.3s' }} />
    </div>
  )
}
