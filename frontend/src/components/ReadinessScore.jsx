import React from 'react'

const GRADE_COLORS = {
  A: 'text-emerald-500 border-emerald-500/25 bg-emerald-500/5',
  B: 'text-teal-500 border-teal-500/25 bg-teal-500/5',
  C: 'text-yellow-500 border-yellow-500/25 bg-yellow-500/5',
  D: 'text-orange-500 border-orange-500/25 bg-orange-500/5',
  F: 'text-red-500 border-red-500/25 bg-red-500/5',
}

export default function ReadinessScore({ score, grade }) {
  const gradeColor = GRADE_COLORS[grade] || GRADE_COLORS.F

  return (
    <div className="p-8 rounded-2xl border border-[rgba(255,255,255,0.06)] bg-[rgba(255,255,255,0.04)] flex flex-col items-center justify-center text-center shadow-xl relative overflow-hidden">
      <div className="absolute inset-0 bg-gradient-to-br from-purple-500/5 to-pink-500/5 pointer-events-none" />
      
      <p className="text-xs uppercase tracking-widest text-[#8E9AAF] font-semibold mb-6">ML Readiness Score</p>
      
      {/* Circular Progress Gauge */}
      <div className="relative w-40 h-40 flex items-center justify-center mb-6">
        <svg className="w-full h-full transform -rotate-90">
          {/* Background track */}
          <circle
            cx="80"
            cy="80"
            r="70"
            className="stroke-[rgba(255,255,255,0.03)] fill-none stroke-[8px]"
          />
          {/* Progress fill */}
          <circle
            cx="80"
            cy="80"
            r="70"
            className="fill-none stroke-[8px] transition-all duration-1000 ease-out"
            style={{
              stroke: 'url(#gradient)',
              strokeDasharray: 440,
              strokeDashoffset: 440 - (440 * score) / 100,
              strokeLinecap: 'round',
            }}
          />
          <defs>
            <linearGradient id="gradient" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#000000" />
              <stop offset="100%" stopColor="#000000" />
            </linearGradient>
          </defs>
        </svg>
        <div className="absolute flex flex-col items-center justify-center">
          <span className="text-5xl font-extrabold text-[#F0F0F8] tracking-tight">{score}</span>
          <span className="text-xs text-[#8E9AAF] mt-1">out of 100</span>
        </div>
      </div>

      {/* Grade Badge */}
      <div className={`px-4 py-1.5 rounded-full border text-sm font-extrabold tracking-wide uppercase ${gradeColor}`}>
        Grade {grade}
      </div>
    </div>
  )
}
