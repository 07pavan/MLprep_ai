import React from 'react'

export default function InsightCard({ insights }) {
  if (!insights) return null

  const lines = insights
    .split('\n')
    .map((l) => l.trim())
    .filter(Boolean)

  return (
    <div className="insight-card">
      {lines.map((line, i) => {
        // Highlight ✦ bullet lines from the new structured insights format
        const isBullet = line.startsWith('✦')
        return (
          <p
            key={i}
            style={
              isBullet
                ? { color: 'var(--text-primary)', fontWeight: 500, marginBottom: 6 }
                : { color: 'var(--text-secondary)', fontSize: '0.82rem' }
            }
          >
            {line}
          </p>
        )
      })}
    </div>
  )
}
