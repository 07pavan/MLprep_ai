import React from 'react'

export default function StatCard({ title, value, icon: Icon, description }) {
  return (
    <div className="p-6 rounded-xl border border-[rgba(255,255,255,0.06)] bg-[rgba(255,255,255,0.04)] hover:bg-[rgba(255,255,255,0.07)] transition-all duration-200 shadow-lg flex items-start justify-between">
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-[#8E9AAF] mb-1 truncate">{title}</p>
        <h3 className="text-2xl font-bold text-[#F0F0F8] tracking-tight truncate">{value}</h3>
        {description && <p className="text-xs text-[#8E9AAF] mt-1 opacity-70 truncate">{description}</p>}
      </div>
      {Icon && (
        <div className="p-3 rounded-lg bg-[rgba(255,255,255,0.03)] text-[#FF007F] flex-shrink-0">
          <Icon size={20} />
        </div>
      )}
    </div>
  )
}
