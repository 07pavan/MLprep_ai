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
          labelColor: '#777b86',
          titleColor: '#17191c',
          gridColor: 'rgba(163, 166, 175, 0.18)',
          domainColor: 'rgba(163, 166, 175, 0.3)',
        },
        legend: {
          labelColor: '#777b86',
          titleColor: '#17191c',
        },
        title: {
          color: '#17191c',
          fontSize: 14,
          font: 'Source Serif 4, serif',
        },
        view: {
          stroke: 'transparent',
        },
        range: {
          category: ['#5d2a1a', '#4a7ac8', '#777b86', '#a3a6af', '#fbe1d1', '#d3e3fc', '#b45309'],
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
