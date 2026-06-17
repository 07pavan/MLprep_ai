import React, { useState, useEffect } from 'react'
import { X, Sliders, Eye, EyeOff, Check, AlertTriangle, RefreshCw } from 'lucide-react'
import { getRateLimits } from '../api/client'

export default function LLMConfigModal({ isOpen, onClose }) {
  const [provider, setProvider] = useState('groq') // 'groq', 'openrouter', or 'default'
  const [key, setKey] = useState('')
  const [model, setModel] = useState('')
  const [showKey, setShowKey] = useState(false)
  const [limits, setLimits] = useState(null)
  const [loadingLimits, setLoadingLimits] = useState(false)
  const [saveStatus, setSaveStatus] = useState(false)

  // Load saved configurations from localStorage on mount/open
  useEffect(() => {
    if (isOpen) {
      const savedProvider = localStorage.getItem('customLlmProvider') || 'default'
      const savedKey = localStorage.getItem('customLlmKey') || ''
      const savedModel = localStorage.getItem('customLlmModel') || ''
      
      setProvider(savedProvider)
      setKey(savedKey)
      setModel(savedModel)
      setSaveStatus(false)
      
      if (savedKey) {
        fetchLimits(savedKey)
      } else {
        setLimits(null)
      }
    }
  }, [isOpen])

  const fetchLimits = async (activeKey) => {
    setLoadingLimits(true)
    try {
      // Temporarily write to localStorage so the HTTP interceptor uses it for this query
      const oldKey = localStorage.getItem('customLlmKey')
      localStorage.setItem('customLlmKey', activeKey)
      
      const data = await getRateLimits()
      setLimits(data)
      
      // Restore state if needed
      if (!activeKey) {
        localStorage.removeItem('customLlmKey')
      }
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
      if (model.trim()) {
        localStorage.setItem('customLlmModel', model.trim())
      } else {
        localStorage.removeItem('customLlmModel')
      }
    }
    setSaveStatus(true)
    setTimeout(() => {
      setSaveStatus(false)
      onClose()
    }, 1000)
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
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-fade-in">
      <div className="w-full max-w-md rounded-2xl border border-[rgba(255,255,255,0.08)] bg-[#0d0e15] shadow-2xl overflow-hidden p-6 relative">
        <button 
          onClick={onClose}
          className="absolute top-4 right-4 p-1 rounded-lg hover:bg-white/5 text-[#8E9AAF] hover:text-[#F0F0F8] transition-colors"
        >
          <X size={18} />
        </button>

        <div className="flex items-center gap-2 mb-4">
          <Sliders size={20} className="text-[#FF007F]" />
          <h2 className="text-lg font-bold text-[#F0F0F8]">AI Provider Configuration</h2>
        </div>

        <p className="text-xs text-[#8E9AAF] mb-6 leading-relaxed">
          Configure custom API keys. Your keys are stored locally in your browser and are never saved on the server database.
        </p>

        <div className="space-y-4">
          {/* Provider Selector */}
          <div className="space-y-1">
            <label className="block text-xs font-semibold text-[#8E9AAF]">LLM Provider</label>
            <select
              value={provider}
              onChange={(e) => {
                setProvider(e.target.value)
                if (e.target.value === 'default') {
                  setKey('')
                  setModel('')
                  setLimits(null)
                }
              }}
              className="w-full bg-[#141520] border border-[rgba(255,255,255,0.06)] rounded-lg p-2.5 text-[#F0F0F8] text-sm focus:outline-none focus:border-[#FF007F] transition-colors"
            >
              <option value="default">System Default (Groq Server Key)</option>
              <option value="groq">Custom Groq API Key</option>
              <option value="openrouter">Custom OpenRouter Key</option>
            </select>
          </div>

          {provider !== 'default' && (
            <>
              {/* API Key */}
              <div className="space-y-1">
                <label className="block text-xs font-semibold text-[#8E9AAF]">API Key</label>
                <div className="relative">
                  <input
                    type={showKey ? 'text' : 'password'}
                    placeholder={provider === 'groq' ? 'gsk_...' : 'sk-or-...'}
                    value={key}
                    onChange={(e) => setKey(e.target.value)}
                    className="w-full bg-[#141520] border border-[rgba(255,255,255,0.06)] rounded-lg p-2.5 pr-10 text-[#F0F0F8] text-sm font-mono focus:outline-none focus:border-[#FF007F] transition-colors"
                  />
                  <button
                    type="button"
                    onClick={() => setShowKey(!showKey)}
                    className="absolute inset-y-0 right-3 flex items-center text-[#8E9AAF] hover:text-[#F0F0F8]"
                  >
                    {showKey ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                </div>
              </div>

              {/* Model Override */}
              <div className="space-y-1">
                <label className="block text-xs font-semibold text-[#8E9AAF]">
                  Model Override (Optional)
                </label>
                <input
                  type="text"
                  placeholder={provider === 'groq' ? 'llama-3.3-70b-versatile' : 'meta-llama/llama-3.3-70b-instruct'}
                  value={model}
                  onChange={(e) => setModel(e.target.value)}
                  className="w-full bg-[#141520] border border-[rgba(255,255,255,0.06)] rounded-lg p-2.5 text-[#F0F0F8] text-sm font-mono focus:outline-none focus:border-[#FF007F] transition-colors"
                />
              </div>
            </>
          )}

          {/* Rate Limits */}
          {key && (
            <div className="p-4 rounded-xl border border-[rgba(255,255,255,0.05)] bg-[#141520]/40 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-bold uppercase tracking-wider text-[#8E9AAF]">API Request Limits</span>
                <button
                  type="button"
                  onClick={() => fetchLimits(key)}
                  disabled={loadingLimits}
                  className="p-1 rounded-md hover:bg-white/5 text-[#8E9AAF] hover:text-[#FF007F] transition-colors flex items-center gap-1 disabled:opacity-50"
                  title="Check rate limits"
                >
                  <RefreshCw size={12} className={loadingLimits ? 'animate-spin' : ''} />
                  <span className="text-[10px] font-bold">Refresh</span>
                </button>
              </div>

              {limits ? (
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-0.5">
                    <span className="text-[10px] text-[#8E9AAF] block">Remaining Requests</span>
                    <span className="text-sm font-extrabold text-[#F0F0F8]">
                      {limits.remaining_requests?.toLocaleString() || 'N/A'}
                    </span>
                  </div>
                  <div className="space-y-0.5">
                    <span className="text-[10px] text-[#8E9AAF] block">Request Reset In</span>
                    <span className="text-sm font-extrabold text-[#FF007F]">
                      {limits.reset_requests || 'N/A'}
                    </span>
                  </div>
                </div>
              ) : (
                <div className="text-center py-1 text-xs text-[#8E9AAF] flex items-center justify-center gap-1.5">
                  <AlertTriangle size={12} className="text-amber-500/80" />
                  <span>Click Refresh to retrieve active rate status</span>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Buttons */}
        <div className="flex items-center gap-3 mt-6 pt-4 border-t border-[rgba(255,255,255,0.05)]">
          <button
            onClick={handleClear}
            className="px-4 py-2 rounded-lg border border-red-500/20 text-red-400 hover:bg-red-500/10 text-xs font-bold transition-all flex-grow cursor-pointer"
          >
            Clear Custom Keys
          </button>
          
          <button
            onClick={handleSave}
            disabled={provider !== 'default' && !key.trim()}
            className="px-4 py-2 rounded-lg bg-[#FF007F] hover:bg-[#FF007F]/90 text-white text-xs font-bold transition-all disabled:opacity-50 flex items-center justify-center gap-1.5 flex-grow cursor-pointer shadow-lg"
          >
            {saveStatus ? (
              <>
                <Check size={14} /> Saved!
              </>
            ) : (
              <>Save Settings</>
            )}
          </button>
        </div>
      </div>
    </div>
  )
}
