import React from 'react'

export default function InsightCard({ insights }) {
  if (!insights) return null

  const lines = insights
    .split('\n')
    .map((l) => l.trim())
    .filter(Boolean)

  return (
    <div className="insight-card">
      {lines.map((line, i) => (
        <p key={i}>{line}</p>
      ))}
    </div>
  )
}
