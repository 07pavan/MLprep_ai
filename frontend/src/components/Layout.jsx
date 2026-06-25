import React, { useState, useEffect, useRef } from 'react'
import {
  MessageSquare, BarChart2, Sparkles, HelpCircle,
  Wrench, Database, LogOut, Activity, ShieldCheck, Brain,
  Folder, Wand2, AreaChart, BookOpen, Sliders, AlertTriangle,
  ChevronRight, Menu, X, Upload, Plus, Zap
} from 'lucide-react'
import { useAuth } from '../hooks/useAuth'
import LLMConfigModal from './LLMConfigModal'

/* ── Nav groups ─────────────────────────────────────────────────── */
const NAV_GROUPS = [
  {
    label: 'Core',
    items: [
      { id: 'chat',     label: 'AI Copilot',    icon: MessageSquare, hot: true },
      { id: 'overview', label: 'Overview',       icon: BarChart2 },
      { id: 'datasets', label: 'My Datasets',    icon: Folder },
    ],
  },
  {
    label: 'Analysis',
    items: [
      { id: 'profile',      label: 'Data Profile',    icon: Database },
      { id: 'quality',      label: 'Quality Check',   icon: ShieldCheck },
      { id: 'ml-readiness', label: 'ML Readiness',    icon: Brain },
      { id: 'insights',     label: 'AI Insights',     icon: Sparkles },
    ],
  },
  {
    label: 'AI Tools',
    items: [
      { id: 'explanation',      label: 'AI Explainer',    icon: HelpCircle },
      { id: 'visualization',    label: 'AI Visualizer',   icon: AreaChart },
      { id: 'story',            label: 'Data Story',      icon: BookOpen },
      { id: 'clean',            label: 'Data Cleaner',    icon: Wrench },
      { id: 'cleaning-planner', label: 'AI Planner',      icon: Wand2 },
    ],
  },
  {
    label: 'System',
    items: [
      { id: 'traces', label: 'Traces', icon: Activity },
    ],
  },
]

const ALL_NAV = NAV_GROUPS.flatMap(g => g.items)

/* ── Avatar with initials ───────────────────────────────────────── */
function UserAvatar({ user, size = 32 }) {
  const initials = user?.displayName
    ? user.displayName.split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase()
    : user?.email?.[0]?.toUpperCase() || 'U'

  return (
    <div style={{
      width: size, height: size,
      borderRadius: '50%',
      background: 'var(--color-vermillion-signal)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      fontWeight: 700, fontSize: size * 0.35,
      color: '#fff', flexShrink: 0,
      boxShadow: 'var(--shadow-subtle)',
    }}>
      {user?.photoURL ? (
        <img src={user.photoURL} alt="" style={{ width: '100%', height: '100%', borderRadius: '50%', objectFit: 'cover' }} />
      ) : initials}
    </div>
  )
}

