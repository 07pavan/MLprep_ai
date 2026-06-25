import React, { useState, useEffect } from 'react'
import { listDatasets, activateDataset, deleteDataset } from '../services/mlApi'
import { Trash2, Check, ExternalLink, Calendar, Database, Layers } from 'lucide-react'

export default function DatasetManagement({ onActivateSuccess, currentDatasetId, onDeleteActiveDataset }) {
  const [datasets, setDatasets] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [actioningId, setActioningId] = useState(null)

  const fetchDatasets = async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await listDatasets()
      // Sort by upload timestamp descending
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
      // data contains: { sessionId, datasetId, datasetMeta }
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
      <div className="flex flex-col items-center justify-center min-h-[400px] gap-3">
        <div className="spinner" style={{ width: 40, height: 40 }} />
        <span className="text-[#8E9AAF] text-sm">Loading dataset registry...</span>
      </div>
    )
  }

  if (error) {
    return (
      <div className="p-6 rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-elevated)] text-center max-w-lg mx-auto my-8 animate-fade-in">
        <h3 className="text-[var(--text-primary)] font-bold mb-2">Error Loading Registry</h3>
        <p className="text-[var(--text-secondary)] text-sm">{error}</p>
        <button onClick={fetchDatasets} className="mt-4 px-4 py-2 bg-[var(--color-paper)] text-[var(--color-inkwell)] font-semibold text-xs hover:opacity-90 transition-opacity" style={{ borderRadius: 'var(--radius-sm)' }}>
          Retry
        </button>
      </div>
    )
  }

  return (
    <div className="space-y-8 animate-fade-in">
      <div className="overview-header">
        <h1><span className="gradient-text">Dataset Registry</span></h1>
        <p>Manage uploaded and processed datasets, review versions, and toggle active working sessions.</p>
      </div>

      {datasets.length === 0 ? (
        <div className="p-12 border border-[var(--border-subtle)] bg-[var(--bg-surface)] flex flex-col items-center text-center max-w-xl mx-auto my-8" style={{ borderRadius: 'var(--radius-lg)' }}>
          <div className="p-4 rounded-full bg-[var(--color-slate)] text-[var(--color-pearl)] mb-4">
            <Database size={36} />
          </div>
          <h3 className="text-[var(--text-primary)] font-semibold text-lg mb-2">Registry is empty</h3>
          <p className="text-[var(--text-secondary)] text-sm leading-relaxed mb-6">
            You haven't registered any datasets yet. Upload a dataset file to create your first registry entry.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-6">
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
                className={`p-6 border transition-all duration-200 flex flex-col md:flex-row md:items-center justify-between gap-6`}
                style={{
                  borderRadius: 'var(--radius-lg)',
                  borderColor: isActive ? 'var(--color-ember-gold)' : 'var(--border-subtle)',
                  background: isActive ? 'var(--color-slate)' : 'var(--bg-surface)',
                  boxShadow: 'none'
                }}
              >
                <div className="space-y-2 min-w-0 flex-1">
                  <div className="flex items-center gap-3 flex-wrap">
                    <h3 className="text-base font-semibold text-[var(--text-primary)] truncate">{dataset.dataset_name}</h3>
                    <span className="px-2 py-0.5 text-[10px] font-semibold uppercase bg-[var(--color-slate)] text-[var(--color-pearl)] border border-[var(--border-subtle)]" style={{ borderRadius: 'var(--radius-sm)' }}>
                      {dataset.source}
                    </span>
                    <span className="px-2 py-0.5 text-[10px] font-mono bg-[var(--color-inkwell)] text-[var(--color-pearl)]" style={{ borderRadius: 'var(--radius-sm)' }}>
                      v{dataset.dataset_version}
                    </span>
                    {isActive && (
                      <span className="px-2 py-0.5 text-[10px] font-semibold uppercase bg-[rgba(204,145,102,0.08)] text-[var(--color-ember-gold)] border border-[rgba(204,145,102,0.2)] flex items-center gap-1" style={{ borderRadius: 'var(--radius-sm)' }}>
                        <Check size={10} /> Active
                      </span>
                    )}
                  </div>

                  <div className="flex items-center gap-6 text-xs text-[var(--text-secondary)] flex-wrap">
                    <span className="flex items-center gap-1 tabular-nums"><Layers size={14} /> {dataset.row_count.toLocaleString()} rows × {dataset.column_count} cols</span>
                    <span>Format: <span className="font-mono">{dataset.original_file_type}</span></span>
                    <span>Size: {dataset.memory_usage} MB</span>
                    <span className="flex items-center gap-1"><Calendar size={14} /> {dateStr}</span>
                  </div>
                </div>

                <div className="flex items-center gap-3 flex-shrink-0">
                  {/* ML Score indicator */}
                  {dataset.ml_readiness_score !== null && (
                    <div className="px-3 py-1.5 bg-[var(--color-carbon)] border border-[var(--border-subtle)] flex flex-col items-center justify-center min-w-[70px]" style={{ borderRadius: 'var(--radius-sm)' }}>
                      <span className="text-[10px] uppercase font-semibold text-[var(--text-secondary)] tracking-wider">ML Score</span>
                      <span className="text-sm font-semibold text-[var(--text-primary)] tabular-nums">{dataset.ml_readiness_score}</span>
                    </div>
                  )}

                  <button
                    onClick={() => handleSelect(dataset.dataset_id)}
                    disabled={isActive || isWorking}
                    className="px-4 py-2 text-xs font-semibold transition-all duration-150 flex items-center gap-1.5"
                    style={{
                      borderRadius: 'var(--radius-sm)',
                      background: isActive 
                        ? 'rgba(204, 145, 102, 0.08)' 
                        : 'var(--color-paper)',
                      color: isActive 
                        ? 'var(--color-ember-gold)' 
                        : 'var(--color-inkwell)',
                      border: isActive
                        ? '1px solid rgba(204, 145, 102, 0.25)'
                        : 'none',
                      cursor: isActive ? 'default' : 'pointer'
                    }}
                  >
                    {isActive ? (
                      <>Selected</>
                    ) : isWorking ? (
                      <div className="spinner-inline" style={{ width: 12, height: 12 }} />
                    ) : (
                      <>
                        <ExternalLink size={12} /> Select
                      </>
                    )}
                  </button>

                  <button
                    onClick={(e) => handleDelete(dataset.dataset_id, e)}
                    disabled={isWorking}
                    className="p-2 border border-[var(--border-subtle)] text-[var(--color-silver)] hover:bg-[var(--bg-glass-hover)] hover:text-[var(--color-paper)] transition-all duration-150 disabled:opacity-50 cursor-pointer"
                    style={{ borderRadius: 'var(--radius-sm)' }}
                    title="Delete dataset"
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
