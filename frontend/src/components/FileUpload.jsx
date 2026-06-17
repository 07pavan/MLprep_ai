import React, { useState, useEffect } from 'react'
import { useDropzone } from 'react-dropzone'
import { Upload, Database, CheckCircle, AlertCircle } from 'lucide-react'

const FORMATS = ['CSV', 'XLSX', 'XLS', 'JSON', 'Parquet']

// Accept by extension only — MIME types differ wildly between browsers/OS
const ACCEPT = {
  'text/csv': ['.csv'],
  'text/plain': ['.csv'],
  'application/csv': ['.csv'],
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
  'application/vnd.ms-excel': ['.xls'],
  'application/json': ['.json'],
  'text/json': ['.json'],
  'application/octet-stream': ['.parquet', '.csv', '.json'],
  'application/x-parquet': ['.parquet'],
}

const EXT_WHITELIST = ['.csv', '.xlsx', '.xls', '.json', '.parquet']

function isAcceptedByExtension(filename) {
  if (!filename) return false
  const lower = filename.toLowerCase()
  return EXT_WHITELIST.some((ext) => lower.endsWith(ext))
}

export default function FileUpload({ onUpload, onImportURL, isUploading, uploadProgress = 0, uploadError, isSuccess }) {
  const [rejected, setRejected] = useState(null)
  const [url, setUrl] = useState('')
  const [isImportingUrl, setIsImportingUrl] = useState(false)

  useEffect(() => {
    if (!isUploading) {
      setIsImportingUrl(false)
    }
  }, [isUploading])

  const handleImportSubmit = async (e) => {
    e.preventDefault()
    if (!url.trim()) return
    setRejected(null)
    setIsImportingUrl(true)
    if (onImportURL) {
      await onImportURL(url.trim())
    }
  }

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    // Don't rely solely on MIME — also validate by extension in onDrop
    multiple: false,
    disabled: isUploading,
    onDrop: (acceptedFiles, fileRejections) => {
      setRejected(null)

      // Try accepted files first
      if (acceptedFiles.length > 0) {
        const f = acceptedFiles[0]
        if (isAcceptedByExtension(f.name)) {
          onUpload(f)
          return
        }
      }

      // Try rejected files — browser may reject due to wrong MIME but extension is fine
      if (fileRejections.length > 0) {
        const f = fileRejections[0].file
        if (isAcceptedByExtension(f.name)) {
          onUpload(f)
          return
        }
        setRejected(`Unsupported file: "${f.name}". Please use CSV, XLSX, JSON, or Parquet.`)
      }
    },
  })

  const error = uploadError || rejected
  const phase = isImportingUrl
    ? (uploadProgress < 100 ? 'Importing from URL…' : 'Profiling dataset…')
    : (uploadProgress < 100 ? `Uploading… ${uploadProgress}%` : 'Profiling dataset…')

  return (
    <div className="upload-page">
      <div className="upload-card">
        <div className="upload-icon">
          <Database size={36} />
        </div>

        <h1 className="upload-title">
          <span className="gradient-text">Upload Your Dataset</span>
        </h1>
        <p className="upload-subtitle">CSV · Excel · JSON · Parquet &nbsp;·&nbsp; up to 100 MB</p>

        <div
          {...getRootProps()}
          className={`upload-zone ${isDragActive ? 'drag-active' : ''} ${isUploading ? 'uploading' : ''}`}
        >
          <input {...getInputProps()} />
          {isUploading ? (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12, width: '100%' }}>
              <div className="spinner" />
              <p style={{ color: 'var(--text-secondary)', fontSize: '0.88rem' }}>{phase}</p>
              {uploadProgress > 0 && uploadProgress < 100 && !isImportingUrl && (
                <div style={{
                  width: '80%', height: 6, borderRadius: 3,
                  background: 'var(--border)', overflow: 'hidden',
                }}>
                  <div style={{
                    height: '100%', width: `${uploadProgress}%`,
                    background: 'var(--accent-gradient)',
                    borderRadius: 3,
                    transition: 'width 0.3s ease',
                  }} />
                </div>
              )}
            </div>
          ) : (
            <div className="upload-zone-text">
              <Upload size={32} style={{ color: 'var(--text-muted)', marginBottom: 8 }} />
              <p>
                {isDragActive
                  ? 'Drop your file here…'
                  : <><strong>Click to browse</strong> or drag &amp; drop a file</>
                }
              </p>
              <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginTop: 4 }}>
                Any CSV, Excel, JSON or Parquet file
              </p>
            </div>
          )}
        </div>

        {error && (
          <div className="error-card" style={{ marginTop: 16, display: 'flex', alignItems: 'center', gap: 8 }}>
            <AlertCircle size={16} />
            <span>{error}</span>
          </div>
        )}

        {isSuccess && (
          <div className="glass-card" style={{
            marginTop: 16,
            padding: '10px 16px',
            borderColor: 'rgba(16,185,129,0.3)',
            backgroundColor: 'rgba(16,185,129,0.05)',
            color: '#10b981',
            fontSize: '0.84rem',
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            justifyContent: 'center'
          }}>
            <CheckCircle size={16} />
            <span>Dataset loaded successfully! Redirecting...</span>
          </div>
        )}

        {!isUploading && !isSuccess && (
          <>
            <div className="flex items-center my-5">
              <div className="flex-grow border-t border-[rgba(255,255,255,0.08)]"></div>
              <span className="mx-4 text-xs font-semibold uppercase tracking-wider text-gray-500" style={{ color: 'var(--text-muted)' }}>OR</span>
              <div className="flex-grow border-t border-[rgba(255,255,255,0.08)]"></div>
            </div>

            <form onSubmit={handleImportSubmit} className="space-y-2 text-left" style={{ width: '100%' }}>
              <label htmlFor="dataset-url" className="block text-xs font-semibold text-gray-400 mb-1" style={{ color: 'var(--text-secondary)' }}>
                Import from URL
              </label>
              <div className="flex gap-2">
                <input
                  id="dataset-url"
                  type="url"
                  placeholder="https://example.com/data.csv"
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  disabled={isUploading}
                  className="input-field flex-grow"
                  required
                  style={{ flexGrow: 1 }}
                />
                <button
                  type="submit"
                  disabled={isUploading || !url.trim()}
                  className="btn-primary flex-shrink-0"
                  style={{ padding: '10px 16px', flexShrink: 0 }}
                >
                  Import
                </button>
              </div>
              <p className="text-[11px] text-gray-500 mt-1 leading-normal" style={{ color: 'var(--text-muted)', fontSize: '0.72rem', marginTop: 4 }}>
                Supports GitHub CSV/JSON, Kaggle datasets, or any public CSV/Excel/JSON/Parquet URL.
              </p>
            </form>
          </>
        )}

        <div className="upload-formats">
          {FORMATS.map((f) => (
            <span key={f} className="upload-format-chip">{f}</span>
          ))}
        </div>

        <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: 12, textAlign: 'center' }}>
          Your data is processed locally and never stored on external servers.
        </p>
      </div>
    </div>
  )
}
