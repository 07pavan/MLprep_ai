import React, { useState, useCallback, useRef } from 'react'
import {
  BookOpen, Play, Loader, AlertCircle, RefreshCw, Download,
  FileText, FileJson, ChevronDown, ChevronRight, CheckCircle,
  TrendingUp, BarChart2, ShieldCheck, Brain, Target,
  Clock, Star, Layers, Zap, Users, Eye, History,
} from 'lucide-react'
import { generateStoryReport, downloadStoryPdf, downloadStoryJson } from '../api/client'

// ── Constants ──────────────────────────────────────────────────────────────
const REPORT_TYPES = [
  {
    id: 'executive',
    label: 'Executive Report',
    desc: 'High-level business summary for decision makers.',
    icon: Target,
    color: '#6366f1',
    gradient: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
  },
  {
    id: 'business',
    label: 'Business Report',
    desc: 'Trend analysis, KPIs, and business recommendations.',
    icon: TrendingUp,
    color: '#10b981',
    gradient: 'linear-gradient(135deg, #10b981, #059669)',
  },
  {
    id: 'technical',
    label: 'Technical Report',
    desc: 'In-depth statistical analysis and data diagnostics.',
    icon: BarChart2,
    color: '#3b82f6',
    gradient: 'linear-gradient(135deg, #3b82f6, #06b6d4)',
  },
  {
    id: 'ML readiness',
    label: 'ML Readiness Report',
    desc: 'Feature suitability, encoding needs, and model readiness.',
    icon: Brain,
    color: '#f59e0b',
    gradient: 'linear-gradient(135deg, #f59e0b, #ef4444)',
  },
]

const PERSONAS = [
  { id: 'general', label: 'General' },
  { id: 'business', label: 'Business Analyst' },
  { id: 'technical', label: 'Data Engineer' },
  { id: 'executive', label: 'Executive' },
]

const SECTION_ICONS = {
  key_findings: TrendingUp,
  visualization_summary: Eye,
  data_quality: ShieldCheck,
  ml_readiness: Brain,
}

// ── Confidence Badge ───────────────────────────────────────────────────────
function ConfidenceBadge({ score }) {
  const pct = Math.round((score || 0) * 100)
  const color = pct >= 85 ? '#10b981' : pct >= 60 ? '#f59e0b' : '#ef4444'
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
      <div style={{
        width: 48, height: 48, borderRadius: '50%',
        background: `conic-gradient(${color} ${pct * 3.6}deg, rgba(255,255,255,0.08) 0deg)`,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        position: 'relative',
      }}>
        <div style={{
          position: 'absolute', inset: 4, borderRadius: '50%',
          background: 'var(--bg-secondary)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: '0.65rem', fontWeight: 700, color,
        }}>
          {pct}%
        </div>
      </div>
      <div>
        <div style={{ fontSize: '0.7rem', color: 'var(--text-secondary)' }}>Confidence</div>
        <div style={{ fontSize: '0.8rem', fontWeight: 600, color }}>
          {pct >= 85 ? 'High' : pct >= 60 ? 'Medium' : 'Low'}
        </div>
      </div>
    </div>
  )
}

