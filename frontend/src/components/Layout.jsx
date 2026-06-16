import React, { useState, useEffect } from 'react'
import {
  Menu, X, MessageSquare, BarChart2, Sparkles, HelpCircle,
  Wrench, Database, LogOut, Activity, ShieldCheck, Brain, Folder, Wand2, AreaChart, BookOpen,
} from 'lucide-react'
import { useAuth } from '../hooks/useAuth'

const NAV_ITEMS = [
  { id: 'chat', label: 'Chat', icon: MessageSquare },
  { id: 'overview', label: 'Overview', icon: BarChart2 },
  { id: 'datasets', label: 'Datasets', icon: Folder },
  { id: 'profile', label: 'Profile', icon: Database },
  { id: 'quality', label: 'Quality', icon: ShieldCheck },
  { id: 'ml-readiness', label: 'ML Readiness', icon: Brain },
  { id: 'insights', label: 'Insights', icon: Sparkles },
  { id: 'explanation', label: 'AI Explainer', icon: HelpCircle },
  { id: 'visualization', label: 'AI Visualizer', icon: AreaChart },
  { id: 'story', label: 'AI Storytelling', icon: BookOpen },
  { id: 'clean', label: 'Clean', icon: Wrench },
  { id: 'cleaning-planner', label: 'AI Planner', icon: Wand2 },
  { id: 'traces', label: 'Traces', icon: Activity },
]

export default function Layout({ children, activePage, onPageChange, datasetMeta, onClearSession }) {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const { user, logOut } = useAuth()

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

        {/* Sidebar Footer — User profile and session reset */}
        <div className="sidebar-footer" style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {datasetMeta && (
            <button className="btn-ghost" style={{ width: '100%', justifyContent: 'flex-start', color: '#ef4444' }} onClick={onClearSession}>
              <X size={16} /> Close Dataset
            </button>
          )}
          
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: 10,
            padding: '12px 4px 0',
            borderTop: '1px solid var(--border-subtle)',
            marginTop: 4
          }}>
            <div style={{
              width: 32,
              height: 32,
              borderRadius: '50%',
              background: 'linear-gradient(135deg, var(--accent-1), var(--accent-2))',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontWeight: 700,
              fontSize: '0.8rem',
              color: '#fff',
              flexShrink: 0
            }}>
              {user?.displayName ? user.displayName[0].toUpperCase() : 'U'}
            </div>
            
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{
                fontSize: '0.8rem',
                fontWeight: 600,
                color: 'var(--text-primary)',
                textOverflow: 'ellipsis',
                overflow: 'hidden',
                whiteSpace: 'nowrap'
              }}>
                {user?.displayName || 'User'}
              </div>
              <div style={{
                fontSize: '0.7rem',
                color: 'var(--text-secondary)',
                textOverflow: 'ellipsis',
                overflow: 'hidden',
                whiteSpace: 'nowrap',
                opacity: 0.7
              }}>
                {user?.email}
              </div>
            </div>

            <button
              className="btn-icon"
              onClick={logOut}
              title="Log Out"
              style={{ width: 28, height: 28, flexShrink: 0 }}
            >
              <LogOut size={14} />
            </button>
          </div>
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
