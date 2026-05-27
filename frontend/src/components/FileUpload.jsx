import React, { useState } from 'react'
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

export default function FileUpload({ onUpload, isUploading, uploadProgress = 0, uploadError }) {
  const [rejected, setRejected] = useState(null)

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
  const phase = uploadProgress < 100 ? `Uploading… ${uploadProgress}%` : 'Profiling dataset…'

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
              {uploadProgress > 0 && uploadProgress < 100 && (
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
