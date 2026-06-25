import React, { useState, useEffect } from 'react'
import { X, Sliders, Eye, EyeOff, Check, AlertTriangle, RefreshCw } from 'lucide-react'
import { getRateLimits } from '../api/client'

export default function LLMConfigModal({ isOpen, onClose }) {
  const [provider, setProvider] = useState('groq')
  const [key, setKey] = useState('')
  const [model, setModel] = useState('')
  const [showKey, setShowKey] = useState(false)
  const [limits, setLimits] = useState(null)
  const [loadingLimits, setLoadingLimits] = useState(false)
  const [saveStatus, setSaveStatus] = useState(false)

  useEffect(() => {
    if (isOpen) {
      const savedProvider = localStorage.getItem('customLlmProvider') || 'default'
      const savedKey = localStorage.getItem('customLlmKey') || ''
      const savedModel = localStorage.getItem('customLlmModel') || ''
      setProvider(savedProvider)
      setKey(savedKey)
      setModel(savedModel)
      setSaveStatus(false)
      if (savedKey) fetchLimits(savedKey)
      else setLimits(null)
    }
  }, [isOpen])

  const fetchLimits = async (activeKey) => {
    setLoadingLimits(true)
    try {
      const oldKey = localStorage.getItem('customLlmKey')
      localStorage.setItem('customLlmKey', activeKey)
      const data = await getRateLimits()
      setLimits(data)
      if (!activeKey) localStorage.removeItem('customLlmKey')
    } catch (err) {
      console.error('Failed to load rate limits:', err)
      setLimits(null)
    } finally {
      setLoadingLimits(false)
    }
  }

  const handleSave = () => {
    if (provider === 'default') {
      localStorage.removeItem('customLlmProvider')
      localStorage.removeItem('customLlmKey')
      localStorage.removeItem('customLlmModel')
    } else {
      localStorage.setItem('customLlmProvider', provider)
      localStorage.setItem('customLlmKey', key.trim())
      if (model.trim()) localStorage.setItem('customLlmModel', model.trim())
      else localStorage.removeItem('customLlmModel')
    }
    setSaveStatus(true)
    setTimeout(() => { setSaveStatus(false); onClose() }, 1000)
  }

  const handleClear = () => {
    setProvider('default')
    setKey('')
    setModel('')
    setLimits(null)
    localStorage.removeItem('customLlmProvider')
    localStorage.removeItem('customLlmKey')
    localStorage.removeItem('customLlmModel')
  }

  if (!isOpen) return null

  return (
    <>
      <style>{`
        @keyframes backdropFade { from{opacity:0} to{opacity:1} }
        @keyframes modalSlide { from{opacity:0;transform:translateY(16px) scale(0.98)} to{opacity:1;transform:translateY(0) scale(1)} }
        .llm-modal-backdrop { animation: backdropFade 0.2s ease-out; }
        .llm-modal-card { animation: modalSlide 0.25s cubic-bezier(0.16,1,0.3,1); }
        .llm-input {
          width: 100%; padding: 10px 14px;
          background: var(--color-fog);
          border: 1px solid rgba(163, 166, 175, 0.4);
          border-radius: var(--radius-sm);
          color: var(--color-ink); font-size: 0.875rem;
          font-family: inherit; outline: none;
          box-sizing: border-box;
          transition: border-color 0.15s ease, box-shadow 0.15s ease;
        }
        .llm-input:focus {
          border-color: var(--color-ink);
          box-shadow: 0 0 0 3px rgba(27,27,27,0.06);
        }
        .llm-select {
          width: 100%; padding: 10px 14px;
          background: var(--color-fog);
          border: 1px solid rgba(163, 166, 175, 0.4);
          border-radius: var(--radius-sm);
          color: var(--color-ink); font-size: 0.875rem;
          font-family: inherit; outline: none;
          cursor: pointer; appearance: none;
          background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%23636974' stroke-width='2'%3E%3Cpath d='M6 9l6 6 6-6'/%3E%3C/svg%3E");
          background-repeat: no-repeat;
          background-position: right 14px center;
          padding-right: 36px;
        }
        .llm-select:focus { border-color: var(--color-ink); outline: none; }
      `}</style>

      {/* Backdrop */}
      <div
        className="llm-modal-backdrop"
        onClick={onClose}
        style={{
          position: 'fixed', inset: 0, zIndex: 200,
          background: 'rgba(27, 27, 27, 0.4)',
          backdropFilter: 'blur(4px)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          padding: 16,
        }}
      >
        {/* Modal card */}
        <div
          className="llm-modal-card"
          onClick={e => e.stopPropagation()}
          style={{
            width: '100%', maxWidth: 440,
            background: 'var(--color-white)',
            border: '1px solid rgba(163, 166, 175, 0.25)',
            borderRadius: 'var(--radius-lg)',
            boxShadow: 'var(--shadow-card), 0 32px 64px rgba(27,27,27,0.12)',
            padding: 28,
            position: 'relative',
          }}
        >
          {/* Close button */}
          <button
            onClick={onClose}
            style={{
              position: 'absolute', top: 16, right: 16,
              width: 30, height: 30, borderRadius: 'var(--radius-sm)',
              background: 'var(--color-fog)',
              border: '1px solid rgba(163, 166, 175, 0.35)',
              color: 'var(--color-graphite)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              cursor: 'pointer', transition: 'all 0.15s ease',
            }}
            onMouseEnter={e => { e.currentTarget.style.background = 'var(--color-mist)' }}
            onMouseLeave={e => { e.currentTarget.style.background = 'var(--color-fog)' }}
          >
            <X size={15} />
          </button>

          {/* Header */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}>
            <div style={{
              width: 36, height: 36, borderRadius: 'var(--radius-sm)',
              background: 'var(--color-apricot)',
              border: '1px solid var(--color-apricot-mid)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              color: 'var(--color-rust)',
            }}>
              <Sliders size={17} />
            </div>
            <div>
              <h2 style={{ fontSize: '1rem', fontWeight: 700, color: 'var(--color-ink)', margin: 0, letterSpacing: '-0.01em' }}>
                AI Provider Settings
              </h2>
            </div>
          </div>

          <p style={{ fontSize: '0.8rem', color: 'var(--color-graphite)', lineHeight: 1.6, marginBottom: 22 }}>
            Configure custom API keys. Keys are stored locally in your browser and never sent to our servers.
          </p>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

            {/* Provider */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              <label style={{ fontSize: '0.7rem', fontWeight: 700, color: 'var(--color-graphite)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                LLM Provider
              </label>
              <select
                className="llm-select"
                value={provider}
                onChange={(e) => {
                  setProvider(e.target.value)
                  if (e.target.value === 'default') { setKey(''); setModel(''); setLimits(null) }
                }}
              >
                <option value="default">System Default (Groq Server Key)</option>
                <option value="groq">Custom Groq API Key</option>
                <option value="openrouter">Custom OpenRouter Key</option>
              </select>
            </div>

            {provider !== 'default' && (
              <>
                {/* API Key */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                  <label style={{ fontSize: '0.7rem', fontWeight: 700, color: 'var(--color-graphite)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                    API Key
                  </label>
                  <div style={{ position: 'relative' }}>
                    <input
                      className="llm-input"
                      type={showKey ? 'text' : 'password'}
                      placeholder={provider === 'groq' ? 'gsk_...' : 'sk-or-...'}
                      value={key}
                      onChange={(e) => setKey(e.target.value)}
                      style={{ paddingRight: 40, fontFamily: 'var(--font-mono)', fontSize: '0.82rem' }}
                    />
                    <button
                      type="button"
                      onClick={() => setShowKey(!showKey)}
                      style={{
                        position: 'absolute', right: 12, top: '50%', transform: 'translateY(-50%)',
                        background: 'none', border: 'none', color: 'var(--color-dove)', cursor: 'pointer', padding: 4,
                      }}
                    >
                      {showKey ? <EyeOff size={15} /> : <Eye size={15} />}
                    </button>
                  </div>
                </div>

                {/* Model override */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                  <label style={{ fontSize: '0.7rem', fontWeight: 700, color: 'var(--color-graphite)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                    Model Override <span style={{ color: 'var(--color-dove)', fontWeight: 400, textTransform: 'none' }}>(optional)</span>
                  </label>
                  <input
                    className="llm-input"
                    type="text"
                    placeholder={provider === 'groq' ? 'llama-3.3-70b-versatile' : 'meta-llama/llama-3.3-70b-instruct'}
                    value={model}
                    onChange={(e) => setModel(e.target.value)}
                    style={{ fontFamily: 'var(--font-mono)', fontSize: '0.82rem' }}
                  />
                </div>
              </>
            )}

            {/* Rate limits */}
            {key && (
              <div style={{
                padding: '14px 16px',
                background: 'var(--color-fog)',
                border: '1px solid rgba(163, 166, 175, 0.35)',
                borderRadius: 'var(--radius-sm)',
              }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
                  <span style={{ fontSize: '0.65rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--color-graphite)' }}>
                    API Request Limits
                  </span>
                  <button
                    type="button"
                    onClick={() => fetchLimits(key)}
                    disabled={loadingLimits}
                    style={{
                      display: 'flex', alignItems: 'center', gap: 4,
                      padding: '4px 10px', borderRadius: 'var(--radius-full)',
                      background: 'var(--color-white)',
                      border: '1px solid rgba(163, 166, 175, 0.4)',
                      color: 'var(--color-graphite)', fontSize: '0.68rem', fontWeight: 600,
                      cursor: loadingLimits ? 'not-allowed' : 'pointer',
                      opacity: loadingLimits ? 0.6 : 1,
                    }}
                  >
                    <RefreshCw size={11} style={{ animation: loadingLimits ? 'spin 0.8s linear infinite' : 'none' }} />
                    Refresh
                  </button>
                </div>

                {limits ? (
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
                    <div>
                      <span style={{ fontSize: '0.65rem', color: 'var(--color-graphite)', display: 'block', marginBottom: 2 }}>Remaining Requests</span>
                      <span style={{ fontSize: '1rem', fontWeight: 700, color: 'var(--color-ink)' }}>
                        {limits.remaining_requests?.toLocaleString() || 'N/A'}
                      </span>
                    </div>
                    <div>
                      <span style={{ fontSize: '0.65rem', color: 'var(--color-graphite)', display: 'block', marginBottom: 2 }}>Reset In</span>
                      <span style={{ fontSize: '1rem', fontWeight: 700, color: 'var(--color-rust)' }}>
                        {limits.reset_requests || 'N/A'}
                      </span>
                    </div>
                  </div>
                ) : (
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6, fontSize: '0.78rem', color: 'var(--color-graphite)' }}>
                    <AlertTriangle size={13} style={{ color: 'var(--color-rust)' }} />
                    Click Refresh to retrieve active rate status
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Buttons */}
          <div style={{
            display: 'flex', alignItems: 'center', gap: 10, marginTop: 24,
            paddingTop: 20, borderTop: '1px solid rgba(163, 166, 175, 0.25)',
          }}>
            <button
              onClick={handleClear}
              style={{
                flex: 1, padding: '10px 16px',
                borderRadius: 'var(--radius-full)',
                background: 'transparent',
                border: '1px solid rgba(192, 57, 43, 0.25)',
                color: 'rgba(192, 57, 43, 0.8)',
                fontSize: '0.82rem', fontWeight: 600,
                cursor: 'pointer', transition: 'all 0.15s ease',
              }}
              onMouseEnter={e => { e.currentTarget.style.background = 'rgba(192,57,43,0.05)' }}
              onMouseLeave={e => { e.currentTarget.style.background = 'transparent' }}
            >
              Clear Keys
            </button>

            <button
              onClick={handleSave}
              disabled={provider !== 'default' && !key.trim()}
              style={{
                flex: 2, padding: '10px 16px',
                borderRadius: 'var(--radius-full)',
                background: provider !== 'default' && !key.trim() ? 'var(--color-mist)' : 'var(--color-ink)',
                color: provider !== 'default' && !key.trim() ? 'var(--color-dove)' : 'var(--color-white)',
                fontSize: '0.88rem', fontWeight: 600, border: 'none',
                cursor: provider !== 'default' && !key.trim() ? 'not-allowed' : 'pointer',
                display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
                transition: 'opacity 0.15s ease',
              }}
              onMouseEnter={e => { if (!(provider !== 'default' && !key.trim())) e.currentTarget.style.opacity = '0.85' }}
              onMouseLeave={e => { e.currentTarget.style.opacity = '1' }}
            >
              {saveStatus ? (
                <><Check size={15} /> Saved!</>
              ) : (
                <>Save Settings</>
              )}
            </button>
          </div>
        </div>
      </div>
    </>
  )
}
