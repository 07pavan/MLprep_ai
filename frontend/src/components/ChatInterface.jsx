import React, { useState, useRef, useEffect, useMemo } from 'react'
import { Send, Trash2, Brain } from 'lucide-react'
import { useChat } from '../hooks/useChat'
import MessageBubble from './MessageBubble'

const GENERIC_SUGGESTIONS = [
  'Show me the first 5 rows',
  'What are the column types?',
  'Show summary statistics',
  'Which column has the most missing values?',
  'Plot a bar chart of the top categories',
  'Find any outliers in the data',
]

export default function ChatInterface({ sessionId, datasetMeta }) {
  const { messages, isLoading, sendQuestion, clearHistory } = useChat()
  const [input, setInput] = useState('')
  const feedRef = useRef(null)

  // Auto-scroll on new messages
  useEffect(() => {
    if (feedRef.current) {
      feedRef.current.scrollTop = feedRef.current.scrollHeight
    }
  }, [messages])

  const suggestions = useMemo(() => {
    if (!datasetMeta?.columns) return GENERIC_SUGGESTIONS
    const cols = datasetMeta.columns
    const numCols = cols.filter((c) => ['int64', 'float64', 'int32', 'float32'].includes(c.dtype))
    const catCols = cols.filter((c) => c.dtype === 'object')

    const dynamic = []
    dynamic.push('Show me the first 5 rows')
    if (numCols.length > 0) dynamic.push(`Show summary statistics for ${numCols[0].name}`)
    if (catCols.length > 0) dynamic.push(`Show ${catCols[0].name} distribution as a bar chart`)
    if (numCols.length >= 2) dynamic.push(`Scatter plot of ${numCols[0].name} vs ${numCols[1].name}`)
    dynamic.push('Which columns have missing values?')
    if (catCols.length > 0 && numCols.length > 0)
      dynamic.push(`Compare ${numCols[0].name} by ${catCols[0].name}`)
    return dynamic.slice(0, 6)
  }, [datasetMeta])

  const handleSend = () => {
    const q = input.trim()
    if (!q || isLoading) return
    setInput('')
    sendQuestion(sessionId, q)
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', minHeight: 0 }}>
      {/* Memory banner */}
      {messages.length > 0 && (
        <div className="memory-banner">
          <Brain size={14} />
          Memory active — agent remembers last {Math.min(Math.floor(messages.length / 2), 4)} question{messages.length > 2 ? 's' : ''}
        </div>
      )}

      {/* Chat feed */}
      <div ref={feedRef} className="chat-feed" style={{ flex: 1, overflowY: 'auto' }}>
        {messages.length === 0 ? (
          <div className="chat-hero">
            <h1 className="chat-hero-title">
              <span className="gradient-text">Ask anything about your data</span>
            </h1>
            <p className="chat-hero-subtitle">
              I can analyze, visualize, and discover insights from your dataset. Try a question below.
            </p>
            <div className="suggestions-grid">
              {suggestions.map((s, i) => (
                <button
                  key={i}
                  className="suggestion-chip"
                  onClick={() => { setInput(s); sendQuestion(sessionId, s) }}
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        ) : (
          messages.map((msg) => <MessageBubble key={msg.id} message={msg} />)
        )}

        {/* Loading indicator */}
        {isLoading && (
          <div className="message-row agent">
            <div className="message-bubble agent" style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <div className="spinner" style={{ width: 20, height: 20 }} />
              <span style={{ color: 'var(--text-muted)', fontSize: '0.84rem' }}>Analyzing…</span>
            </div>
          </div>
        )}
      </div>

      {/* Input bar */}
      <div className="chat-input-bar">
        {messages.length > 0 && (
          <button className="btn-icon" onClick={clearHistory} title="Clear history">
            <Trash2 size={16} />
          </button>
        )}
        <textarea
          className="input-field"
          placeholder="Ask a question about your data…"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          rows={1}
        />
        <button
          className="chat-send-btn"
          onClick={handleSend}
          disabled={!input.trim() || isLoading}
        >
          <Send size={18} />
        </button>
      </div>
    </div>
  )
}
