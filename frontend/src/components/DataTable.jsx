import React, { useState, useMemo } from 'react'
import { ChevronLeft, ChevronRight, Download } from 'lucide-react'

const PAGE_SIZE = 10

export default function DataTable({ data, maxRows = PAGE_SIZE }) {
  const [page, setPage] = useState(0)

  // Handle different data shapes
  const rows = useMemo(() => {
    if (!data) return []
    if (Array.isArray(data)) return data
    if (typeof data === 'object') return [data]
    return [{ value: data }]
  }, [data])

  if (rows.length === 0) {
    return (
      <div style={{ padding: 16, color: 'var(--text-muted)', fontSize: '0.84rem' }}>
        No data to display.
      </div>
    )
  }

  const columns = Object.keys(rows[0])
  const totalPages = Math.ceil(rows.length / maxRows)
  const pageRows = rows.slice(page * maxRows, (page + 1) * maxRows)

  const downloadCsv = () => {
    const header = columns.join(',')
    const body = rows.map((r) => columns.map((c) => JSON.stringify(r[c] ?? '')).join(',')).join('\n')
    const blob = new Blob([header + '\n' + body], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'result.csv'
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div>
      <div className="data-table-wrapper">
        <table className="data-table">
          <thead>
            <tr>
              {columns.map((col) => (
                <th key={col}>{col}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {pageRows.map((row, i) => (
              <tr key={i}>
                {columns.map((col) => (
                  <td key={col}>{formatCell(row[col])}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="table-pagination">
        <span>{rows.length} row{rows.length !== 1 ? 's' : ''}</span>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <button className="btn-icon" disabled={page === 0} onClick={() => setPage(page - 1)}>
            <ChevronLeft size={16} />
          </button>
          <span>{page + 1} / {totalPages}</span>
          <button className="btn-icon" disabled={page >= totalPages - 1} onClick={() => setPage(page + 1)}>
            <ChevronRight size={16} />
          </button>
          <button className="btn-ghost" onClick={downloadCsv}>
            <Download size={14} /> CSV
          </button>
        </div>
      </div>
    </div>
  )
}

function formatCell(val) {
  if (val === null || val === undefined) return '—'
  if (typeof val === 'number') {
    return Number.isInteger(val) ? val.toLocaleString() : val.toLocaleString(undefined, { maximumFractionDigits: 4 })
  }
  return String(val)
}
