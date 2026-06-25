import React, { useState, useEffect } from 'react'
import { listDatasets, activateDataset, deleteDataset } from '../services/mlApi'
import { Trash2, Check, ExternalLink, Calendar, Database, Layers, Upload, Plus, ArrowLeft } from 'lucide-react'

export default function DatasetManagement({ onActivateSuccess, currentDatasetId, onDeleteActiveDataset, onUploadNew, onBack }) {
  const [datasets, setDatasets] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [actioningId, setActioningId] = useState(null)

  const fetchDatasets = async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await listDatasets()
      const sorted = (data || []).sort((a, b) => new Date(b.upload_timestamp) - new Date(a.upload_timestamp))
      setDatasets(sorted)
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to fetch registered datasets')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchDatasets()
  }, [])

  const handleSelect = async (datasetId) => {
    setActioningId(datasetId)
    try {
      const data = await activateDataset(datasetId)
      if (onActivateSuccess) {
        onActivateSuccess(data.sessionId, data.datasetMeta, data.datasetId)
      }
    } catch (err) {
      alert(err.response?.data?.detail || err.message || 'Failed to select active dataset')
    } finally {
      setActioningId(null)
    }
  }

  const handleDelete = async (datasetId, e) => {
    e.stopPropagation()
    if (!window.confirm('Are you sure you want to delete this dataset from the registry?')) return
    setActioningId(datasetId)
    try {
      await deleteDataset(datasetId)
      setDatasets(datasets.filter(d => d.dataset_id !== datasetId))
      if (datasetId === currentDatasetId && onDeleteActiveDataset) {
        onDeleteActiveDataset()
      }
    } catch (err) {
      alert(err.response?.data?.detail || err.message || 'Failed to delete dataset')
    } finally {
      setActioningId(null)
    }
  }

  if (loading) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: 400, gap: 12 }}>
        <div className="spinner" style={{ width: 40, height: 40 }} />
        <span style={{ color: 'var(--color-graphite)', fontSize: '0.875rem' }}>Loading dataset registry…</span>
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
        <h3 style={{ color: 'var(--color-ink)', fontWeight: 700, marginBottom: 8 }}>Error Loading Registry</h3>
        <p style={{ color: 'var(--color-ash)', fontSize: '0.875rem', marginBottom: 16 }}>{error}</p>
        <button
          onClick={fetchDatasets}
          style={{
            padding: '9px 20px', borderRadius: 'var(--radius-full)',
            background: 'var(--color-ink)', color: 'var(--color-white)',
            fontSize: '0.82rem', fontWeight: 600, cursor: 'pointer', border: 'none',
          }}
        >
          Retry
        </button>
      </div>
    )
  }

  return (
    <div style={{ animation: 'fadeSlideUp 0.3s ease-out' }}>
      {/* Page header */}
      <div className="overview-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 8 }}>
          {onBack && (
            <button
              onClick={onBack}
              style={{
                display: 'inline-flex', alignItems: 'center', gap: 6,
                padding: '6px 14px',
                borderRadius: 'var(--radius-full)',
                background: 'var(--color-fog)',
                border: '1px solid rgba(163, 166, 175, 0.4)',
                color: 'var(--color-graphite)',
                fontSize: '0.8rem', fontWeight: 600,
                cursor: 'pointer', transition: 'all 0.15s ease',
                fontFamily: 'inherit',
              }}
              onMouseEnter={e => { e.currentTarget.style.background = 'var(--color-mist)'; e.currentTarget.style.color = 'var(--color-ink)' }}
              onMouseLeave={e => { e.currentTarget.style.background = 'var(--color-fog)'; e.currentTarget.style.color = 'var(--color-graphite)' }}
            >
              <ArrowLeft size={14} />
              Back to Dashboard
            </button>
          )}
        </div>
        <h1><span className="gradient-text">Dataset Registry</span></h1>
        <p>Manage uploaded and processed datasets, review versions, and toggle active working sessions.</p>
      </div>

      {datasets.length === 0 ? (
        /* ── Empty State ─────────────────────────────────────────── */
        <div style={{
          display: 'flex', flexDirection: 'column', alignItems: 'center',
          textAlign: 'center', padding: '64px 40px',
          background: 'var(--color-white)',
          border: '1px solid rgba(163, 166, 175, 0.25)',
          borderRadius: 'var(--radius-lg)',
          maxWidth: 540, margin: '40px auto',
          boxShadow: 'var(--shadow-subtle)',
        }}>
          {/* Icon */}
          <div style={{
            width: 80, height: 80, borderRadius: 'var(--radius-full)',
            background: 'var(--color-apricot)',
            border: '1.5px solid var(--color-apricot-mid)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            marginBottom: 24, color: 'var(--color-rust)',
          }}>
            <Database size={36} />
          </div>

          <h3 style={{
            fontFamily: 'var(--font-serif)', fontWeight: 400, fontSize: '1.5rem',
            color: 'var(--color-ink)', marginBottom: 12, letterSpacing: '-0.015em',
          }}>
            No datasets yet
          </h3>
          <p style={{
            color: 'var(--color-graphite)', fontSize: '0.9rem',
            lineHeight: 1.65, marginBottom: 32, maxWidth: 380,
          }}>
            You haven't uploaded any datasets yet. Upload a CSV, Excel, JSON, or Parquet file to get started with AI-powered analysis.
          </p>

          {/* Primary CTA */}
          <button
            onClick={onUploadNew}
            style={{
              display: 'inline-flex', alignItems: 'center', gap: 8,
              padding: '12px 28px', borderRadius: 'var(--radius-full)',
              background: 'var(--color-ink)', color: 'var(--color-white)',
              fontSize: '0.92rem', fontWeight: 600,
              border: 'none', cursor: 'pointer',
              transition: 'opacity 0.15s ease',
            }}
            onMouseEnter={e => { e.currentTarget.style.opacity = '0.85' }}
            onMouseLeave={e => { e.currentTarget.style.opacity = '1' }}
          >
            <Upload size={17} />
            Upload your first dataset
          </button>

          {/* Supported formats */}
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', justifyContent: 'center', marginTop: 24 }}>
            {['CSV', 'XLSX', 'JSON', 'Parquet'].map(fmt => (
              <span key={fmt} style={{
                padding: '3px 12px', borderRadius: 'var(--radius-full)',
                background: 'var(--color-fog)', border: '1px solid rgba(163, 166, 175, 0.35)',
                fontSize: '0.68rem', fontWeight: 600, color: 'var(--color-graphite)',
                textTransform: 'uppercase', letterSpacing: '0.05em',
              }}>
                {fmt}
              </span>
            ))}
          </div>
        </div>
      ) : (
        /* ── Dataset list ─────────────────────────────────────────── */
        <div>
          {/* Upload new button */}
          <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 20 }}>
            <button
              onClick={onUploadNew}
              style={{
                display: 'inline-flex', alignItems: 'center', gap: 7,
                padding: '9px 20px', borderRadius: 'var(--radius-full)',
                background: 'var(--color-ink)', color: 'var(--color-white)',
                fontSize: '0.82rem', fontWeight: 600,
                border: 'none', cursor: 'pointer',
                transition: 'opacity 0.15s ease',
              }}
              onMouseEnter={e => { e.currentTarget.style.opacity = '0.8' }}
              onMouseLeave={e => { e.currentTarget.style.opacity = '1' }}
            >
              <Plus size={15} /> Upload New
            </button>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: 16 }}>
            {datasets.map((dataset) => {
              const isActive = dataset.dataset_id === currentDatasetId
              const isWorking = actioningId === dataset.dataset_id
              const dateStr = new Date(dataset.upload_timestamp).toLocaleString(undefined, {
                dateStyle: 'medium',
                timeStyle: 'short'
              })

              return (
                <div
                  key={dataset.dataset_id}
                  style={{
                    padding: 24,
                    borderRadius: 'var(--radius-lg)',
                    borderColor: isActive ? 'var(--color-apricot-mid)' : 'rgba(163, 166, 175, 0.25)',
                    borderWidth: isActive ? 2 : 1,
                    borderStyle: 'solid',
                    background: isActive ? 'var(--color-apricot)' : 'var(--color-white)',
                    boxShadow: isActive ? 'var(--shadow-subtle)' : 'var(--shadow-card)',
                    display: 'flex', flexDirection: 'column', gap: 16,
                    transition: 'box-shadow 0.2s ease',
                  }}
                  onMouseEnter={e => { if (!isActive) e.currentTarget.style.boxShadow = 'var(--shadow-subtle)' }}
                  onMouseLeave={e => { if (!isActive) e.currentTarget.style.boxShadow = 'var(--shadow-card)' }}
                >
                  {/* Top row: name + badges + actions */}
                  <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 16, flexWrap: 'wrap' }}>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      {/* Dataset name + badges */}
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', marginBottom: 8 }}>
                        <h3 style={{
                          fontSize: '1rem', fontWeight: 600,
                          color: 'var(--color-ink)', margin: 0,
                          overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                        }}>
                          {dataset.dataset_name}
                        </h3>
                        <span style={{
                          padding: '2px 10px', borderRadius: 'var(--radius-full)',
                          background: 'var(--color-fog)',
                          border: '1px solid rgba(163, 166, 175, 0.35)',
                          fontSize: '0.65rem', fontWeight: 700, textTransform: 'uppercase',
                          letterSpacing: '0.05em', color: 'var(--color-graphite)',
                        }}>
                          {dataset.source}
                        </span>
                        <span style={{
                          padding: '2px 8px', borderRadius: 'var(--radius-sm)',
                          background: 'var(--color-fog)',
                          fontSize: '0.65rem', fontFamily: 'var(--font-mono)',
                          color: 'var(--color-ash)',
                        }}>
                          v{dataset.dataset_version}
                        </span>
                        {isActive && (
                          <span style={{
                            padding: '2px 10px', borderRadius: 'var(--radius-full)',
                            background: 'var(--color-white)',
                            border: '1px solid var(--color-apricot-mid)',
                            fontSize: '0.65rem', fontWeight: 700, textTransform: 'uppercase',
                            letterSpacing: '0.05em', color: 'var(--color-rust)',
                            display: 'flex', alignItems: 'center', gap: 4,
                          }}>
                            <Check size={10} /> Active
                          </span>
                        )}
                      </div>

                      {/* Meta row */}
                      <div style={{
                        display: 'flex', alignItems: 'center', gap: 20,
                        fontSize: '0.78rem', color: 'var(--color-graphite)', flexWrap: 'wrap',
                      }}>
                        <span style={{ display: 'flex', alignItems: 'center', gap: 4, fontVariantNumeric: 'tabular-nums' }}>
                          <Layers size={13} /> {dataset.row_count.toLocaleString()} rows × {dataset.column_count} cols
                        </span>
                        <span>Format: <span style={{ fontFamily: 'var(--font-mono)' }}>{dataset.original_file_type}</span></span>
                        <span>{dataset.memory_usage} MB</span>
                        <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                          <Calendar size={13} /> {dateStr}
                        </span>
                      </div>
                    </div>

                    {/* Actions */}
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexShrink: 0 }}>
                      {/* ML Score */}
                      {dataset.ml_readiness_score !== null && (
                        <div style={{
                          padding: '6px 14px',
                          background: isActive ? 'rgba(255,255,255,0.5)' : 'var(--color-fog)',
                          border: '1px solid rgba(163, 166, 175, 0.35)',
                          borderRadius: 'var(--radius-sm)',
                          display: 'flex', flexDirection: 'column', alignItems: 'center',
                          minWidth: 64,
                        }}>
                          <span style={{ fontSize: '0.58rem', textTransform: 'uppercase', fontWeight: 700, color: 'var(--color-graphite)', letterSpacing: '0.07em' }}>ML</span>
                          <span style={{ fontSize: '0.92rem', fontWeight: 700, color: 'var(--color-rust)', fontVariantNumeric: 'tabular-nums' }}>{dataset.ml_readiness_score}</span>
                        </div>
                      )}

                      {/* Select button */}
                      <button
                        onClick={() => handleSelect(dataset.dataset_id)}
                        disabled={isActive || isWorking}
                        style={{
                          padding: '9px 18px', borderRadius: 'var(--radius-full)',
                          fontSize: '0.8rem', fontWeight: 600,
                          background: isActive ? 'var(--color-white)' : 'var(--color-ink)',
                          color: isActive ? 'var(--color-rust)' : 'var(--color-white)',
                          border: isActive ? '1px solid var(--color-apricot-mid)' : 'none',
                          cursor: isActive ? 'default' : 'pointer',
                          display: 'flex', alignItems: 'center', gap: 6,
                          transition: 'opacity 0.15s ease',
                          opacity: isWorking ? 0.6 : 1,
                        }}
                        onMouseEnter={e => { if (!isActive) e.currentTarget.style.opacity = '0.8' }}
                        onMouseLeave={e => { e.currentTarget.style.opacity = isWorking ? '0.6' : '1' }}
                      >
                        {isWorking ? (
                          <div className="spinner-inline" style={{ width: 13, height: 13 }} />
                        ) : isActive ? (
                          <><Check size={13} /> Active</>
                        ) : (
                          <><ExternalLink size={13} /> Select</>
                        )}
                      </button>

                      {/* Delete button */}
                      <button
                        onClick={(e) => handleDelete(dataset.dataset_id, e)}
                        disabled={isWorking}
                        title="Delete dataset"
                        style={{
                          width: 36, height: 36, borderRadius: 'var(--radius-sm)',
                          display: 'flex', alignItems: 'center', justifyContent: 'center',
                          background: 'transparent',
                          border: '1px solid rgba(163, 166, 175, 0.35)',
                          color: 'var(--color-graphite)',
                          cursor: 'pointer', transition: 'all 0.15s ease',
                          opacity: isWorking ? 0.4 : 1,
                        }}
                        onMouseEnter={e => { e.currentTarget.style.background = 'rgba(192,57,43,0.06)'; e.currentTarget.style.borderColor = 'rgba(192,57,43,0.2)'; e.currentTarget.style.color = '#c0392b' }}
                        onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.borderColor = 'rgba(163, 166, 175, 0.35)'; e.currentTarget.style.color = 'var(--color-graphite)' }}
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