// ── Section Card ───────────────────────────────────────────────────────────
function SectionCard({ section, index }) {
  const [expanded, setExpanded] = useState(index < 2)
  const Icon = SECTION_ICONS[section.section_id] || Layers
  const metaKeys = section.metadata ? Object.keys(section.metadata) : []

  return (
    <div style={{
      background: 'var(--bg-secondary)',
      border: '1px solid var(--border-subtle)',
      borderRadius: 12,
      overflow: 'hidden',
      transition: 'border-color 0.2s',
    }}
      onMouseEnter={e => e.currentTarget.style.borderColor = 'rgba(99,102,241,0.4)'}
      onMouseLeave={e => e.currentTarget.style.borderColor = 'var(--border-subtle)'}
    >
      {/* Header */}
      <button
        onClick={() => setExpanded(v => !v)}
        style={{
          width: '100%', display: 'flex', alignItems: 'center', gap: 12,
          padding: '16px 20px', background: 'none', border: 'none',
          cursor: 'pointer', textAlign: 'left',
        }}
      >
        <div style={{
          width: 36, height: 36, borderRadius: 8,
          background: 'linear-gradient(135deg, rgba(99,102,241,0.2), rgba(139,92,246,0.2))',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          flexShrink: 0,
        }}>
          <Icon size={18} color="#6366f1" />
        </div>
        <div style={{ flex: 1 }}>
          <div style={{ fontWeight: 600, fontSize: '0.9rem', color: 'var(--text-primary)' }}>
            {section.title}
          </div>
          {!expanded && section.content && (
            <div style={{
              fontSize: '0.75rem', color: 'var(--text-secondary)',
              whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
              maxWidth: 480, marginTop: 2,
            }}>
              {section.content.slice(0, 100)}…
            </div>
          )}
        </div>
        {expanded
          ? <ChevronDown size={16} color="var(--text-secondary)" />
          : <ChevronRight size={16} color="var(--text-secondary)" />}
      </button>

      {expanded && (
        <div style={{ padding: '0 20px 20px' }}>
          <div style={{
            fontSize: '0.85rem', color: 'var(--text-secondary)', lineHeight: 1.7,
            whiteSpace: 'pre-line',
          }}>
            {section.content}
          </div>

          {metaKeys.length > 0 && (
            <div style={{ marginTop: 14, display: 'flex', flexWrap: 'wrap', gap: 8 }}>
              {metaKeys.slice(0, 8).map(k => (
                <div key={k} style={{
                  background: 'rgba(99,102,241,0.1)',
                  border: '1px solid rgba(99,102,241,0.2)',
                  borderRadius: 6, padding: '3px 10px',
                  fontSize: '0.72rem', color: '#a5b4fc',
                }}>
                  <span style={{ opacity: 0.7 }}>{k}: </span>
                  <span style={{ fontWeight: 600 }}>
                    {typeof section.metadata[k] === 'object'
                      ? JSON.stringify(section.metadata[k])
                      : String(section.metadata[k])}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ── Recommendation Card ────────────────────────────────────────────────────
const REC_COLORS = {
  business: { bg: 'rgba(16,185,129,0.1)', border: 'rgba(16,185,129,0.25)', text: '#34d399', label: 'Business' },
  analytical: { bg: 'rgba(59,130,246,0.1)', border: 'rgba(59,130,246,0.25)', text: '#60a5fa', label: 'Analytical' },
  ml: { bg: 'rgba(245,158,11,0.1)', border: 'rgba(245,158,11,0.25)', text: '#fbbf24', label: 'ML / AI' },
}

function RecommendationCard({ rec }) {
  const [expanded, setExpanded] = useState(false)
  const style = REC_COLORS[rec.rec_type] || REC_COLORS.analytical

  return (
    <div style={{
      background: style.bg, border: `1px solid ${style.border}`,
      borderRadius: 10, padding: '14px 16px', cursor: 'pointer',
      transition: 'opacity 0.2s',
    }} onClick={() => setExpanded(v => !v)}>
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10 }}>
        <Zap size={16} color={style.text} style={{ flexShrink: 0, marginTop: 2 }} />
        <div style={{ flex: 1 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
            <span style={{
              fontSize: '0.65rem', fontWeight: 700, textTransform: 'uppercase',
              letterSpacing: '0.05em', color: style.text,
              background: `${style.border}`, borderRadius: 4, padding: '1px 6px',
            }}>{style.label}</span>
          </div>
          <div style={{ fontWeight: 600, fontSize: '0.85rem', color: 'var(--text-primary)' }}>
            {rec.title}
          </div>
          <div style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', marginTop: 4 }}>
            {rec.description}
          </div>
          {expanded && (
            <>
              {rec.expected_impact && (
                <div style={{ marginTop: 10, fontSize: '0.78rem' }}>
                  <span style={{ color: style.text, fontWeight: 600 }}>Expected Impact: </span>
                  <span style={{ color: 'var(--text-secondary)' }}>{rec.expected_impact}</span>
                </div>
              )}
              {rec.action_steps?.length > 0 && (
                <ul style={{
                  marginTop: 8, paddingLeft: 16,
                  fontSize: '0.75rem', color: 'var(--text-secondary)', lineHeight: 1.7,
                }}>
                  {rec.action_steps.map((step, i) => (
                    <li key={i}>{step}</li>
                  ))}
                </ul>
              )}
            </>
          )}
        </div>
        {expanded
          ? <ChevronDown size={14} color="var(--text-secondary)" style={{ flexShrink: 0 }} />
          : <ChevronRight size={14} color="var(--text-secondary)" style={{ flexShrink: 0 }} />}
      </div>
    </div>
  )
}

// ── Report View ────────────────────────────────────────────────────────────
function ReportView({ report, reportType, onDownloadPdf, onDownloadJson, isExporting }) {
  const { executive_summary, sections = [], recommendations = [], sources = [], generated_timestamp } = report
  const typeConfig = REPORT_TYPES.find(r => r.id === reportType) || REPORT_TYPES[0]

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      {/* Report Header */}
      <div style={{
        background: `linear-gradient(135deg, rgba(99,102,241,0.12), rgba(139,92,246,0.08))`,
        border: '1px solid rgba(99,102,241,0.2)',
        borderRadius: 16, padding: '28px 28px 24px',
        position: 'relative', overflow: 'hidden',
      }}>
        {/* Decorative blur */}
        <div style={{
          position: 'absolute', top: -30, right: -30, width: 160, height: 160,
          background: 'radial-gradient(circle, rgba(139,92,246,0.15), transparent)',
          borderRadius: '50%', pointerEvents: 'none',
        }} />

        <div style={{ display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: 16, position: 'relative' }}>
          <div style={{ flex: 1, minWidth: 240 }}>
            {/* Type badge */}
            <div style={{
              display: 'inline-flex', alignItems: 'center', gap: 6,
              background: `${typeConfig.gradient}`, borderRadius: 20,
              padding: '3px 12px', marginBottom: 12,
              fontSize: '0.72rem', fontWeight: 700, color: '#fff',
              textTransform: 'uppercase', letterSpacing: '0.06em',
            }}>
              <typeConfig.icon size={12} />
              {typeConfig.label}
            </div>
            <h2 style={{
              fontSize: '1.3rem', fontWeight: 700, color: 'var(--text-primary)',
              lineHeight: 1.3, marginBottom: 14,
            }}>
              {report.title}
            </h2>
            <div style={{ display: 'flex', gap: 20, flexWrap: 'wrap' }}>
              <ConfidenceBadge score={report.confidence_score} />
              {generated_timestamp && (
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <Clock size={14} color="var(--text-secondary)" />
                  <div>
                    <div style={{ fontSize: '0.7rem', color: 'var(--text-secondary)' }}>Generated</div>
                    <div style={{ fontSize: '0.78rem', fontWeight: 600, color: 'var(--text-primary)' }}>
                      {new Date(generated_timestamp).toLocaleString()}
                    </div>
                  </div>
                </div>
              )}
              {sources.length > 0 && (
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <Layers size={14} color="var(--text-secondary)" />
                  <div>
                    <div style={{ fontSize: '0.7rem', color: 'var(--text-secondary)' }}>Sources</div>
                    <div style={{ fontSize: '0.78rem', fontWeight: 600, color: 'var(--text-primary)' }}>
                      {sources.join(', ')}
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Export buttons */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8, alignSelf: 'flex-start' }}>
            <button
              className="btn-primary"
              style={{ fontSize: '0.78rem', padding: '8px 16px', gap: 6, display: 'flex', alignItems: 'center' }}
              onClick={onDownloadPdf}
              disabled={isExporting}
            >
              {isExporting ? <Loader size={14} className="spin" /> : <FileText size={14} />}
              Export HTML/PDF
            </button>
            <button
              className="btn-ghost"
              style={{ fontSize: '0.78rem', padding: '8px 16px', gap: 6, display: 'flex', alignItems: 'center' }}
              onClick={onDownloadJson}
              disabled={isExporting}
            >
              <FileJson size={14} />
              Export JSON
            </button>
          </div>
        </div>
      </div>

      {/* Executive Summary */}
      {executive_summary && (
        <div style={{
          background: 'var(--bg-secondary)',
          border: '1px solid var(--border-subtle)',
          borderRadius: 14, padding: 24,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
            <div style={{
              width: 32, height: 32, borderRadius: 8,
              background: 'linear-gradient(135deg, rgba(99,102,241,0.25), rgba(139,92,246,0.25))',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}>
              <Star size={16} color="#a5b4fc" />
            </div>
            <h3 style={{ fontWeight: 700, fontSize: '0.95rem', color: 'var(--text-primary)' }}>
              Executive Summary
            </h3>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 12, marginBottom: 16 }}>
            {/* Quality Score */}
            <div style={{
              background: 'rgba(99,102,241,0.08)', border: '1px solid rgba(99,102,241,0.15)',
              borderRadius: 10, padding: 16, textAlign: 'center',
            }}>
              <div style={{ fontSize: '2rem', fontWeight: 800, background: 'linear-gradient(135deg, #6366f1, #8b5cf6)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
                {Math.round(executive_summary.data_quality_score || 0)}
              </div>
              <div style={{ fontSize: '0.72rem', color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                Quality Score / 100
              </div>
            </div>

            {/* Sections count */}
            <div style={{
              background: 'rgba(16,185,129,0.08)', border: '1px solid rgba(16,185,129,0.15)',
              borderRadius: 10, padding: 16, textAlign: 'center',
            }}>
              <div style={{ fontSize: '2rem', fontWeight: 800, color: '#34d399' }}>
                {sections.length}
              </div>
              <div style={{ fontSize: '0.72rem', color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                Report Sections
              </div>
            </div>

            {/* Recommendations */}
            <div style={{
              background: 'rgba(245,158,11,0.08)', border: '1px solid rgba(245,158,11,0.15)',
              borderRadius: 10, padding: 16, textAlign: 'center',
            }}>
              <div style={{ fontSize: '2rem', fontWeight: 800, color: '#fbbf24' }}>
                {recommendations.length}
              </div>
              <div style={{ fontSize: '0.72rem', color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                Recommendations
              </div>
            </div>
          </div>

          {/* Overview paragraph */}
          <div style={{
            background: 'rgba(255,255,255,0.03)', borderRadius: 8, padding: 14,
            fontSize: '0.85rem', color: 'var(--text-secondary)', lineHeight: 1.7,
            borderLeft: '3px solid #6366f1', marginBottom: 12,
          }}>
            {executive_summary.dataset_overview}
          </div>

          {/* Business summary */}
          {executive_summary.overall_business_summary && (
            <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', lineHeight: 1.7 }}>
              {executive_summary.overall_business_summary}
            </div>
          )}
        </div>
      )}

      {/* Story Sections */}
      {sections.length > 0 && (
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14 }}>
            <Layers size={16} color="#6366f1" />
            <h3 style={{ fontWeight: 700, fontSize: '0.95rem', color: 'var(--text-primary)' }}>
              Report Sections
            </h3>
            <span style={{
              background: 'rgba(99,102,241,0.15)', color: '#a5b4fc',
              borderRadius: 20, padding: '1px 10px', fontSize: '0.72rem', fontWeight: 600,
            }}>{sections.length}</span>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {sections.map((sec, i) => (
              <SectionCard key={sec.section_id || i} section={sec} index={i} />
            ))}
          </div>
        </div>
      )}

      {/* Recommendations */}
      {recommendations.length > 0 && (
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14 }}>
            <Zap size={16} color="#f59e0b" />
            <h3 style={{ fontWeight: 700, fontSize: '0.95rem', color: 'var(--text-primary)' }}>
              Recommendations
            </h3>
            <span style={{
              background: 'rgba(245,158,11,0.15)', color: '#fbbf24',
              borderRadius: 20, padding: '1px 10px', fontSize: '0.72rem', fontWeight: 600,
            }}>{recommendations.length}</span>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {recommendations.map((rec, i) => (
              <RecommendationCard key={i} rec={rec} />
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

// ── History Sidebar ────────────────────────────────────────────────────────
function HistoryItem({ entry, isActive, onClick }) {
  const typeConfig = REPORT_TYPES.find(r => r.id === entry.reportType) || REPORT_TYPES[0]
  return (
    <button
      onClick={onClick}
      style={{
        width: '100%', textAlign: 'left', padding: '10px 14px',
        borderRadius: 10, border: `1px solid ${isActive ? 'rgba(99,102,241,0.4)' : 'transparent'}`,
        background: isActive ? 'rgba(99,102,241,0.08)' : 'transparent',
        cursor: 'pointer', transition: 'all 0.15s',
        display: 'flex', alignItems: 'flex-start', gap: 10,
      }}
      onMouseEnter={e => { if (!isActive) e.currentTarget.style.background = 'rgba(255,255,255,0.04)' }}
      onMouseLeave={e => { if (!isActive) e.currentTarget.style.background = 'transparent' }}
    >
      <div style={{
        width: 30, height: 30, borderRadius: 6, flexShrink: 0,
        background: typeConfig.gradient,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}>
        <typeConfig.icon size={14} color="#fff" />
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{
          fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-primary)',
          overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
        }}>
          {entry.title || typeConfig.label}
        </div>
        <div style={{ fontSize: '0.7rem', color: 'var(--text-secondary)', marginTop: 2 }}>
          {new Date(entry.timestamp).toLocaleTimeString()}
        </div>
      </div>
      {isActive && <CheckCircle size={14} color="#6366f1" style={{ flexShrink: 0, marginTop: 6 }} />}
    </button>
  )
}

// ── Empty State ────────────────────────────────────────────────────────────
function EmptyState({ onGenerate }) {
  return (
    <div style={{
      display: 'flex', flexDirection: 'column', alignItems: 'center',
      justifyContent: 'center', padding: '80px 24px', textAlign: 'center',
    }}>
      <div style={{
        width: 80, height: 80, borderRadius: 20, marginBottom: 24,
        background: 'linear-gradient(135deg, rgba(99,102,241,0.2), rgba(139,92,246,0.15))',
        border: '1px solid rgba(99,102,241,0.2)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}>
        <BookOpen size={36} color="#6366f1" />
      </div>
      <h3 style={{ fontSize: '1.2rem', fontWeight: 700, color: 'var(--text-primary)', marginBottom: 10 }}>
        No Report Generated Yet
      </h3>
      <p style={{ color: 'var(--text-secondary)', fontSize: '0.88rem', maxWidth: 380, lineHeight: 1.6, marginBottom: 28 }}>
        Select a report type and click <strong>Generate Report</strong> to create a structured AI analysis of your dataset.
      </p>
      <button className="btn-primary" onClick={onGenerate} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <Play size={16} />
        Generate My First Report
      </button>
    </div>
  )
}

// ── Main StoryPanel ────────────────────────────────────────────────────────
export default function StoryPanel({ sessionId }) {
  const [activeReportType, setActiveReportType] = useState('executive')
  const [activePersona, setActivePersona] = useState('general')
  const [isLoading, setIsLoading] = useState(false)
  const [isExporting, setIsExporting] = useState(false)
  const [error, setError] = useState(null)
  const [history, setHistory] = useState([])    // [{reportType, title, timestamp, report}]
  const [activeHistoryIdx, setActiveHistoryIdx] = useState(null)

  const activeReport = activeHistoryIdx !== null ? history[activeHistoryIdx]?.report : null
  const activeReportTypeSaved = activeHistoryIdx !== null ? history[activeHistoryIdx]?.reportType : activeReportType

  const handleGenerate = useCallback(async () => {
    setIsLoading(true)
    setError(null)

    try {
      const data = await generateStoryReport(sessionId, activeReportType, activePersona)

      if (!data?.success) {
        setError(data?.errors?.[0] || 'Report generation failed. Please try again.')
        return
      }

      const entry = {
        reportType: activeReportType,
        title: data.report?.title || REPORT_TYPES.find(r => r.id === activeReportType)?.label,
        timestamp: new Date().toISOString(),
        report: data.report,
        reportId: data.report?.report_id,
      }

      setHistory(prev => {
        const next = [entry, ...prev].slice(0, 10)  // keep last 10
        setActiveHistoryIdx(0)
        return next
      })
    } catch (err) {
      console.error(err)
      setError(err.response?.data?.detail || err.message || 'Network error. Please retry.')
    } finally {
      setIsLoading(false)
    }
  }, [sessionId, activeReportType, activePersona])

  const handleDownloadPdf = useCallback(async () => {
    if (!activeReport?.report_id) return
    setIsExporting(true)
    try {
      await downloadStoryPdf(activeReport.report_id, activeReport.title)
    } catch (err) {
      setError('Failed to export PDF. Please try again.')
    } finally {
      setIsExporting(false)
    }
  }, [activeReport])

  const handleDownloadJson = useCallback(async () => {
    if (!activeReport?.report_id) return
    setIsExporting(true)
    try {
      await downloadStoryJson(activeReport.report_id, activeReport.title)
    } catch (err) {
      setError('Failed to export JSON. Please try again.')
    } finally {
      setIsExporting(false)
    }
  }, [activeReport])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 0, minHeight: '100%' }}>
      {/* ── Panel Header ─────────────────────────────────────────── */}
      <div style={{ marginBottom: 28 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 6 }}>
          <div style={{
            width: 40, height: 40, borderRadius: 10,
            background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            boxShadow: '0 4px 12px rgba(99,102,241,0.4)',
          }}>
            <BookOpen size={20} color="#fff" />
          </div>
          <div>
            <h1 style={{ fontSize: '1.3rem', fontWeight: 800, margin: 0, color: 'var(--text-primary)' }}>
              AI Data Storytelling
            </h1>
            <p style={{ margin: 0, fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
              Generate structured business reports and executive narratives
            </p>
          </div>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) 220px', gap: 24, alignItems: 'start' }}>
        {/* ── LEFT COLUMN: Controls + Report ────────────────────── */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>

          {/* Report Type Selector */}
          <div>
            <div style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 10, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Report Type
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(170px, 1fr))', gap: 10 }}>
              {REPORT_TYPES.map(rt => {
                const isActive = activeReportType === rt.id
                return (
                  <button
                    key={rt.id}
                    onClick={() => setActiveReportType(rt.id)}
                    style={{
                      padding: '14px 16px', borderRadius: 12, textAlign: 'left',
                      border: `1px solid ${isActive ? rt.color : 'var(--border-subtle)'}`,
                      background: isActive
                        ? `linear-gradient(135deg, ${rt.color}18, ${rt.color}0a)`
                        : 'var(--bg-secondary)',
                      cursor: 'pointer', transition: 'all 0.15s',
                      boxShadow: isActive ? `0 0 0 2px ${rt.color}40` : 'none',
                    }}
                    onMouseEnter={e => { if (!isActive) e.currentTarget.style.borderColor = rt.color + '55' }}
                    onMouseLeave={e => { if (!isActive) e.currentTarget.style.borderColor = 'var(--border-subtle)' }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                      <rt.icon size={16} color={isActive ? rt.color : 'var(--text-secondary)'} />
                      <span style={{
                        fontSize: '0.82rem', fontWeight: 700,
                        color: isActive ? rt.color : 'var(--text-primary)',
                      }}>{rt.label}</span>
                    </div>
                    <div style={{ fontSize: '0.72rem', color: 'var(--text-secondary)', lineHeight: 1.4 }}>
                      {rt.desc}
                    </div>
                  </button>
                )
              })}
            </div>
          </div>

          {/* Persona + Generate Row */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <Users size={14} color="var(--text-secondary)" />
              <span style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>Persona:</span>
              <div style={{ display: 'flex', gap: 4 }}>
                {PERSONAS.map(p => (
                  <button
                    key={p.id}
                    onClick={() => setActivePersona(p.id)}
                    style={{
                      padding: '4px 12px', borderRadius: 20, fontSize: '0.75rem',
                      border: `1px solid ${activePersona === p.id ? '#6366f1' : 'var(--border-subtle)'}`,
                      background: activePersona === p.id ? 'rgba(99,102,241,0.15)' : 'transparent',
                      color: activePersona === p.id ? '#a5b4fc' : 'var(--text-secondary)',
                      cursor: 'pointer', fontWeight: activePersona === p.id ? 600 : 400,
                      transition: 'all 0.15s',
                    }}
                  >{p.label}</button>
                ))}
              </div>
            </div>

            <div style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>
              {activeReport && (
                <button
                  className="btn-ghost"
                  onClick={handleGenerate}
                  disabled={isLoading}
                  style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.82rem' }}
                >
                  <RefreshCw size={14} className={isLoading ? 'spin' : ''} />
                  Regenerate
                </button>
              )}
              <button
                className="btn-primary"
                onClick={handleGenerate}
                disabled={isLoading}
                style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 160 }}
              >
                {isLoading
                  ? <><Loader size={16} className="spin" /> Generating…</>
                  : <><Play size={16} /> Generate Report</>}
              </button>
            </div>
          </div>

          {/* Loading */}
          {isLoading && (
            <div style={{
              background: 'rgba(99,102,241,0.06)', border: '1px solid rgba(99,102,241,0.15)',
              borderRadius: 12, padding: '20px 24px',
              display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12,
            }}>
              <div className="spinner" style={{ width: 36, height: 36 }} />
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontWeight: 600, color: 'var(--text-primary)', marginBottom: 4 }}>
                  Generating AI Report…
                </div>
                <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                  Aggregating dataset metadata, insights, and visualizations. This may take 15–30 seconds.
                </div>
              </div>
              {/* Progress steps */}
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', justifyContent: 'center' }}>
                {['Profiling', 'Quality', 'Insights', 'Visualizations', 'LLM Narrative'].map(step => (
                  <div key={step} style={{
                    background: 'rgba(99,102,241,0.12)', border: '1px solid rgba(99,102,241,0.2)',
                    borderRadius: 20, padding: '3px 12px',
                    fontSize: '0.72rem', color: '#a5b4fc', display: 'flex', alignItems: 'center', gap: 5,
                  }}>
                    <div className="spinner" style={{ width: 10, height: 10, borderWidth: 1 }} />
                    {step}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Error */}
          {error && !isLoading && (
            <div style={{
              background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.25)',
              borderRadius: 12, padding: '14px 18px',
              display: 'flex', alignItems: 'flex-start', gap: 12,
            }}>
              <AlertCircle size={18} color="#f87171" style={{ flexShrink: 0, marginTop: 1 }} />
              <div style={{ flex: 1 }}>
                <div style={{ fontWeight: 600, color: '#f87171', marginBottom: 4 }}>Generation Failed</div>
                <div style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>{error}</div>
              </div>
              <button
                style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 4 }}
                onClick={() => setError(null)}
              >
                <RefreshCw size={14} color="#f87171" />
              </button>
            </div>
          )}

          {/* Report or Empty State */}
          {!isLoading && !activeReport && !error && (
            <EmptyState onGenerate={handleGenerate} />
          )}

          {!isLoading && activeReport && (
            <ReportView
              report={activeReport}
              reportType={activeReportTypeSaved}
              onDownloadPdf={handleDownloadPdf}
              onDownloadJson={handleDownloadJson}
              isExporting={isExporting}
            />
          )}
        </div>

        {/* ── RIGHT COLUMN: History Sidebar ────────────────────── */}
        <div style={{
          background: 'var(--bg-secondary)', border: '1px solid var(--border-subtle)',
          borderRadius: 14, padding: 16, position: 'sticky', top: 16,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14 }}>
            <History size={14} color="var(--text-secondary)" />
            <span style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-secondary)' }}>
              Report History
            </span>
            {history.length > 0 && (
              <span style={{
                marginLeft: 'auto',
                background: 'rgba(99,102,241,0.15)', color: '#a5b4fc',
                borderRadius: 20, padding: '0px 8px', fontSize: '0.68rem', fontWeight: 600,
              }}>{history.length}</span>
            )}
          </div>

          {history.length === 0 ? (
            <div style={{
              textAlign: 'center', padding: '24px 8px',
              color: 'var(--text-secondary)', fontSize: '0.78rem', lineHeight: 1.5,
            }}>
              <History size={24} color="var(--border-subtle)" style={{ marginBottom: 8 }} />
              <div>No reports yet.<br />Generate one to see history.</div>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              {history.map((entry, i) => (
                <HistoryItem
                  key={`${entry.reportId}-${i}`}
                  entry={entry}
                  isActive={activeHistoryIdx === i}
                  onClick={() => setActiveHistoryIdx(i)}
                />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
