import React, { useState, useEffect } from 'react'
import { useDropzone } from 'react-dropzone'
import {
  Upload, Database, CheckCircle, AlertCircle, Link2, FileText,
  ArrowRight, Sparkles, Cloud, X, ChevronRight, Zap, Info, ArrowLeft
} from 'lucide-react'

const FORMATS = ['CSV', 'XLSX', 'XLS', 'JSON', 'Parquet']

// ── Kaggle URL helpers ───────────────────────────────────────────────────────
const KAGGLE_DATASET_RE = /^https:\/\/(www\.)?kaggle\.com\/datasets\/[\w-]+\/[\w-]+\/?$/i

function isKaggleUrl(url) {
  return url && url.toLowerCase().includes('kaggle.com')
}

function getKaggleUrlStatus(url) {
  if (!isKaggleUrl(url)) return null
  if (KAGGLE_DATASET_RE.test(url.trim())) return 'valid'
  return 'invalid'
}

// ── Kaggle guide panel ────────────────────────────────────────────────────────
function KaggleGuide() {
  return (
    <div style={{
      marginTop: 14,
      background: 'rgba(204, 145, 102, 0.02)',
      border: '1px solid rgba(204, 145, 102, 0.15)',
      borderRadius: 'var(--radius-md)',
      overflow: 'hidden',
    }}>
      {/* Header */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 8,
        padding: '10px 14px',
        borderBottom: '1px solid rgba(204, 145, 102, 0.1)',
        background: 'rgba(204, 145, 102, 0.05)',
      }}>
        <span style={{ fontSize: '1rem' }}>🐾</span>
        <span style={{ fontSize: '0.8rem', fontWeight: 700, color: 'var(--color-vermillion-signal)' }}>
          How to copy the correct Kaggle dataset link
        </span>
      </div>

      <div style={{ padding: '14px 16px', display: 'flex', flexDirection: 'column', gap: 10 }}>
        {/* Steps */}
        {[
          { step: '1', text: 'Go to', link: 'kaggle.com/datasets', href: 'https://www.kaggle.com/datasets' },
          { step: '2', text: 'Search for and open the dataset you want' },
          { step: '3', text: 'Copy the URL directly from your browser\'s address bar' },
        ].map(({ step, text, link, href }) => (
          <div key={step} style={{ display: 'flex', alignItems: 'flex-start', gap: 10 }}>
            <div style={{
              width: 20, height: 20, borderRadius: 'var(--radius-sm)', flexShrink: 0,
              background: 'rgba(204, 145, 102, 0.08)',
              border: '1px solid rgba(204, 145, 102, 0.25)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: '0.65rem', fontWeight: 800, color: 'var(--color-vermillion-signal)',
            }}>{step}</div>
            <span style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', lineHeight: 1.5, paddingTop: 1 }}>
              {text}{' '}
              {link && (
                <a href={href} target="_blank" rel="noopener noreferrer"
                  style={{ color: 'var(--color-vermillion-signal)', textDecoration: 'none', fontWeight: 600 }}>
                  {link} ↗
                </a>
              )}
            </span>
          </div>
        ))}

        {/* Correct format */}
        <div style={{
          marginTop: 4,
          background: 'var(--color-fog)',
          borderRadius: 'var(--radius-sm)',
          padding: '10px 12px',
          border: '1px solid rgba(163, 166, 175, 0.35)',
        }}>
          <p style={{ fontSize: '0.65rem', color: 'var(--text-secondary)', marginBottom: 5, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            ✅ Correct URL format
          </p>
          <code style={{
            fontSize: '0.75rem',
            color: 'var(--text-primary)',
            fontFamily: 'monospace',
            wordBreak: 'break-all',
            lineHeight: 1.5,
          }}>
            https://www.kaggle.com/datasets/<span style={{ color: 'var(--color-vermillion-signal)' }}>username</span>/<span style={{ color: 'var(--color-vermillion-signal)' }}>dataset-name</span>
          </code>
        </div>

        {/* Common mistakes */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
          <p style={{ fontSize: '0.65rem', color: 'var(--text-secondary)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            ❌ Common mistakes to avoid
          </p>
          {[
            'www.kaggle.com/... (missing https://)',
            'kaggle.com/username/dataset (missing /datasets/)',
            'kaggle.com/datasets/username/dataset/download (extra paths)',
          ].map(m => (
            <div key={m} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{ color: 'var(--color-vermillion-signal)', fontSize: '0.7rem' }}>✕</span>
              <code style={{ fontSize: '0.7rem', color: 'var(--text-secondary)', fontFamily: 'monospace' }}>{m}</code>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

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
      background: 'var(--bg-surface)',
      border: '1px solid var(--border-subtle)',
      borderRadius: 'var(--radius-lg)',
      boxShadow: 'none',
      flex: 1, minWidth: 0,
    }}>
      <span style={{ fontSize: '1.3rem' }}>{icon}</span>
      <span style={{ fontSize: '0.95rem', fontWeight: 700, color: 'var(--text-primary)' }}>{value}</span>
      <span style={{ fontSize: '0.68rem', color: 'var(--text-secondary)', textAlign: 'center' }}>{label}</span>
    </div>
  )
}



export default function FileUpload({ onUpload, onImportURL, isUploading, uploadProgress = 0, uploadError, isSuccess, hasDatasets, onBack }) {
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
        @keyframes pulseGlow { 0%,100%{box-shadow:0 0 10px rgba(204,145,102,0.1)} 50%{box-shadow:0 0 20px rgba(204,145,102,0.2)} }
        @keyframes spin { to{transform:rotate(360deg)} }
        .upload-page-new { animation: fadeSlideUp 0.5s cubic-bezier(0.16,1,0.3,1) forwards; }
        .drop-zone-active { 
          border-color: var(--color-vermillion-signal) !important;
          background: rgba(204, 145, 102, 0.04) !important;
          animation: pulseGlow 1.5s ease-in-out infinite;
        }
        .upload-tab-btn { transition: all 0.2s ease; }
        .upload-tab-btn:hover { color: var(--color-vermillion-signal) !important; }
      `}</style>

      {/* Background */}
      <div style={{ position: 'fixed', inset: 0, background: 'var(--bg-primary)', zIndex: 0 }} />

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
          {/* Back button to registry if registry has items */}
          {hasDatasets && onBack && (
            <div style={{ marginBottom: 16, textAlign: 'left' }}>
              <button
                onClick={onBack}
                style={{
                  display: 'inline-flex', alignItems: 'center', gap: 7,
                  padding: '6px 14px',
                  borderRadius: 'var(--radius-full)',
                  background: 'var(--color-fog)',
                  border: '1px solid rgba(163, 166, 175, 0.4)',
                  color: 'var(--color-graphite)',
                  fontSize: '0.8rem', fontWeight: 600,
                  cursor: 'pointer', fontFamily: 'inherit',
                  transition: 'all 0.15s ease',
                }}
                onMouseEnter={e => {
                  e.currentTarget.style.background = 'var(--color-mist)'
                  e.currentTarget.style.color = 'var(--color-ink)'
                }}
                onMouseLeave={e => {
                  e.currentTarget.style.background = 'var(--color-fog)'
                  e.currentTarget.style.color = 'var(--color-graphite)'
                }}
              >
                <ArrowLeft size={14} />
                Back to Registry
              </button>
            </div>
          )}

          {/* Header */}
          <div style={{ textAlign: 'center', marginBottom: 28 }}>
            <div style={{
              display: 'inline-flex', alignItems: 'center', gap: 8,
              padding: '6px 14px',
              background: 'var(--color-apricot)',
              border: '1px solid var(--color-apricot-mid)',
              borderRadius: 'var(--radius-full)',
              fontSize: '0.72rem', fontWeight: 700, color: 'var(--color-rust)',
              marginBottom: 16,
              letterSpacing: '0.02em',
            }}>
              <Zap size={12} /> Step 1 of 1 — Load your dataset
            </div>
            <h1 style={{
              fontSize: '2.2rem', fontWeight: 700, letterSpacing: '-0.03em',
              color: 'var(--color-ink)', marginBottom: 10,
              fontFamily: 'var(--font-serif)',
            }}>
              Upload Your{' '}
              <span style={{ color: 'var(--color-rust)' }}>
                Dataset
              </span>
            </h1>
            <p style={{ fontSize: '0.9rem', color: 'var(--color-graphite)', lineHeight: 1.6 }}>
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
            background: 'var(--color-white)',
            border: '1px solid rgba(163, 166, 175, 0.25)',
            borderRadius: 'var(--radius-lg)',
            overflow: 'hidden',
            boxShadow: 'var(--shadow-subtle)',
          }}>
            {/* Tab bar */}
            <div style={{
              display: 'flex',
              borderBottom: '1px solid var(--border-subtle)',
              background: 'var(--bg-glass-hover)',
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
                    color: activeTab === key ? 'var(--color-vermillion-signal)' : 'var(--text-secondary)',
                    background: 'none', border: 'none', cursor: 'pointer',
                    borderBottom: activeTab === key ? '2px solid var(--color-vermillion-signal)' : '2px solid transparent',
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
                      border: '2px dashed var(--border-subtle)',
                      borderRadius: 'var(--radius-md)',
                      padding: '40px 24px',
                      textAlign: 'center',
                      cursor: isUploading ? 'default' : 'pointer',
                      background: isDragActive ? 'rgba(204, 145, 102, 0.03)' : 'var(--bg-glass-hover)',
                      transition: 'all 0.25s ease',
                    }}
                  >
                    <input {...getInputProps()} />

                    {isUploading ? (
                      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 14 }}>
                        {/* Spinner ring */}
                        <div style={{
                          width: 52, height: 52, borderRadius: '50%',
                          border: '3px solid rgba(93, 42, 26, 0.12)',
                          borderTopColor: 'var(--color-rust)',
                          animation: 'spin 0.9s linear infinite',
                        }} />
                        <div style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', fontWeight: 500 }}>
                          {uploadPhase}
                        </div>
                        {uploadProgress > 0 && uploadProgress < 100 && !isImportingUrl && (
                          <div style={{ width: '70%', height: 6, borderRadius: 'var(--radius-full)', background: 'var(--color-mist)', border: '1px solid rgba(163, 166, 175, 0.35)', overflow: 'hidden' }}>
                            <div style={{
                              height: '100%', width: `${uploadProgress}%`,
                              background: 'var(--color-rust)',
                              transition: 'width 0.3s ease',
                            }} />
                          </div>
                        )}
                      </div>
                    ) : (
                      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12 }}>
                        <div style={{
                          width: 60, height: 60, borderRadius: 'var(--radius-md)',
                          background: isDragActive
                            ? 'rgba(204, 145, 102, 0.12)'
                            : 'rgba(204, 145, 102, 0.06)',
                          border: `1px solid rgba(204, 145, 102, ${isDragActive ? 0.35 : 0.18})`,
                          display: 'flex', alignItems: 'center', justifyContent: 'center',
                          transition: 'all 0.25s ease',
                        }}>
                          <Upload size={24} style={{ color: 'var(--color-vermillion-signal)' }} />
                        </div>
                        <div>
                          <p style={{ fontSize: '0.95rem', color: 'var(--text-primary)', fontWeight: 600, marginBottom: 4 }}>
                            {isDragActive ? '✨ Drop your file here' : (
                              <><strong style={{ color: 'var(--color-vermillion-signal)' }}>Click to browse</strong> or drag & drop</>
                            )}
                          </p>
                          <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                            Any CSV, Excel, JSON, or Parquet file up to 100 MB
                          </p>
                        </div>
                        {/* Format chips */}
                        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', justify: 'center', marginTop: 4 }}>
                          {FORMATS.map(f => (
                            <span key={f} style={{
                              padding: '3px 10px',
                              background: 'var(--color-fog)',
                              border: '1px solid rgba(163, 166, 175, 0.35)',
                              borderRadius: 'var(--radius-full)',
                              fontSize: '0.68rem', fontWeight: 600,
                              color: 'var(--color-graphite)',
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
                          type="text"
                          placeholder="https://www.kaggle.com/datasets/owner/name  or  direct .csv URL"
                          value={url}
                          onChange={e => setUrl(e.target.value)}
                          disabled={isUploading}
                          style={{
                            width: '100%', padding: '12px 14px 12px 40px',
                            background: 'var(--bg-glass-hover)',
                            border: `1px solid ${
                              getKaggleUrlStatus(url) === 'invalid'
                                ? 'var(--color-vermillion-signal)'
                                : getKaggleUrlStatus(url) === 'valid'
                                  ? '#10b981'
                                  : 'var(--border-subtle)'
                            }`,
                            borderRadius: 'var(--radius-md)', color: 'var(--text-primary)',
                            fontSize: '0.88rem', fontFamily: 'inherit',
                            outline: 'none', boxSizing: 'border-box',
                          }}
                          onFocus={e => { e.target.style.boxShadow = '0 0 0 3px rgba(204, 145, 102, 0.08)' }}
                          onBlur={e => { e.target.style.boxShadow = 'none' }}
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

                      {/* Kaggle valid badge */}
                      {getKaggleUrlStatus(url) === 'valid' && (
                        <div style={{
                          marginTop: 8, display: 'flex', alignItems: 'center', gap: 6,
                          fontSize: '0.75rem', color: 'var(--success)',
                        }}>
                          <CheckCircle size={13} />
                          Kaggle dataset URL looks correct — ready to import!
                        </div>
                      )}

                      {/* Kaggle invalid guide */}
                      {getKaggleUrlStatus(url) === 'invalid' && <KaggleGuide />}

                      {/* Generic hint for non-Kaggle URLs */}
                      {url && !isKaggleUrl(url) && (
                        <p style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: 6, lineHeight: 1.5 }}>
                          Supports Kaggle datasets, GitHub raw CSV/JSON, or any public direct URL
                        </p>
                      )}
                    </div>

                    {isUploading ? (
                      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12, padding: '20px 0' }}>
                        <div style={{
                          width: 44, height: 44, borderRadius: '50%',
                          border: '3px solid rgba(93, 42, 26, 0.12)',
                          borderTopColor: 'var(--color-rust)',
                          animation: 'spin 0.9s linear infinite',
                        }} />
                        <span style={{ fontSize: '0.88rem', color: 'var(--text-secondary)' }}>{uploadPhase}</span>
                      </div>
                    ) : (
                      <button
                        type="submit"
                        disabled={!url.trim() || isUploading}
                        style={{
                          padding: '12px 24px',
                          borderRadius: 'var(--radius-full)',
                          background: url.trim()
                            ? 'var(--color-ink)'
                            : 'var(--color-mist)',
                          color: url.trim() ? 'var(--color-white)' : 'var(--color-dove)',
                          fontWeight: 600, fontSize: '0.9rem',
                          letterSpacing: '-0.007em',
                          border: 'none',
                          cursor: url.trim() ? 'pointer' : 'not-allowed',
                          display: 'flex', alignItems: 'center', justify: 'center', gap: 8,
                          transition: 'opacity 0.15s ease',
                          boxShadow: 'none',
                          fontFamily: 'inherit',
                          opacity: url.trim() ? 1 : 0.5,
                        }}
                      >
                        <Cloud size={16} />
                        Import Dataset
                        <ArrowRight size={15} />
                      </button>
                    )}
                  </form>


                </div>
              )}

              {/* Error */}
              {error && (
                <div style={{
                  marginTop: 16,
                  display: 'flex', alignItems: 'flex-start', gap: 10,
                  padding: '12px 14px',
                  background: 'rgba(204, 145, 102, 0.05)',
                  border: '1px solid rgba(204, 145, 102, 0.2)',
                  borderRadius: 'var(--radius-md)',
                  fontSize: '0.8rem', color: 'var(--color-vermillion-signal)', lineHeight: 1.4,
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
                  background: 'rgba(16, 185, 129, 0.06)',
                  border: '1px solid rgba(16, 185, 129, 0.22)',
                  borderRadius: 'var(--radius-md)',
                  fontSize: '0.84rem', color: 'var(--success)', fontWeight: 500,
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
