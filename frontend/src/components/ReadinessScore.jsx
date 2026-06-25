import React from 'react'

const GRADE_COLORS = {
  A: 'text-[#cc9166] border-[#cc9166]/25 bg-[#cc9166]/5',
  B: 'text-[#cc9166] border-[#cc9166]/25 bg-[#cc9166]/5',
  C: 'text-[#9194a1] border-[#9194a1]/25 bg-[#9194a1]/5',
  D: 'text-[#777a88] border-[#777a88]/25 bg-[#777a88]/5',
  F: 'text-[#777a88] border-[#777a88]/25 bg-[#777a88]/5',
}

export default function ReadinessScore({ score, grade }) {
  const gradeColor = GRADE_COLORS[grade] || GRADE_COLORS.F

  return (
    <div 
      className="p-8 border border-[rgba(255,255,255,0.06)] bg-[rgba(255,255,255,0.04)] flex flex-col items-center justify-center text-center relative overflow-hidden"
      style={{ borderRadius: 'var(--radius-lg)', boxShadow: 'none' }}
    >
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
              strokeLinecap: 'square',
            }}
          />
          <defs>
            <linearGradient id="gradient" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#ae9357" />
              <stop offset="40%" stopColor="#fff0cc" />
              <stop offset="70%" stopColor="#ae9357" />
            </linearGradient>
          </defs>
        </svg>
        <div className="absolute flex flex-col items-center justify-center">
          <span className="text-5xl font-extrabold text-[#F0F0F8] tracking-tight tabular-nums">{score}</span>
          <span className="text-xs text-[#8E9AAF] mt-1">out of 100</span>
        </div>
      </div>

      {/* Grade Badge */}
      <div className={`px-4 py-1.5 border text-sm font-semibold tracking-wide uppercase ${gradeColor}`} style={{ borderRadius: 'var(--radius-full)' }}>
        Grade {grade}
      </div>
    </div>
  )
}
