import React from 'react'

const GRADE_COLORS = {
  A: { text: '#5d2a1a', border: 'rgba(93, 42, 26, 0.3)', bg: '#fbe1d1' },
  B: { text: '#5d2a1a', border: 'rgba(93, 42, 26, 0.3)', bg: '#fbe1d1' },
  C: { text: '#777b86', border: 'rgba(119, 123, 134, 0.3)', bg: '#f7f7f8' },
  D: { text: '#4c4c4c', border: 'rgba(76, 76, 76, 0.2)',   bg: '#f0f0f2' },
  F: { text: '#4c4c4c', border: 'rgba(76, 76, 76, 0.2)',   bg: '#f0f0f2' },
}

export default function ReadinessScore({ score, grade }) {
  const gradeColor = GRADE_COLORS[grade] || GRADE_COLORS.F

  return (
    <div
      style={{
        padding: 32,
        borderRadius: 'var(--radius-lg)',
        background: 'var(--color-apricot)',
        border: '1px solid var(--color-apricot-mid)',
        display: 'flex', flexDirection: 'column', alignItems: 'center',
        justifyContent: 'center', textAlign: 'center',
        position: 'relative', overflow: 'hidden',
        boxShadow: 'var(--shadow-card)',
      }}
    >
      <p style={{
        fontSize: '0.7rem', textTransform: 'uppercase', letterSpacing: '0.1em',
        color: 'var(--color-rust)', fontWeight: 700, marginBottom: 24,
      }}>
        ML Readiness Score
      </p>

      {/* Circular Progress Gauge */}
      <div style={{ position: 'relative', width: 160, height: 160, marginBottom: 24 }}>
        <svg style={{ width: '100%', height: '100%', transform: 'rotate(-90deg)' }}>
          {/* Background track */}
          <circle
            cx="80" cy="80" r="70"
            fill="none"
            stroke="rgba(93, 42, 26, 0.12)"
            strokeWidth="8"
          />
          {/* Progress fill */}
          <circle
            cx="80" cy="80" r="70"
            fill="none"
            stroke="var(--color-rust)"
            strokeWidth="8"
            strokeLinecap="round"
            style={{
              strokeDasharray: 440,
              strokeDashoffset: 440 - (440 * score) / 100,
              transition: 'stroke-dashoffset 1s ease-out',
            }}
          />
        </svg>
        <div style={{
          position: 'absolute', inset: 0,
          display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
        }}>
          <span style={{
            fontSize: '3rem', fontWeight: 700, color: 'var(--color-ink)',
            lineHeight: 1, letterSpacing: '-0.03em',
            fontVariantNumeric: 'tabular-nums',
            fontFamily: 'var(--font-serif)',
          }}>
            {score}
          </span>
          <span style={{ fontSize: '0.72rem', color: 'var(--color-rust)', marginTop: 4 }}>
            out of 100
          </span>
        </div>
      </div>

      {/* Grade Badge */}
      <div style={{
        padding: '6px 20px',
        borderRadius: 'var(--radius-full)',
        background: gradeColor.bg,
        border: `1px solid ${gradeColor.border}`,
        color: gradeColor.text,
        fontSize: '0.82rem', fontWeight: 700,
        letterSpacing: '0.06em', textTransform: 'uppercase',
      }}>
        Grade {grade}
      </div>
    </div>
  )
}
