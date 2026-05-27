import React, { useState } from 'react'
import { useSession } from './hooks/useSession'
import Layout from './components/Layout'
import FileUpload from './components/FileUpload'
import ChatInterface from './components/ChatInterface'
import CleaningPanel from './components/CleaningPanel'
import TraceViewer from './components/TraceViewer'

// ── Overview page (inline) ──────────────────────────────────────
function OverviewPage({ datasetMeta }) {
  if (!datasetMeta) return null
  const { filename, shape, columns, memoryMb } = datasetMeta

  return (
    <div>
      <div className="overview-header">
        <h1><span className="gradient-text">Dataset Overview</span></h1>
        <p>{filename} · {shape.rows.toLocaleString()} rows × {shape.cols} columns · {memoryMb} MB</p>
      </div>

      <div className="stat-grid">
        <div className="metric-card">
          <div className="metric-value gradient-text">{shape.rows.toLocaleString()}</div>
          <div className="metric-label">Rows</div>
        </div>
        <div className="metric-card">
          <div className="metric-value gradient-text">{shape.cols}</div>
          <div className="metric-label">Columns</div>
        </div>
        <div className="metric-card">
          <div className="metric-value gradient-text">{memoryMb}</div>
          <div className="metric-label">MB</div>
        </div>
        <div className="metric-card">
          <div className="metric-value gradient-text">
            {columns.filter(c => c.nullCount > 0).length}
          </div>
          <div className="metric-label">W/ Nulls</div>
        </div>
      </div>

      <h2 style={{ fontSize: '1rem', fontWeight: 600, margin: '24px 0 12px' }}>Columns</h2>
      <div className="columns-grid">
        {columns.map((col) => (
          <div key={col.name} className="column-card">
            <div className="column-card-name">{col.name}</div>
            <div className="column-card-meta">
              <span>{col.dtype}</span>
              <span>{col.uniqueCount.toLocaleString()} unique</span>
              <span>{col.nullCount > 0 ? `${col.nullCount} nulls` : '✓ complete'}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

// ── Insights placeholder page ──────────────────────────────────
function InsightsPage() {
  return (
    <div className="chat-hero">
      <h1 className="chat-hero-title">
        <span className="gradient-text">Auto Insights</span>
      </h1>
      <p className="chat-hero-subtitle">
        Ask questions in the Chat tab and insights will be generated automatically.
        You can also ask "Give me insights about this data" to get a full analysis.
      </p>
    </div>
  )
}

// ── Root App ────────────────────────────────────────────────────
export default function App() {
  const {
    sessionId, datasetMeta,
    isUploading, uploadProgress, uploadError,
    uploadDataset, clearSession,
  } = useSession()

  const [activePage, setActivePage] = useState('chat')

  // No session → show upload page
  if (!sessionId) {
    return (
      <FileUpload
        onUpload={uploadDataset}
        isUploading={isUploading}
        uploadProgress={uploadProgress}
        uploadError={uploadError}
      />
    )
  }

  // With session → show layout + page
  const renderPage = () => {
    switch (activePage) {
      case 'chat':
        return <ChatInterface sessionId={sessionId} datasetMeta={datasetMeta} />
      case 'overview':
        return <OverviewPage datasetMeta={datasetMeta} />
      case 'insights':
        return <InsightsPage />
      case 'clean':
        return <CleaningPanel sessionId={sessionId} />
      case 'traces':
        return <TraceViewer sessionId={sessionId} />
      default:
        return <ChatInterface sessionId={sessionId} datasetMeta={datasetMeta} />
    }
  }

  return (
    <Layout
      activePage={activePage}
      onPageChange={setActivePage}
      datasetMeta={datasetMeta}
      onClearSession={clearSession}
    >
      {renderPage()}
    </Layout>
  )
}
