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
      <div className="p-6 rounded-xl border border-red-500/25 bg-red-500/10 text-center max-w-lg mx-auto my-8 animate-fade-in">
        <h3 className="text-red-500 font-bold mb-2">Error Loading Registry</h3>
        <p className="text-[#8E9AAF] text-sm">{error}</p>
        <button onClick={fetchDatasets} className="mt-4 px-4 py-2 bg-red-500 text-white rounded-lg text-xs font-semibold hover:bg-red-600 transition-colors">
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
        <div className="p-12 rounded-xl border border-[rgba(255,255,255,0.06)] bg-[rgba(255,255,255,0.02)] flex flex-col items-center text-center max-w-xl mx-auto my-8">
          <div className="p-4 rounded-full bg-[rgba(255,255,255,0.03)] text-[#8E9AAF] mb-4">
            <Database size={36} />
          </div>
          <h3 className="text-[#F0F0F8] font-bold text-lg mb-2">Registry is empty</h3>
          <p className="text-[#8E9AAF] text-sm leading-relaxed mb-6">
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
                className={`p-6 rounded-xl border transition-all duration-200 flex flex-col md:flex-row md:items-center justify-between gap-6 ${
                  isActive 
                    ? 'border-[#FF007F] bg-[#FF007F]/5 shadow-[0_0_15px_rgba(255,0,127,0.1)]' 
                    : 'border-[rgba(255,255,255,0.06)] bg-[rgba(255,255,255,0.02)] hover:bg-[rgba(255,255,255,0.04)]'
                }`}
              >
                <div className="space-y-2 min-w-0 flex-1">
                  <div className="flex items-center gap-3 flex-wrap">
                    <h3 className="text-base font-bold text-[#F0F0F8] truncate">{dataset.dataset_name}</h3>
                    <span className="px-2 py-0.5 text-[10px] font-bold uppercase rounded bg-[#FF007F]/10 text-[#FF007F] border border-[#FF007F]/20">
                      {dataset.source}
                    </span>
                    <span className="px-2 py-0.5 text-[10px] font-mono rounded bg-[rgba(255,255,255,0.06)] text-[#8E9AAF]">
                      v{dataset.dataset_version}
                    </span>
                    {isActive && (
                      <span className="px-2 py-0.5 text-[10px] font-bold uppercase rounded bg-emerald-500/10 text-emerald-500 border border-emerald-500/20 flex items-center gap-1">
                        <Check size={10} /> Active
                      </span>
                    )}
                  </div>

                  <div className="flex items-center gap-6 text-xs text-[#8E9AAF] flex-wrap">
                    <span className="flex items-center gap-1"><Layers size={14} /> {dataset.row_count.toLocaleString()} rows × {dataset.column_count} cols</span>
                    <span>Format: <span className="font-mono">{dataset.original_file_type}</span></span>
                    <span>Size: {dataset.memory_usage} MB</span>
                    <span className="flex items-center gap-1"><Calendar size={14} /> {dateStr}</span>
                  </div>
                </div>

                <div className="flex items-center gap-3 flex-shrink-0">
                  {/* ML Score indicator */}
                  {dataset.ml_readiness_score !== null && (
                    <div className="px-3 py-1.5 rounded-lg bg-[rgba(0,0,0,0.2)] border border-[rgba(255,255,255,0.04)] flex flex-col items-center justify-center min-w-[70px]">
                      <span className="text-[10px] uppercase font-bold text-[#8E9AAF] tracking-wider">ML Score</span>
                      <span className="text-sm font-extrabold text-[#F0F0F8]">{dataset.ml_readiness_score}</span>
                    </div>
                  )}

                  <button
                    onClick={() => handleSelect(dataset.dataset_id)}
                    disabled={isActive || isWorking}
                    className={`px-4 py-2 rounded-lg text-xs font-bold transition-all duration-150 flex items-center gap-1.5 ${
                      isActive
                        ? 'bg-emerald-500/10 text-emerald-500 border border-emerald-500/20 cursor-default'
                        : 'bg-[#FF007F] hover:bg-[#FF007F]/90 text-white shadow-lg cursor-pointer disabled:opacity-50'
                    }`}
                  >
                    {isActive ? (
                      <>Selected</>
                    ) : isWorking ? (
                      <div className="spinner" style={{ width: 12, height: 12, borderWidth: 2 }} />
                    ) : (
                      <>
                        <ExternalLink size={12} /> Select
                      </>
                    )}
                  </button>

                  <button
                    onClick={(e) => handleDelete(dataset.dataset_id, e)}
                    disabled={isWorking}
                    className="p-2.5 rounded-lg border border-red-500/20 text-red-400 hover:bg-red-500/10 hover:text-red-500 transition-all duration-150 disabled:opacity-50 cursor-pointer"
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
