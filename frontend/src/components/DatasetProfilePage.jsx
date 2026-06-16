import React, { useState, useEffect } from 'react'
import { getProfile } from '../services/mlApi'
import StatCard from './StatCard'
import { Rows, Columns, HardDrive, Hash, Type, Copy } from 'lucide-react'

export default function DatasetProfilePage({ sessionId }) {
  const [profile, setProfile] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    async function loadProfile() {
      setLoading(true)
      setError(null)
      try {
        const data = await getProfile(sessionId)
        setProfile(data)
      } catch (err) {
        setError(err.response?.data?.detail || err.message || 'Failed to load dataset profile')
      } finally {
        setLoading(false)
      }
    }
    loadProfile()
  }, [sessionId])

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[400px] gap-3">
        <div className="spinner" style={{ width: 40, height: 40 }} />
        <span className="text-[#8E9AAF] text-sm">Generating dataset profile...</span>
      </div>
    )
  }

  if (error) {
    return (
      <div className="p-6 rounded-xl border border-red-500/25 bg-red-500/10 text-center max-w-lg mx-auto my-8">
        <h3 className="text-red-500 font-bold mb-2">Error Loading Profile</h3>
        <p className="text-[#8E9AAF] text-sm">{error}</p>
      </div>
    )
  }

  if (!profile) return null

  // Map missing values list to a lookup dictionary for easy schema display
  const missingLookup = (profile.missing_values || []).reduce((acc, curr) => {
    acc[curr.column] = curr
    return acc
  }, {})

  return (
    <div className="space-y-8 animate-fade-in">
      <div className="overview-header">
        <h1><span className="gradient-text">Dataset Profile</span></h1>
        <p>Detailed structural profile and descriptive statistics of the uploaded dataset.</p>
      </div>

      {/* Grid of Overview stats */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        <StatCard title="Total Rows" value={profile.rows.toLocaleString()} icon={Rows} />
        <StatCard title="Total Columns" value={profile.columns.toLocaleString()} icon={Columns} />
        <StatCard title="Memory Usage" value={`${profile.memory_mb} MB`} icon={HardDrive} />
        <StatCard title="Numeric Features" value={profile.numerical_count} icon={Hash} />
        <StatCard title="Categorical Features" value={profile.categorical_count} icon={Type} />
        <StatCard
          title="Duplicate Rows"
          value={profile.duplicate_rows?.count?.toLocaleString() || '0'}
          icon={Copy}
          description={`${profile.duplicate_rows?.percentage || '0'}% duplication rate`}
        />
      </div>

      {/* Column Details Schema Table */}
      <div className="p-6 rounded-xl border border-[rgba(255,255,255,0.06)] bg-[rgba(255,255,255,0.02)]">
        <h2 className="text-lg font-bold text-[#F0F0F8] mb-4">Schema Information</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-[rgba(255,255,255,0.06)] text-[#8E9AAF] text-xs font-semibold uppercase tracking-wider">
                <th className="pb-3 pl-4">Column Name</th>
                <th className="pb-3 pl-4">Data Type</th>
                <th className="pb-3 pl-4 text-right pr-4">Missing Value %</th>
              </tr>
            </thead>
            <tbody>
              {profile.column_names.map((colName) => {
                const dtype = profile.dtypes[colName] || 'unknown'
                const missing = missingLookup[colName]
                const missingPct = missing ? missing.null_percentage : 0
                const missingCount = missing ? missing.null_count : 0

                return (
                  <tr key={colName} className="border-b border-[rgba(255,255,255,0.03)] hover:bg-[rgba(255,255,255,0.01)] text-sm transition-colors duration-150">
                    <td className="py-3 pl-4 font-medium text-[#F0F0F8]">{colName}</td>
                    <td className="py-3 pl-4 font-mono text-xs text-[#8E9AAF]">{dtype}</td>
                    <td className="py-3 pl-4 text-right pr-4">
                      {missingCount > 0 ? (
                        <span className={missingPct > 20 ? 'text-red-400 font-semibold' : missingPct > 5 ? 'text-yellow-400 font-semibold' : 'text-blue-400'}>
                          {missingPct}% ({missingCount.toLocaleString()} nulls)
                        </span>
                      ) : (
                        <span className="text-emerald-500">✓ 0% complete</span>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Descriptive statistics for numerical columns */}
      {profile.numerical_stats && profile.numerical_stats.length > 0 && (
        <div className="p-6 rounded-xl border border-[rgba(255,255,255,0.06)] bg-[rgba(255,255,255,0.02)]">
          <h2 className="text-lg font-bold text-[#F0F0F8] mb-4">Descriptive Statistics</h2>
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-[rgba(255,255,255,0.06)] text-[#8E9AAF] text-xs font-semibold uppercase tracking-wider">
                  <th className="pb-3 pl-4">Numerical Feature</th>
                  <th className="pb-3 pl-4 text-right">Mean</th>
                  <th className="pb-3 pl-4 text-right">Std Dev</th>
                  <th className="pb-3 pl-4 text-right">Min</th>
                  <th className="pb-3 pl-4 text-right">Median</th>
                  <th className="pb-3 pl-4 text-right pr-4">Max</th>
                </tr>
              </thead>
              <tbody>
                {profile.numerical_stats.map((stat) => (
                  <tr key={stat.column} className="border-b border-[rgba(255,255,255,0.03)] hover:bg-[rgba(255,255,255,0.01)] text-sm transition-colors duration-150">
                    <td className="py-3 pl-4 font-medium text-[#F0F0F8]">{stat.column}</td>
                    <td className="py-3 pl-4 text-right font-mono text-[#8E9AAF]">{stat.mean.toLocaleString()}</td>
                    <td className="py-3 pl-4 text-right font-mono text-[#8E9AAF]">{stat.std.toLocaleString()}</td>
                    <td className="py-3 pl-4 text-right font-mono text-[#8E9AAF]">{stat.min.toLocaleString()}</td>
                    <td className="py-3 pl-4 text-right font-mono text-[#8E9AAF]">{stat.median.toLocaleString()}</td>
                    <td className="py-3 pl-4 text-right pr-4 font-mono text-[#8E9AAF]">{stat.max.toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
