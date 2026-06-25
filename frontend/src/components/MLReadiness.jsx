import React, { useState, useEffect } from 'react'
import { getMLReadiness } from '../services/mlApi'
import ReadinessScore from './ReadinessScore'
import { CheckCircle2, AlertTriangle, ListOrdered } from 'lucide-react'

export default function MLReadiness({ sessionId }) {
  if (!sessionId) {
    return (
      <div className="p-8 text-center text-[#8E9AAF] text-sm bg-[rgba(255,255,255,0.02)] rounded-lg border border-[rgba(255,255,255,0.06)] max-w-lg mx-auto my-12 animate-fade-in">
        No active dataset. Please upload a dataset file or select one from the Datasets page.
      </div>
    )
  }

  const [report, setReport] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    async function loadReadiness() {
      setLoading(true)
      setError(null)
      try {
        const data = await getMLReadiness(sessionId)
        setReport(data)
      } catch (err) {
        setError(err.response?.data?.detail || err.message || 'Failed to load readiness score')
      } finally {
        setLoading(false)
      }
    }
    loadReadiness()
  }, [sessionId])

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[400px] gap-3">
        <div className="spinner" style={{ width: 40, height: 40 }} />
        <span className="text-[#8E9AAF] text-sm">Evaluating ML readiness...</span>
      </div>
    )
  }

  if (error) {
    return (
      <div className="p-6 rounded-xl border border-red-500/25 bg-red-500/10 text-center max-w-lg mx-auto my-8">
        <h3 className="text-red-500 font-bold mb-2">Evaluation Failed</h3>
        <p className="text-[#8E9AAF] text-sm">{error}</p>
      </div>
    )
  }

  if (!report) return null

  const { score, grade, strengths, problems, recommendations } = report

  return (
    <div className="space-y-8 animate-fade-in">
      <div className="overview-header">
        <h1><span className="gradient-text">ML Readiness Scorecard</span></h1>
        <p>Evaluate your dataset's structural readiness and suitability for machine learning pipelines.</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Left Side - Large circular score gauge */}
        <div className="lg:col-span-1">
          <ReadinessScore score={score} grade={grade} />
        </div>

        {/* Right Side - Strengths, Problems, and Recommendations */}
        <div className="lg:col-span-2 space-y-8">
          
          {/* Strengths Card */}
          {strengths && strengths.length > 0 && (
            <div className="p-6 rounded-xl border border-[rgba(255,255,255,0.06)] bg-[rgba(255,255,255,0.02)]">
              <h3 className="text-base font-bold text-[#F0F0F8] mb-4 flex items-center gap-2">
                <CheckCircle2 className="text-emerald-500" size={20} />
                Dataset Strengths
              </h3>
              <ul className="space-y-3 pl-0 list-none m-0">
                {strengths.map((str, idx) => (
                  <li key={idx} className="flex items-start gap-2.5 text-sm text-[#8E9AAF]">
                    <span className="text-emerald-500 font-bold mt-0.5">✓</span>
                    <span className="leading-relaxed">{str}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Problems Card */}
          {problems && problems.length > 0 && (
            <div className="p-6 rounded-xl border border-[rgba(255,255,255,0.06)] bg-[rgba(255,255,255,0.02)]">
              <h3 className="text-base font-bold text-[#F0F0F8] mb-4 flex items-center gap-2">
                <AlertTriangle className="text-yellow-500" size={20} />
                Data Impediments
              </h3>
              <ul className="space-y-3 pl-0 list-none m-0">
                {problems.map((prob, idx) => (
                  <li key={idx} className="flex items-start gap-2.5 text-sm text-[#8E9AAF]">
                    <span className="text-yellow-500 font-bold mt-0.5">⚠</span>
                    <span className="leading-relaxed">{prob}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Recommendations checklist */}
          {recommendations && recommendations.length > 0 && (
            <div className="p-6 rounded-xl border border-[rgba(255,255,255,0.06)] bg-[rgba(255,255,255,0.02)]">
              <h3 className="text-base font-bold text-[#F0F0F8] mb-4 flex items-center gap-2">
                <ListOrdered className="text-black" size={20} />
                Recommended Actions
              </h3>
              <ol className="space-y-4 pl-0 list-none m-0">
                {recommendations.map((rec, idx) => (
                  <li key={idx} className="flex items-start gap-3 text-sm text-[#8E9AAF]">
                    <div className="w-5 h-5 rounded-full bg-black/10 border border-black/25 text-black text-xs font-bold flex items-center justify-center flex-shrink-0 mt-0.5 font-mono">
                      {idx + 1}
                    </div>
                    <span className="leading-relaxed pt-0.5">{rec}</span>
                  </li>
                ))}
              </ol>
            </div>
          )}

        </div>
      </div>
    </div>
  )
}