/* ── Sidebar nav item ───────────────────────────────────────────── */
function NavItem({ item, isActive, onClick, collapsed }) {
  const { id, label, icon: Icon, hot } = item
  const [hovered, setHovered] = useState(false)

  return (
    <button
      onClick={() => onClick(id)}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      title={collapsed ? label : undefined}
      style={{
        display: 'flex', alignItems: 'center',
        gap: collapsed ? 0 : 10,
        padding: collapsed ? '10px' : '9px 12px',
        borderRadius: 'var(--radius-md)',
        width: '100%',
        justifyContent: collapsed ? 'center' : 'flex-start',
        color: isActive ? 'var(--color-vermillion-signal)' : (hovered ? 'var(--text-primary)' : 'var(--text-secondary)'),
        background: isActive
          ? 'rgba(228, 43, 12, 0.06)'
          : (hovered ? 'var(--bg-glass-hover)' : 'transparent'),
        border: isActive ? '1px solid rgba(228, 43, 12, 0.22)' : '1px solid transparent',
        cursor: 'pointer',
        transition: 'all 0.18s ease',
        fontFamily: 'inherit',
        position: 'relative',
        fontSize: '0.855rem',
        fontWeight: isActive ? 600 : 500,
        textAlign: 'left',
        whiteSpace: 'nowrap',
        overflow: 'hidden',
      }}
    >
      {/* Active indicator bar */}
      {isActive && (
        <div style={{
          position: 'absolute', left: 0, top: '20%', bottom: '20%',
          width: 3, borderRadius: 3,
          background: 'var(--color-vermillion-signal)',
        }} />
      )}

      <Icon
        size={17}
        style={{
          flexShrink: 0,
          color: isActive ? 'var(--color-vermillion-signal)' : 'inherit',
          opacity: isActive ? 1 : 0.75,
        }}
      />

      {!collapsed && (
        <>
          <span style={{ flex: 1 }}>{label}</span>
          {hot && (
            <span style={{
              fontSize: '0.58rem', fontWeight: 700,
              padding: '2px 6px', borderRadius: 'var(--radius-sm)',
              background: 'rgba(228, 43, 12, 0.1)',
              border: '1px solid rgba(228, 43, 12, 0.2)',
              color: 'var(--color-vermillion-signal)',
              letterSpacing: '0.04em',
            }}>
              AI
            </span>
          )}
        </>
      )}
    </button>
  )
}

