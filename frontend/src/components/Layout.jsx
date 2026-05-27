import React, { useState, useEffect } from 'react'
import {
  Menu, X, MessageSquare, BarChart2, Sparkles,
  Wrench, Database, LogOut, Activity,
} from 'lucide-react'

const NAV_ITEMS = [
  { id: 'chat', label: 'Chat', icon: MessageSquare },
  { id: 'overview', label: 'Overview', icon: BarChart2 },
  { id: 'insights', label: 'Insights', icon: Sparkles },
  { id: 'clean', label: 'Clean', icon: Wrench },
  { id: 'traces', label: 'Traces', icon: Activity },
]

export default function Layout({ children, activePage, onPageChange, datasetMeta, onClearSession }) {
  const [sidebarOpen, setSidebarOpen] = useState(false)

  // Close sidebar on page change (mobile)
  useEffect(() => { setSidebarOpen(false) }, [activePage])

  return (
    <div className="app-shell">
      {/* Sidebar overlay */}
      <div
        className={`sidebar-overlay ${sidebarOpen ? 'visible' : ''}`}
        onClick={() => setSidebarOpen(false)}
      />

      {/* Sidebar */}
      <aside className={`sidebar ${sidebarOpen ? 'open' : ''}`}>
        <div className="sidebar-brand">
          <div className="sidebar-brand-icon"><Database size={22} /></div>
          <span className="sidebar-brand-text">DataAI</span>
          <button
            className="btn-icon"
            style={{ marginLeft: 'auto', display: 'none' }}
            onClick={() => setSidebarOpen(false)}
          >
            <X size={18} />
          </button>
        </div>

        {datasetMeta && (
          <div className="sidebar-dataset">
            <div className="sidebar-dataset-name">{datasetMeta.filename}</div>
            <div className="sidebar-dataset-meta">
              {datasetMeta.shape.rows.toLocaleString()} rows × {datasetMeta.shape.cols} cols
              &nbsp;·&nbsp;{datasetMeta.memoryMb} MB
            </div>
          </div>
        )}

        <nav className="sidebar-nav">
          {NAV_ITEMS.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              className={`sidebar-nav-item ${activePage === id ? 'active' : ''}`}
              onClick={() => onPageChange(id)}
            >
              <Icon size={18} />
              {label}
            </button>
          ))}
        </nav>

        <div className="sidebar-footer">
          <button className="btn-ghost" style={{ width: '100%' }} onClick={onClearSession}>
            <LogOut size={16} /> Reset Session
          </button>
        </div>
      </aside>

      {/* Mobile top bar */}
      <div className="top-bar">
        <button className="top-bar-btn" onClick={() => setSidebarOpen(true)}>
          <Menu size={22} />
        </button>
        <span className="top-bar-title">{NAV_ITEMS.find(i => i.id === activePage)?.label || 'DataAI'}</span>
        {datasetMeta && (
          <span className="top-bar-chip">{datasetMeta.filename}</span>
        )}
      </div>

      {/* Main content */}
      <div className="main-content">
        <div className="main-inner">{children}</div>
      </div>

      {/* Mobile bottom nav */}
      <div className="bottom-nav">
        {NAV_ITEMS.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            className={`bottom-nav-item ${activePage === id ? 'active' : ''}`}
            onClick={() => onPageChange(id)}
          >
            <Icon />
            <span>{label}</span>
          </button>
        ))}
      </div>
    </div>
  )
}
