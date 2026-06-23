import React, { useState, useEffect } from 'react'
import { useDropzone } from 'react-dropzone'
import {
  Upload, Database, CheckCircle, AlertCircle, Link2, FileText,
  ArrowRight, Sparkles, Cloud, X, ChevronRight, Zap
} from 'lucide-react'

const FORMATS = ['CSV', 'XLSX', 'XLS', 'JSON', 'Parquet']

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

/* ── Stat card at top ───────────────────────────────────────────── */
function QuickStat({ icon, value, label }) {
  return (
    <div style={{
      display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4,
      padding: '14px 20px',
      background: 'rgba(217,119,6,0.05)',
      border: '1px solid rgba(217,119,6,0.12)',
      borderRadius: 14, flex: 1, minWidth: 0,
    }}>
      <span style={{ fontSize: '1.3rem' }}>{icon}</span>
      <span style={{ fontSize: '1rem', fontWeight: 700, color: 'var(--text-primary)' }}>{value}</span>
      <span style={{ fontSize: '0.68rem', color: 'var(--text-muted)', textAlign: 'center' }}>{label}</span>
    </div>
  )
}

/* ── Sample dataset chip ────────────────────────────────────────── */
function SampleChip({ url, label, emoji, onImport }) {
  return (
    <button
      onClick={() => onImport(url)}
      style={{
        display: 'flex', alignItems: 'center', gap: 6,
        padding: '6px 12px',
        background: 'rgba(255,255,255,0.03)',
        border: '1px solid rgba(255,255,255,0.07)',
        borderRadius: 999,
        fontSize: '0.74rem', color: 'var(--text-secondary)',
        cursor: 'pointer', transition: 'all 0.2s ease',
        fontFamily: 'inherit',
      }}
      onMouseEnter={e => {
        e.currentTarget.style.background = 'rgba(217,119,6,0.1)'
        e.currentTarget.style.borderColor = 'rgba(217,119,6,0.25)'
        e.currentTarget.style.color = 'var(--accent-2)'
      }}
      onMouseLeave={e => {
        e.currentTarget.style.background = 'rgba(255,255,255,0.03)'
        e.currentTarget.style.borderColor = 'rgba(255,255,255,0.07)'
        e.currentTarget.style.color = 'var(--text-secondary)'
      }}
    >
      {emoji} {label}
    </button>
  )
}