export default function Layout({ children, activePage, onPageChange, datasetMeta, onClearSession }) {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [collapsed, setCollapsed] = useState(false)
  const [isConfigOpen, setIsConfigOpen] = useState(false)
  const { user, logOut } = useAuth()
  const sidebarRef = useRef(null)

  const [isMobile, setIsMobile] = useState(window.innerWidth <= 768)

  useEffect(() => {
    const handleResize = () => setIsMobile(window.innerWidth <= 768)
    window.addEventListener('resize', handleResize)
    return () => window.removeEventListener('resize', handleResize)
  }, [])

  const sidebarWidth = isMobile ? 0 : (collapsed ? 64 : 260)

  useEffect(() => { setSidebarOpen(false) }, [activePage])

  // Close mobile sidebar on outside click
  useEffect(() => {
    const handler = (e) => {
      if (sidebarOpen && sidebarRef.current && !sidebarRef.current.contains(e.target)) {
        setSidebarOpen(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [sidebarOpen])

  const visibleNavGroups = NAV_GROUPS.map(group => {
    if (!datasetMeta) {
      return {
        ...group,
        items: group.items.filter(item => item.id === 'datasets')
      }
    }
    return group
  }).filter(group => group.items.length > 0)

  const visibleAllNav = datasetMeta 
    ? ALL_NAV 
    : ALL_NAV.filter(item => item.id === 'datasets')

  const activeLabel = visibleAllNav.find(i => i.id === activePage)?.label || 'MLPrep AI'

  return (
    <>
      <style>{`
        @keyframes slideInLeft { from{opacity:0;transform:translateX(-12px)} to{opacity:1;transform:translateX(0)} }
        @keyframes spin { to{transform:rotate(360deg)} }
        .main-page-content { animation: slideInLeft 0.25s cubic-bezier(0.16,1,0.3,1) forwards; }
        .sidebar-scroll::-webkit-scrollbar { width: 3px; }
        .sidebar-scroll::-webkit-scrollbar-track { background: transparent; }
        .sidebar-scroll::-webkit-scrollbar-thumb { background: var(--color-cloud); border-radius: 3px; }
        @media (max-width: 768px) {
          .desktop-sidebar { display: none !important; }
          .mobile-topbar { display: flex !important; }
          .mobile-bottom-nav { display: flex !important; }
          .main-content-area { margin-left: 0 !important; padding-bottom: 72px; }
        }
        @media (min-width: 769px) {
          .mobile-topbar { display: none !important; }
          .mobile-sidebar-overlay { display: none !important; }
          .mobile-bottom-nav { display: none !important; }
        }
      `}</style>

      <div style={{ display: 'flex', minHeight: '100vh', background: 'var(--bg-primary)' }}>

        {/* ── Mobile Overlay ─────────────────────────────────────── */}
        {sidebarOpen && (
          <div
            className="mobile-sidebar-overlay"
            onClick={() => setSidebarOpen(false)}
            style={{
              position: 'fixed', inset: 0, zIndex: 98,
              background: 'rgba(0,0,0,0.3)', backdropFilter: 'blur(2px)',
            }}
          />
        )}

        {/* ── Desktop Sidebar ─────────────────────────────────────── */}
        <aside
          ref={sidebarRef}
          className="desktop-sidebar"
          style={{
            width: sidebarWidth,
            minWidth: sidebarWidth,
            height: '100vh',
            position: 'fixed',
            top: 0, left: 0, bottom: 0,
            zIndex: 100,
            background: 'var(--bg-surface)',
            borderRight: '1px solid var(--border-subtle)',
            display: 'flex',
            flexDirection: 'column',
            transition: 'width 0.25s cubic-bezier(0.4,0,0.2,1)',
            overflow: 'hidden',
          }}
        >
          {/* Brand */}
          <div style={{
            padding: collapsed ? '18px 0' : '18px 16px',
            display: 'flex',
            alignItems: 'center',
            gap: 10,
            borderBottom: '1px solid var(--border-subtle)',
            justifyContent: collapsed ? 'center' : 'flex-start',
            flexShrink: 0,
            minHeight: 64,
          }}>
            <div style={{
              width: 36, height: 36, borderRadius: 'var(--radius-lg)',
              background: 'var(--color-vermillion-signal)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 18, flexShrink: 0,
              boxShadow: 'var(--shadow-subtle)',
            }}>
              🧠
            </div>
            {!collapsed && (
              <>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{
                    fontWeight: 600, fontSize: '1.1rem', letterSpacing: '-0.025em',
                    color: 'var(--color-slate-900)',
                  }}>
                    MLPrep AI<span style={{ color: 'var(--color-vermillion-signal)' }}>*</span>
                  </div>
                  <div style={{ fontSize: '0.65rem', color: 'var(--color-slate-600)', marginTop: -1 }}>
                    Data Intelligence Platform
                  </div>
                </div>
                <button
                  onClick={() => setCollapsed(true)}
                  style={{
                    width: 26, height: 26, borderRadius: 'var(--radius-md)',
                    background: 'var(--bg-glass-hover)',
                    border: '1px solid var(--border-subtle)',
                    color: 'var(--color-slate-700)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    cursor: 'pointer', flexShrink: 0,
                    transition: 'all 0.2s ease',
                  }}
                  title="Collapse sidebar"
                >
                  <ChevronRight size={13} style={{ transform: 'rotate(180deg)' }} />
                </button>
              </>
            )}
            {collapsed && (
              <button
                onClick={() => setCollapsed(false)}
                style={{
                  position: 'absolute', top: 18, right: -10,
                  width: 20, height: 20, borderRadius: 'var(--radius-sm)',
                  background: 'rgba(228, 43, 12, 0.15)',
                  border: '1px solid rgba(228, 43, 12, 0.3)',
                  color: 'var(--color-vermillion-signal)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  cursor: 'pointer', zIndex: 10,
                }}
              >
                <ChevronRight size={11} />
              </button>
            )}
          </div>

          {/* Dataset badge */}
          {datasetMeta && !collapsed && (
            <div style={{
              margin: '12px 12px 4px',
              padding: '10px 13px',
              background: 'var(--color-vellum)',
              border: '1px solid var(--color-cloud)',
              borderRadius: 'var(--radius-lg)',
              flexShrink: 0,
            }}>
              <div style={{
                fontSize: '0.8rem', fontWeight: 600,
                color: 'var(--text-primary)',
                overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                marginBottom: 3,
              }}>
                📄 {datasetMeta.filename}
              </div>
              <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
                {datasetMeta.shape.rows.toLocaleString()} rows · {datasetMeta.shape.cols} cols · {datasetMeta.memoryMb} MB
              </div>
            </div>
          )}

          {/* Upload new dataset button */}
          {!collapsed && (
            <div style={{ padding: '8px 12px 4px', flexShrink: 0 }}>
              <button
                onClick={onClearSession}
                style={{
                  width: '100%', padding: '8px 12px',
                  borderRadius: 'var(--radius-md)',
                  background: datasetMeta ? 'transparent' : 'rgba(228, 43, 12, 0.08)',
                  border: `1px solid ${datasetMeta ? 'var(--color-cloud)' : 'rgba(228, 43, 12, 0.2)'}`,
                  color: datasetMeta ? 'var(--text-secondary)' : 'var(--color-vermillion-signal)',
                  fontSize: '0.78rem', fontWeight: 600,
                  display: 'flex', alignItems: 'center', gap: 7,
                  cursor: 'pointer', fontFamily: 'inherit',
                  transition: 'all 0.2s ease',
                }}
                onMouseEnter={e => {
                  e.currentTarget.style.background = 'rgba(228, 43, 12, 0.1)'
                  e.currentTarget.style.borderColor = 'rgba(228, 43, 12, 0.25)'
                  e.currentTarget.style.color = 'var(--color-vermillion-signal)'
                }}
                onMouseLeave={e => {
                  e.currentTarget.style.background = datasetMeta ? 'transparent' : 'rgba(228, 43, 12, 0.08)'
                  e.currentTarget.style.borderColor = datasetMeta ? 'var(--color-cloud)' : 'rgba(228, 43, 12, 0.2)'
                  e.currentTarget.style.color = datasetMeta ? 'var(--text-secondary)' : 'var(--color-vermillion-signal)'
                }}
              >
                {datasetMeta ? <><Upload size={13} /> Load New Dataset</> : <><Plus size={13} /> Upload Dataset</>}
              </button>
            </div>
          )}

          {/* Nav */}
          <nav
            className="sidebar-scroll"
            style={{
              flex: 1,
              overflowY: 'auto',
              overflowX: 'hidden',
              padding: collapsed ? '8px 6px' : '8px 10px',
              display: 'flex',
              flexDirection: 'column',
              gap: 0,
            }}
          >
            {visibleNavGroups.map((group, gi) => (
              <div key={gi} style={{ marginBottom: 4 }}>
                {!collapsed && (
                  <div style={{
                    padding: '10px 8px 4px',
                    fontSize: '0.62rem', fontWeight: 700,
                    color: 'var(--text-secondary)',
                    letterSpacing: '0.08em', textTransform: 'uppercase',
                  }}>
                    {group.label}
                  </div>
                )}
                {collapsed && gi > 0 && (
                  <div style={{
                    height: 1, background: 'var(--border-subtle)',
                    margin: '6px 4px',
                  }} />
                )}
                <div style={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                  {group.items.map(item => (
                    <NavItem
                      key={item.id}
                      item={item}
                      isActive={activePage === item.id}
                      onClick={onPageChange}
                      collapsed={collapsed}
                    />
                  ))}
                </div>
              </div>
            ))}
          </nav>

          {/* Footer */}
          <div style={{
            padding: collapsed ? '12px 6px' : '12px',
            borderTop: '1px solid var(--border-subtle)',
            flexShrink: 0,
            display: 'flex',
            flexDirection: 'column',
            gap: 6,
          }}>
            {/* Settings button */}
            <button
              onClick={() => setIsConfigOpen(true)}
              style={{
                display: 'flex', alignItems: 'center',
                gap: collapsed ? 0 : 9,
                padding: collapsed ? '9px' : '9px 10px',
                borderRadius: 'var(--radius-md)',
                background: 'var(--bg-primary)',
                border: '1px solid var(--color-cloud)',
                color: 'var(--text-secondary)',
                fontSize: '0.82rem', fontWeight: 500,
                cursor: 'pointer', fontFamily: 'inherit',
                width: '100%',
                justifyContent: collapsed ? 'center' : 'flex-start',
                transition: 'all 0.18s ease',
              }}
              onMouseEnter={e => { e.currentTarget.style.background = 'var(--bg-glass-hover)'; e.currentTarget.style.color = 'var(--text-primary)' }}
              onMouseLeave={e => { e.currentTarget.style.background = 'var(--bg-primary)'; e.currentTarget.style.color = 'var(--text-secondary)' }}
              title={collapsed ? 'AI Settings' : undefined}
            >
              <Sliders size={15} style={{ flexShrink: 0, opacity: 0.8 }} />
              {!collapsed && <span>AI Settings</span>}
              {!collapsed && (
                <span style={{
                  marginLeft: 'auto',
                  fontSize: '0.6rem', fontWeight: 700, padding: '2px 7px',
                  borderRadius: 'var(--radius-sm)', background: 'rgba(228, 43, 12, 0.1)',
                  border: '1px solid rgba(228, 43, 12, 0.25)',
                  color: 'var(--color-vermillion-signal)',
                }}>
                  <Zap size={9} style={{ display: 'inline', verticalAlign: 'middle', marginRight: 2 }} />
                  LLM
                </span>
              )}
            </button>

            {/* User row */}
            <div style={{
              display: 'flex', alignItems: 'center',
              gap: collapsed ? 0 : 9,
              padding: collapsed ? '6px' : '8px 6px',
              borderRadius: 'var(--radius-md)',
              justifyContent: collapsed ? 'center' : 'flex-start',
            }}>
              <UserAvatar user={user} size={32} />
              {!collapsed && (
                <>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{
                      fontSize: '0.8rem', fontWeight: 600,
                      color: 'var(--text-primary)',
                      overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                    }}>
                      {user?.displayName || 'User'}
                    </div>
                    <div style={{
                      fontSize: '0.68rem', color: 'var(--text-muted)',
                      overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                    }}>
                      {user?.email}
                    </div>
                  </div>
                  <button
                    onClick={logOut}
                    title="Log Out"
                    style={{
                      width: 28, height: 28, borderRadius: 'var(--radius-md)',
                      background: 'transparent',
                      border: '1px solid var(--color-cloud)',
                      color: 'var(--text-secondary)',
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      cursor: 'pointer', flexShrink: 0, transition: 'all 0.2s ease',
                    }}
                    onMouseEnter={e => { e.currentTarget.style.background = 'rgba(228, 43, 12, 0.08)'; e.currentTarget.style.borderColor = 'rgba(228, 43, 12, 0.2)'; e.currentTarget.style.color = 'var(--color-vermillion-signal)' }}
                    onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.borderColor = 'var(--color-cloud)'; e.currentTarget.style.color = 'var(--text-secondary)' }}
                  >
                    <LogOut size={13} />
                  </button>
                </>
              )}
            </div>
          </div>
        </aside>

        {/* ── Mobile sidebar (slide-in) ──────────────────────────── */}
        <aside
          style={{
            position: 'fixed', top: 0, left: 0, bottom: 0,
            width: 260, zIndex: 200,
            background: 'var(--bg-surface)',
            borderRight: '1px solid var(--border-subtle)',
            display: 'flex', flexDirection: 'column',
            transform: sidebarOpen ? 'translateX(0)' : 'translateX(-100%)',
            transition: 'transform 0.3s cubic-bezier(0.4,0,0.2,1)',
            overflowY: 'auto',
          }}
        >
          {/* Mobile sidebar header */}
          <div style={{
            padding: '16px',
            display: 'flex', alignItems: 'center', gap: 10,
            borderBottom: '1px solid var(--border-subtle)',
          }}>
            <div style={{
              width: 34, height: 34, borderRadius: 'var(--radius-md)',
              background: 'var(--color-vermillion-signal)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 17,
            }}>🧠</div>
            <span style={{
              fontWeight: 600, fontSize: '1.05rem',
              color: 'var(--color-slate-900)',
            }}>MLPrep AI<span style={{ color: 'var(--color-vermillion-signal)' }}>*</span></span>
            <button
              onClick={() => setSidebarOpen(false)}
              style={{
                marginLeft: 'auto', width: 28, height: 28, borderRadius: 'var(--radius-md)',
                background: 'var(--bg-glass-hover)',
                border: '1px solid var(--border-subtle)',
                color: 'var(--text-secondary)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                cursor: 'pointer',
              }}
            >
              <X size={14} />
            </button>
          </div>

          {/* Mobile nav */}
          <nav style={{ flex: 1, padding: '8px 10px', display: 'flex', flexDirection: 'column', gap: 0 }}>
            {visibleNavGroups.map((group, gi) => (
              <div key={gi} style={{ marginBottom: 4 }}>
                <div style={{
                  padding: '8px 8px 4px',
                  fontSize: '0.62rem', fontWeight: 700,
                  color: 'var(--text-secondary)',
                  letterSpacing: '0.08em', textTransform: 'uppercase',
                }}>
                  {group.label}
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                  {group.items.map(item => (
                    <NavItem
                      key={item.id}
                      item={item}
                      isActive={activePage === item.id}
                      onClick={(id) => { onPageChange(id); setSidebarOpen(false) }}
                      collapsed={false}
                    />
                  ))}
                </div>
              </div>
            ))}
          </nav>

          {/* Mobile footer */}
          <div style={{ padding: '12px', borderTop: '1px solid var(--border-subtle)' }}>
            <button onClick={() => setIsConfigOpen(true)} style={{
              display: 'flex', alignItems: 'center', gap: 9,
              padding: '9px 10px', borderRadius: 'var(--radius-md)', width: '100%',
              background: 'var(--bg-primary)', border: '1px solid var(--color-cloud)',
              color: 'var(--text-secondary)', fontSize: '0.82rem', fontWeight: 500,
              cursor: 'pointer', fontFamily: 'inherit', marginBottom: 8,
            }}>
              <Sliders size={15} /> AI Settings
            </button>
            <div style={{ display: 'flex', alignItems: 'center', gap: 9, padding: '4px 6px' }}>
              <UserAvatar user={user} size={30} />
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: '0.78rem', fontWeight: 600, color: 'var(--text-primary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{user?.displayName || 'User'}</div>
                <div style={{ fontSize: '0.67rem', color: 'var(--text-muted)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{user?.email}</div>
              </div>
              <button onClick={logOut} style={{ width: 26, height: 26, borderRadius: 'var(--radius-md)', background: 'rgba(228, 43, 12, 0.08)', border: '1px solid rgba(228, 43, 12, 0.2)', color: 'var(--color-vermillion-signal)', display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer' }}>
                <LogOut size={12} />
              </button>
            </div>
          </div>
        </aside>

        {/* ── Mobile top bar ──────────────────────────────────────── */}
        <div
          className="mobile-topbar"
          style={{
            display: 'none',
            position: 'fixed', top: 0, left: 0, right: 0, zIndex: 50,
            height: 56,
            background: 'var(--bg-surface)',
            borderBottom: '1px solid var(--border-subtle)',
            padding: '0 16px',
            alignItems: 'center', gap: 12,
          }}
        >
          <button
            onClick={() => setSidebarOpen(true)}
            style={{ color: 'var(--text-primary)', padding: 6, borderRadius: 'var(--radius-md)', background: 'var(--bg-glass-hover)', border: '1px solid var(--border-subtle)', cursor: 'pointer' }}
          >
            <Menu size={19} />
          </button>
          <span style={{ fontWeight: 600, fontSize: '0.95rem', color: 'var(--text-primary)' }}>
            {activeLabel}
          </span>
          {datasetMeta && (
            <span style={{
              marginLeft: 'auto', padding: '3px 10px', borderRadius: 'var(--radius-md)',
              background: 'var(--color-vellum)', border: '1px solid var(--color-cloud)',
              fontSize: '0.68rem', color: 'var(--color-slate-700)', fontWeight: 600,
              overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
              maxWidth: '40vw',
            }}>
              {datasetMeta.filename}
            </span>
          )}
        </div>

        {/* ── Main content area ───────────────────────────────────── */}
        <div
          className="main-content-area"
          style={{
            flex: 1,
            marginLeft: sidebarWidth,
            paddingTop: isMobile ? 56 : 0,
            minHeight: '100vh',
            display: 'flex',
            flexDirection: 'column',
            transition: 'margin-left 0.25s cubic-bezier(0.4,0,0.2,1)',
          }}
        >
          {/* Warning banner */}
          {datasetMeta?.warning && (
            <div style={{
              display: 'flex', alignItems: 'center', gap: 10,
              padding: '10px 24px',
              background: 'rgba(228, 43, 12, 0.05)',
              borderBottom: '1px solid rgba(228, 43, 12, 0.15)',
              fontSize: '0.8rem', color: 'var(--color-vermillion-signal)',
            }}>
              <AlertTriangle size={14} style={{ flexShrink: 0 }} />
              <span>{datasetMeta.warning}</span>
            </div>
          )}

          {/* Page content */}
          <div
            key={activePage}
            className="main-page-content"
            style={{
              flex: 1,
              padding: '24px',
              maxWidth: '100%',
              overflowX: 'hidden',
            }}
          >
            {children}
          </div>
        </div>

        {/* ── Mobile bottom nav ─────────────────────────────────── */}
        <div
          className="mobile-bottom-nav"
          style={{
            display: 'none',
            position: 'fixed', bottom: 0, left: 0, right: 0, zIndex: 50,
            height: 64,
            background: 'var(--bg-surface)',
            borderTop: '1px solid var(--border-subtle)',
            justifyContent: 'space-around', alignItems: 'center',
            paddingBottom: 'env(safe-area-inset-bottom, 0)',
          }}
        >
          {/* Show only top 5 nav items on mobile */}
          {visibleAllNav.slice(0, 5).map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => onPageChange(id)}
              style={{
                display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 3,
                padding: '6px 10px', borderRadius: 'var(--radius-md)',
                color: activePage === id ? 'var(--color-vermillion-signal)' : 'var(--text-secondary)',
                fontSize: '0.6rem', fontWeight: 600,
                cursor: 'pointer', background: 'none', border: 'none', fontFamily: 'inherit',
                transition: 'all 0.18s ease',
              }}
            >
              <Icon size={20} style={{ color: activePage === id ? 'var(--color-vermillion-signal)' : 'inherit', opacity: activePage === id ? 1 : 0.6 }} />
              <span>{label}</span>
            </button>
          ))}
          <button
            onClick={() => setSidebarOpen(true)}
            style={{
              display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 3,
              padding: '6px 10px', borderRadius: 'var(--radius-md)',
              color: 'var(--text-secondary)',
              fontSize: '0.6rem', fontWeight: 600,
              cursor: 'pointer', background: 'none', border: 'none', fontFamily: 'inherit',
            }}
          >
            <Menu size={20} style={{ opacity: 0.6 }} />
            <span>More</span>
          </button>
        </div>
      </div>

      {/* LLM Config Modal */}
      <LLMConfigModal isOpen={isConfigOpen} onClose={() => setIsConfigOpen(false)} />
    </>
  )
}
