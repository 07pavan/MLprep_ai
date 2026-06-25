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
          labelColor: '#acafb9',
          titleColor: '#e2e3e9',
          gridColor: 'rgba(46, 48, 56, 0.3)',
          domainColor: 'rgba(46, 48, 56, 0.5)',
        },
        legend: {
          labelColor: '#acafb9',
          titleColor: '#e2e3e9',
        },
        title: {
          color: '#e2e3e9',
          fontSize: 15,
          font: 'Cormorant Garamond, serif',
        },
        view: {
          stroke: 'transparent',
        },
        range: {
          category: ['#cc9166', '#9194a1', '#acafb9', '#e2e3e9', '#5e616e', '#777a88', '#cdcdcd'],
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