export default function FileUpload({ onUpload, onImportURL, isUploading, uploadProgress = 0, uploadError, isSuccess }) {
  const [rejected, setRejected] = useState(null)
  const [url, setUrl] = useState('')
  const [isImportingUrl, setIsImportingUrl] = useState(false)
  const [activeTab, setActiveTab] = useState('file') // 'file' | 'url'
  const [mounted, setMounted] = useState(false)

  useEffect(() => { setMounted(true) }, [])

  useEffect(() => {
    if (!isUploading) setIsImportingUrl(false)
  }, [isUploading])

  const handleImportSubmit = async (e) => {
    e?.preventDefault()
    const targetUrl = typeof e === 'string' ? e : url.trim()
    if (!targetUrl) return
    setRejected(null)
    setIsImportingUrl(true)
    if (onImportURL) await onImportURL(targetUrl)
  }

  const handleSampleImport = (sampleUrl) => {
    setUrl(sampleUrl)
    setActiveTab('url')
    setIsImportingUrl(true)
    if (onImportURL) onImportURL(sampleUrl)
  }

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    multiple: false,
    disabled: isUploading,
    onDrop: (acceptedFiles, fileRejections) => {
      setRejected(null)
      if (acceptedFiles.length > 0) {
        const f = acceptedFiles[0]
        if (isAcceptedByExtension(f.name)) { onUpload(f); return }
      }
      if (fileRejections.length > 0) {
        const f = fileRejections[0].file
        if (isAcceptedByExtension(f.name)) { onUpload(f); return }
        setRejected(`Unsupported file: "${f.name}". Please use CSV, XLSX, JSON, or Parquet.`)
      }
    },
  })

  const error = uploadError || rejected
  const uploadPhase = isImportingUrl
    ? (uploadProgress < 100 ? 'Fetching dataset…' : 'Profiling data…')
    : (uploadProgress < 100 ? `Uploading… ${uploadProgress}%` : 'Profiling data…')

  return (
    <>
      <style>{`
        @keyframes fadeSlideUp { from{opacity:0;transform:translateY(20px)} to{opacity:1;transform:translateY(0)} }
        @keyframes pulseGlow { 0%,100%{box-shadow:0 0 20px rgba(217,119,6,0.15)} 50%{box-shadow:0 0 40px rgba(217,119,6,0.3)} }
        @keyframes spin { to{transform:rotate(360deg)} }
        @keyframes progressShimmer { 0%{background-position:200% center} 100%{background-position:-200% center} }
        .upload-page-new { animation: fadeSlideUp 0.5s cubic-bezier(0.16,1,0.3,1) forwards; }
        .drop-zone-active { 
          border-color: rgba(217,119,6,0.6) !important;
          background: rgba(217,119,6,0.06) !important;
          animation: pulseGlow 1.5s ease-in-out infinite;
        }
        .upload-tab-btn { transition: all 0.2s ease; }
        .upload-tab-btn:hover { color: var(--text-primary) !important; }
      `}</style>

      {/* Background */}
      <div style={{ position: 'fixed', inset: 0, background: 'var(--bg-primary)', zIndex: 0 }}>
        <div style={{
          position: 'absolute', top: 0, left: '50%', transform: 'translateX(-50%)',
          width: 800, height: 400,
          background: 'radial-gradient(ellipse at top, rgba(217,119,6,0.08) 0%, transparent 70%)',
          pointerEvents: 'none',
        }} />
        <div style={{
          position: 'absolute', inset: 0,
          backgroundImage: `linear-gradient(rgba(255,255,255,0.012) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.012) 1px, transparent 1px)`,
          backgroundSize: '56px 56px',
          maskImage: 'radial-gradient(ellipse 80% 60% at 50% 0%, black 0%, transparent 100%)',
        }} />
      </div>

      <div style={{
        position: 'relative', zIndex: 1,
        minHeight: '100vh',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '32px 16px',
      }}>
        <div
          className="upload-page-new"
          style={{ width: '100%', maxWidth: 580 }}
        >
          {/* Header */}
          <div style={{ textAlign: 'center', marginBottom: 28 }}>
            <div style={{
              display: 'inline-flex', alignItems: 'center', gap: 8,
              padding: '6px 16px',
              background: 'rgba(217,119,6,0.08)',
              border: '1px solid rgba(217,119,6,0.2)',
              borderRadius: 999,
              fontSize: '0.75rem', fontWeight: 600, color: 'var(--accent-2)',
              marginBottom: 16,
            }}>
              <Zap size={12} /> Step 1 of 1 — Load your dataset
            </div>
            <h1 style={{
              fontSize: '2.2rem', fontWeight: 800, letterSpacing: '-0.03em',
              color: 'var(--text-primary)', marginBottom: 10,
            }}>
              Upload Your{' '}
              <span style={{
                background: 'linear-gradient(135deg, #F59E0B, #D97706)',
                WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent',
                backgroundClip: 'text',
              }}>
                Dataset
              </span>
            </h1>
            <p style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', lineHeight: 1.6 }}>
              Upload a file or import from a URL to start analyzing with AI
            </p>
          </div>

          {/* Quick stats row */}
          <div style={{ display: 'flex', gap: 10, marginBottom: 20 }}>
            <QuickStat icon="📁" value="100 MB" label="Max file size" />
            <QuickStat icon="⚡" value="< 3s" label="Avg load time" />
            <QuickStat icon="🔒" value="Private" label="Local processing" />
          </div>

          {/* Main card */}
          <div style={{
            background: 'rgba(20,19,16,0.85)',
            backdropFilter: 'blur(24px)',
            border: '1px solid rgba(255,255,255,0.06)',
            borderRadius: 20,
            overflow: 'hidden',
            boxShadow: '0 24px 64px rgba(0,0,0,0.5)',
          }}>
            {/* Tab bar */}
            <div style={{
              display: 'flex',
              borderBottom: '1px solid rgba(255,255,255,0.05)',
              background: 'rgba(0,0,0,0.2)',
            }}>
              {[
                { key: 'file', icon: <Upload size={14} />, label: 'Upload File' },
                { key: 'url', icon: <Link2 size={14} />, label: 'Import URL' },
              ].map(({ key, icon, label }) => (
                <button
                  key={key}
                  className="upload-tab-btn"
                  onClick={() => setActiveTab(key)}
                  style={{
                    flex: 1, padding: '14px 16px',
                    display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 7,
                    fontSize: '0.83rem', fontWeight: 600,
                    color: activeTab === key ? 'var(--accent-2)' : 'var(--text-muted)',
                    background: 'none', border: 'none', cursor: 'pointer',
                    borderBottom: activeTab === key ? '2px solid var(--accent-1)' : '2px solid transparent',
                    transition: 'all 0.2s ease',
                    fontFamily: 'inherit',
                  }}
                >
                  {icon} {label}
                </button>
              ))}
            </div>

            <div style={{ padding: '28px 28px 24px' }}>

              {/* Upload tab */}
              {activeTab === 'file' && (
                <>
                  <div
                    {...getRootProps()}
                    className={isDragActive ? 'drop-zone-active' : ''}
                    style={{
                      border: '2px dashed rgba(255,255,255,0.1)',
                      borderRadius: 16,
                      padding: '40px 24px',
                      textAlign: 'center',
                      cursor: isUploading ? 'default' : 'pointer',
                      background: isDragActive ? 'rgba(217,119,6,0.05)' : 'rgba(255,255,255,0.02)',
                      transition: 'all 0.25s ease',
                    }}
                  >
                    <input {...getInputProps()} />

                    {isUploading ? (
                      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 14 }}>
                        {/* Spinner ring */}
                        <div style={{
                          width: 52, height: 52, borderRadius: '50%',
                          border: '3px solid rgba(217,119,6,0.15)',
                          borderTopColor: 'var(--accent-1)',
                          animation: 'spin 0.9s linear infinite',
                        }} />
                        <div style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', fontWeight: 500 }}>
                          {uploadPhase}
                        </div>
                        {uploadProgress > 0 && uploadProgress < 100 && !isImportingUrl && (
                          <div style={{ width: '70%', height: 5, borderRadius: 99, background: 'rgba(255,255,255,0.06)', overflow: 'hidden' }}>
                            <div style={{
                              height: '100%', width: `${uploadProgress}%`,
                              background: 'linear-gradient(90deg, #D97706, #F59E0B, #D97706)',
                              backgroundSize: '200% auto',
                              animation: 'progressShimmer 1.5s linear infinite',
                              borderRadius: 99,
                              transition: 'width 0.3s ease',
                            }} />
                          </div>
                        )}
                      </div>
                    ) : (
                      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12 }}>
                        <div style={{
                          width: 60, height: 60, borderRadius: 16,
                          background: isDragActive
                            ? 'linear-gradient(135deg, rgba(217,119,6,0.3), rgba(245,158,11,0.2))'
                            : 'rgba(217,119,6,0.1)',
                          border: `1px solid ${isDragActive ? 'rgba(217,119,6,0.4)' : 'rgba(217,119,6,0.15)'}`,
                          display: 'flex', alignItems: 'center', justifyContent: 'center',
                          transition: 'all 0.25s ease',
                        }}>
                          <Upload size={24} style={{ color: isDragActive ? 'var(--accent-2)' : 'var(--accent-1)' }} />
                        </div>
                        <div>
                          <p style={{ fontSize: '0.95rem', color: 'var(--text-primary)', fontWeight: 600, marginBottom: 4 }}>
                            {isDragActive ? '✨ Drop your file here' : (
                              <><strong style={{ color: 'var(--accent-2)' }}>Click to browse</strong> or drag & drop</>
                            )}
                          </p>
                          <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                            Any CSV, Excel, JSON, or Parquet file up to 100 MB
                          </p>
                        </div>
                        {/* Format chips */}
                        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', justifyContent: 'center', marginTop: 4 }}>
                          {FORMATS.map(f => (
                            <span key={f} style={{
                              padding: '3px 10px',
                              background: 'rgba(255,255,255,0.04)',
                              border: '1px solid rgba(255,255,255,0.08)',
                              borderRadius: 999,
                              fontSize: '0.7rem', fontWeight: 600,
                              color: 'var(--text-muted)',
                              letterSpacing: '0.04em',
                            }}>{f}</span>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </>
              )}

              {/* URL tab */}
              {activeTab === 'url' && (
                <div>
                  <form onSubmit={handleImportSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                    <div>
                      <label style={{
                        display: 'block', fontSize: '0.72rem', fontWeight: 600,
                        color: 'var(--text-secondary)', letterSpacing: '0.04em',
                        textTransform: 'uppercase', marginBottom: 8,
                      }}>
                        Dataset URL
                      </label>
                      <div style={{ position: 'relative' }}>
                        <Link2 size={15} style={{
                          position: 'absolute', left: 14, top: '50%',
                          transform: 'translateY(-50%)', color: 'var(--text-muted)',
                          pointerEvents: 'none',
                        }} />
                        <input
                          id="dataset-url"
                          type="url"
                          placeholder="https://example.com/dataset.csv"
                          value={url}
                          onChange={e => setUrl(e.target.value)}
                          disabled={isUploading}
                          style={{
                            width: '100%', padding: '12px 14px 12px 40px',
                            background: 'rgba(255,255,255,0.04)',
                            border: '1px solid rgba(255,255,255,0.08)',
                            borderRadius: 12, color: 'var(--text-primary)',
                            fontSize: '0.88rem', fontFamily: 'inherit',
                            outline: 'none',
                          }}
                          onFocus={e => { e.target.style.borderColor = 'rgba(217,119,6,0.45)'; e.target.style.boxShadow = '0 0 0 3px rgba(217,119,6,0.08)' }}
                          onBlur={e => { e.target.style.borderColor = 'rgba(255,255,255,0.08)'; e.target.style.boxShadow = 'none' }}
                        />
                        {url && (
                          <button type="button" onClick={() => setUrl('')} style={{
                            position: 'absolute', right: 12, top: '50%',
                            transform: 'translateY(-50%)', background: 'none', border: 'none',
                            color: 'var(--text-muted)', cursor: 'pointer', padding: 4,
                          }}>
                            <X size={14} />
                          </button>
                        )}
                      </div>
                      <p style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: 6, lineHeight: 1.5 }}>
                        Supports Kaggle datasets, GitHub CSV/JSON, or any public direct URL
                      </p>
                    </div>

                    {isUploading ? (
                      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12, padding: '20px 0' }}>
                        <div style={{
                          width: 44, height: 44, borderRadius: '50%',
                          border: '3px solid rgba(217,119,6,0.15)',
                          borderTopColor: 'var(--accent-1)',
                          animation: 'spin 0.9s linear infinite',
                        }} />
                        <span style={{ fontSize: '0.88rem', color: 'var(--text-secondary)' }}>{uploadPhase}</span>
                      </div>
                    ) : (
                      <button
                        type="submit"
                        disabled={!url.trim() || isUploading}
                        style={{
                          padding: '13px',
                          borderRadius: 12,
                          background: url.trim()
                            ? 'linear-gradient(135deg, #D97706, #F59E0B)'
                            : 'rgba(255,255,255,0.05)',
                          color: url.trim() ? '#fff' : 'var(--text-muted)',
                          fontWeight: 700, fontSize: '0.9rem',
                          border: url.trim() ? 'none' : '1px solid rgba(255,255,255,0.06)',
                          cursor: url.trim() ? 'pointer' : 'not-allowed',
                          display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
                          transition: 'all 0.2s ease',
                          boxShadow: url.trim() ? '0 4px 16px rgba(217,119,6,0.2)' : 'none',
                          fontFamily: 'inherit',
                        }}
                      >
                        <Cloud size={16} />
                        Import Dataset
                        <ArrowRight size={15} />
                      </button>
                    )}
                  </form>

                  {/* Sample datasets */}
                  {!isUploading && (
                    <div style={{ marginTop: 20, paddingTop: 16, borderTop: '1px solid rgba(255,255,255,0.05)' }}>
                      <p style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginBottom: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                        Try a sample dataset
                      </p>
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                        <SampleChip
                          emoji="🚢"
                          label="Titanic"
                          url="https://raw.githubusercontent.com/datasciencedojo/datasets/master/titanic.csv"
                          onImport={handleSampleImport}
                        />
                        <SampleChip
                          emoji="🌸"
                          label="Iris"
                          url="https://raw.githubusercontent.com/mwaskom/seaborn-data/master/iris.csv"
                          onImport={handleSampleImport}
                        />
                        <SampleChip
                          emoji="🏠"
                          label="Housing"
                          url="https://raw.githubusercontent.com/ageron/handson-ml/master/datasets/housing/housing.csv"
                          onImport={handleSampleImport}
                        />
                        <SampleChip
                          emoji="💊"
                          label="Diabetes"
                          url="https://raw.githubusercontent.com/jbrownlee/Datasets/master/pima-indians-diabetes.csv"
                          onImport={handleSampleImport}
                        />
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* Error */}
              {error && (
                <div style={{
                  marginTop: 16,
                  display: 'flex', alignItems: 'flex-start', gap: 10,
                  padding: '12px 14px',
                  background: 'rgba(239,68,68,0.08)',
                  border: '1px solid rgba(239,68,68,0.25)',
                  borderRadius: 12,
                  fontSize: '0.8rem', color: '#fca5a5', lineHeight: 1.4,
                }}>
                  <AlertCircle size={15} style={{ flexShrink: 0, marginTop: 1 }} />
                  <span>{error}</span>
                </div>
              )}

              {/* Success */}
              {isSuccess && (
                <div style={{
                  marginTop: 16,
                  display: 'flex', alignItems: 'center', gap: 10,
                  padding: '12px 16px',
                  background: 'rgba(16,185,129,0.08)',
                  border: '1px solid rgba(16,185,129,0.25)',
                  borderRadius: 12,
                  fontSize: '0.84rem', color: '#34d399', fontWeight: 500,
                }}>
                  <CheckCircle size={17} />
                  <span>Dataset loaded! Opening your workspace…</span>
                </div>
              )}
            </div>
          </div>

          {/* Bottom trust bar */}
          <div style={{
            marginTop: 20,
            display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 20,
            fontSize: '0.72rem', color: 'var(--text-muted)',
          }}>
            {[
              { icon: '🔒', text: 'Data stays local' },
              { icon: '⚡', text: 'Instant AI analysis' },
              { icon: '📊', text: 'Auto data profiling' },
            ].map(({ icon, text }) => (
              <span key={text} style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                {icon} {text}
              </span>
            ))}
          </div>
        </div>
      </div>
    </>
  )
}
