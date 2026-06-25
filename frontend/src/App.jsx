import React, { useState, useEffect } from 'react'
import { AuthProvider, useAuth } from './hooks/useAuth'
import AuthPage from './components/AuthPage'
import { useSession } from './hooks/useSession'
import Layout from './components/Layout'
import FileUpload from './components/FileUpload'
import ChatInterface from './components/ChatInterface'
import CleaningPanel from './components/CleaningPanel'
import CleaningPlannerPage from './components/CleaningPlannerPage'
import TraceViewer from './components/TraceViewer'
import InsightPanel from './components/InsightPanel'
import DatasetProfile from './components/DatasetProfile'
import DataQuality from './components/DataQuality'
import MLReadiness from './components/MLReadiness'
import DatasetManagement from './components/DatasetManagement'
import ExplanationPanel from './components/ExplanationPanel'
import VisualizationPanel from './components/VisualizationPanel'
import StoryPanel from './components/StoryPanel'


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

// ── Main Dashboard Shell ─────────────────────────────────────────
function DashboardContent() {
  const { user } = useAuth()
  const {
    sessionId, datasetMeta, currentDatasetId,
    isUploading, uploadProgress, uploadError, isSuccess,
    uploadDataset, importDataset, activateSession, clearSession,
  } = useSession(user?.uid)   // ← scoped to this user's UID

  const getInitialPage = () => {
    const path = window.location.pathname
    if (path === '/profile') return 'profile'
    if (path === '/quality') return 'quality'
    if (path === '/ml-readiness') return 'ml-readiness'
    if (path === '/datasets') return 'datasets'
    if (path === '/insights') return 'insights'
    if (path === '/explanation') return 'explanation'
    if (path === '/visualization') return 'visualization'
    if (path === '/story') return 'story'
    if (path === '/clean') return 'clean'
    if (path === '/cleaning-planner') return 'cleaning-planner'
    if (path === '/traces') return 'traces'
    if (path === '/overview') return 'overview'
    return 'chat'
  }

  const [activePage, setActivePage] = useState(getInitialPage)

  const handlePageChange = (page) => {
    setActivePage(page)
    const path = page === 'chat' ? '/' : `/${page}`
    window.history.pushState(null, '', path)
  }

  useEffect(() => {
    const handlePopState = () => {
      setActivePage(getInitialPage())
    }
    window.addEventListener('popstate', handlePopState)
    return () => window.removeEventListener('popstate', handlePopState)
  }, [])

  // No dataset session → show upload page unless visiting datasets page
  if (!sessionId) {
    if (activePage === 'datasets') {
      return (
        <Layout
          activePage={activePage}
          onPageChange={handlePageChange}
          datasetMeta={null}
          onClearSession={clearSession}
        >
          <DatasetManagement 
            onActivateSuccess={activateSession} 
            currentDatasetId={currentDatasetId} 
            onDeleteActiveDataset={clearSession}
          />
        </Layout>
      )
    }
    return (
      <FileUpload
        onUpload={uploadDataset}
        onImportURL={importDataset}
        isUploading={isUploading}
        uploadProgress={uploadProgress}
        uploadError={uploadError}
        isSuccess={isSuccess}
      />
    )
  }

  // With session → show layout + page
  const renderPage = () => {
    switch (activePage) {
      case 'chat':
        return <ChatInterface sessionId={sessionId} datasetMeta={datasetMeta} onClearSession={clearSession} />
      case 'overview':
        return <OverviewPage datasetMeta={datasetMeta} />
      case 'datasets':
        return (
          <DatasetManagement 
            onActivateSuccess={activateSession} 
            currentDatasetId={currentDatasetId} 
            onDeleteActiveDataset={clearSession}
          />
        )
      case 'profile':
        return <DatasetProfile sessionId={sessionId} />
      case 'quality':
        return <DataQuality sessionId={sessionId} />
      case 'ml-readiness':
        return <MLReadiness sessionId={sessionId} />
      case 'insights':
        return <InsightPanel sessionId={sessionId} />
      case 'explanation':
        return <ExplanationPanel sessionId={sessionId} />
      case 'visualization':
        return <VisualizationPanel sessionId={sessionId} />
      case 'story':
        return <StoryPanel sessionId={sessionId} />
      case 'clean':
        return <CleaningPanel sessionId={sessionId} />
      case 'cleaning-planner':
        return (
          <CleaningPlannerPage
            sessionId={sessionId}
            currentDatasetId={currentDatasetId}
          />
        )
      case 'traces':
        return <TraceViewer sessionId={sessionId} />
      default:
        return <ChatInterface sessionId={sessionId} datasetMeta={datasetMeta} onClearSession={clearSession} />
    }
  }

  return (
    <Layout
      activePage={activePage}
      onPageChange={handlePageChange}
      datasetMeta={datasetMeta}
      onClearSession={clearSession}
    >
      {renderPage()}
    </Layout>
  )
}

// ── Root App Wrapper ─────────────────────────────────────────────
function AppShell() {
  const { user, loading } = useAuth()

  if (loading) {
    return (
      <div style={{
        minHeight: '100vh',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'var(--bg-primary)',
        gap: 20,
      }}>
        <div style={{
          width: 56, height: 56,
          borderRadius: 'var(--radius-lg)',
          background: 'var(--color-vermillion-signal)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 26,
          boxShadow: 'var(--shadow-subtle)',
        }}>🧠</div>
        <div style={{
          width: 32, height: 32, borderRadius: '50%',
          border: '3px solid var(--color-cloud)',
          borderTopColor: 'var(--color-vermillion-signal)',
          animation: 'spin 0.8s linear infinite',
        }} />
        <div style={{ textAlign: 'center' }}>
          <div style={{
            fontSize: '1.2rem', fontWeight: 600,
            color: 'var(--color-slate-900)',
            marginBottom: 4,
            letterSpacing: '-0.01em',
          }}>
            MLPrep AI<span style={{ color: 'var(--color-vermillion-signal)' }}>*</span>
          </div>
          <div style={{ color: 'var(--text-muted)', fontSize: '0.78rem', textTransform: 'uppercase', letterSpacing: '0.025em' }}>
            Initializing…
          </div>
        </div>
      </div>
    )
  }

  if (!user) {
    return <AuthPage />
  }

  return <DashboardContent />
}

export default function App() {
  return (
    <AuthProvider>
      <AppShell />
    </AuthProvider>
  )
}
