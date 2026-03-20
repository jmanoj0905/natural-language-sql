import { useState, useMemo, useEffect } from 'react'
import ExportModal from './ExportModal'
import { detectWriteOp } from '../utils/sql'

const ROWS_PER_PAGE = 50
// Backend auto-applies LIMIT 100; row_count at this threshold likely means results were cut off
const TRUNCATION_THRESHOLD = 100

export default function ResultsDisplay({ result }) {
  const [sqlExpanded, setSqlExpanded] = useState(false)
  const [copied, setCopied] = useState(false)
  const [showExport, setShowExport] = useState(false)
  const [sortCol, setSortCol] = useState(null)
  const [sortDir, setSortDir] = useState('asc')
  const [currentPage, setCurrentPage] = useState(0)

  // Reset sort/page when result changes
  useEffect(() => {
    setSortCol(null)
    setSortDir('asc')
    setCurrentPage(0)
  }, [result])

  if (!result) return null

  const { generated_sql, sql_explanation, execution_result, metadata } = result
  const writeOp = detectWriteOp(generated_sql)
  const firstRow = execution_result?.rows?.[0]
  const isWriteResult = firstRow?.operation === 'write'

  const handleCopy = () => {
    navigator.clipboard.writeText(generated_sql)
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }

  const handleSort = (col) => {
    if (sortCol === col) {
      setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    } else {
      setSortCol(col)
      setSortDir('asc')
    }
    setCurrentPage(0)
  }

  const displayCols = execution_result?.columns?.filter(col => col !== '__source_db__') ?? []

  const sortedRows = useMemo(() => {
    const rows = [...(execution_result?.rows ?? [])]
    if (!sortCol) return rows
    return rows.sort((a, b) => {
      const aVal = a[sortCol]
      const bVal = b[sortCol]
      if (aVal === null && bVal === null) return 0
      if (aVal === null) return sortDir === 'asc' ? 1 : -1
      if (bVal === null) return sortDir === 'asc' ? -1 : 1
      if (typeof aVal === 'number' && typeof bVal === 'number')
        return sortDir === 'asc' ? aVal - bVal : bVal - aVal
      return sortDir === 'asc'
        ? String(aVal).localeCompare(String(bVal))
        : String(bVal).localeCompare(String(aVal))
    })
  }, [execution_result?.rows, sortCol, sortDir])

  const totalPages = Math.ceil(sortedRows.length / ROWS_PER_PAGE)
  const pagedRows = sortedRows.slice(currentPage * ROWS_PER_PAGE, (currentPage + 1) * ROWS_PER_PAGE)

  const rowCount = execution_result?.row_count ?? 0
  const isTruncated = !isWriteResult && rowCount >= TRUNCATION_THRESHOLD
  const isMultiDb = metadata?.multi_db && metadata?.database_nicknames?.length > 1

  return (
    <>
    <div className="space-y-8">
      {/* SQL Output (terminal style) */}
      <div className="brutalist-border bg-[#1a1c1d] p-1 soft-shadow rounded-2xl overflow-hidden">
        <div className="flex items-center justify-between px-6 py-3 border-b border-white/10 mb-1">
          <div className="flex gap-2">
            <div className="w-3 h-3 rounded-full brutalist-border bg-danger"></div>
            <div className="w-3 h-3 rounded-full brutalist-border bg-main"></div>
            <div className="w-3 h-3 rounded-full brutalist-border bg-success"></div>
          </div>
          <div className="flex items-center gap-3">
            {writeOp && (
              <span className={`px-3 py-0.5 rounded-full brutalist-border text-[10px] font-bold ${
                writeOp.variant === 'danger' ? 'bg-danger text-[#520c00]' : 'bg-warning text-[#1a1c1d]'
              }`}>
                {writeOp.label}
              </span>
            )}
            <span className="font-mono text-xs text-white/50 font-bold">SQL_OUTPUT</span>
          </div>
        </div>
        <div className="relative group">
          <pre className={`p-8 font-mono text-lg leading-relaxed text-success overflow-x-auto whitespace-pre-wrap ${
            !sqlExpanded ? 'max-h-48' : ''
          }`}>
            {generated_sql}
          </pre>
          <div className="absolute top-3 right-3 flex gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
            <button onClick={() => setSqlExpanded(p => !p)} className="px-2 py-1 text-xs font-heading text-white/50 hover:text-white bg-white/10 rounded-lg transition-colors">
              {sqlExpanded ? 'COLLAPSE' : 'EXPAND'}
            </button>
            <button onClick={handleCopy} className="px-2 py-1 text-xs font-heading text-white/50 hover:text-white bg-white/10 rounded-lg transition-colors">
              {copied ? 'COPIED!' : 'COPY'}
            </button>
          </div>
        </div>
      </div>

      {/* Results */}
      {execution_result && (
        <section className="brutalist-border bg-white overflow-hidden soft-shadow rounded-2xl">
          {/* Header */}
          <div className="bg-[#f1f5f9] p-5 border-b-2 border-border flex justify-between items-center flex-wrap gap-3">
            <div className="flex items-center gap-3 flex-wrap">
              <h3 className="font-heading font-black uppercase text-xl">QUERY_RESULTS</h3>
              {isWriteResult ? (
                <span className="bg-success px-3 py-1 rounded-full brutalist-border text-[10px] font-bold text-[#065f46]">
                  {firstRow?.affected_rows ?? 0} ROWS AFFECTED
                </span>
              ) : (
                <span className="bg-main/30 px-3 py-1 rounded-full brutalist-border text-[10px] font-bold">
                  {rowCount} {rowCount === 1 ? 'ROW' : 'ROWS'}
                </span>
              )}
              <span className="text-xs text-foreground/50 font-mono">
                {(execution_result.execution_time_ms ?? 0).toFixed(1)}ms
              </span>
              {/* Multi-DB merged-from banner */}
              {isMultiDb && (
                <span className="flex items-center gap-1.5 px-3 py-1 rounded-full brutalist-border text-[10px] font-bold bg-[#dbeafe] text-[#1e3a8a]">
                  <span className="material-symbols-outlined text-xs">merge</span>
                  Merged from {metadata.database_nicknames.length} databases
                </span>
              )}
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => setShowExport(true)}
                className="p-2 rounded-lg brutalist-border bg-white hover:bg-main/20 active-press transition-colors"
                title="Export data"
              >
                <span className="material-symbols-outlined text-sm">download</span>
              </button>
            </div>
          </div>

          {/* Truncation notice */}
          {isTruncated && (
            <div className="flex items-center gap-2 px-5 py-2.5 bg-warning/20 border-b-2 border-border font-label text-xs">
              <span className="material-symbols-outlined text-sm">info</span>
              Showing first {rowCount} rows — results may be limited. Export to CSV for full data.
            </div>
          )}

          {/* Write op result */}
          {isWriteResult && (
            <div className="px-6 py-8 text-center">
              <span className="inline-flex items-center gap-2 px-6 py-3 bg-success/30 brutalist-border rounded-xl font-heading text-sm">
                <span className="material-symbols-outlined">check_circle</span>
                {firstRow?.message ?? 'Operation completed'}
              </span>
            </div>
          )}

          {/* Select result table */}
          {!isWriteResult && sortedRows.length > 0 && (
            <>
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse">
                  <thead>
                    <tr className="bg-[#f8fafc]">
                      {displayCols.map((col, i) => (
                        <th
                          key={i}
                          onClick={() => handleSort(col)}
                          className="p-4 border-b-2 border-r-2 border-border font-heading font-black uppercase text-sm last:border-r-0 cursor-pointer hover:bg-main/20 select-none transition-colors"
                        >
                          <span className="flex items-center gap-1.5">
                            {col}
                            {sortCol === col ? (
                              <span className="material-symbols-outlined text-sm text-[#7d4e58]">
                                {sortDir === 'asc' ? 'arrow_upward' : 'arrow_downward'}
                              </span>
                            ) : (
                              <span className="material-symbols-outlined text-sm text-foreground/20">unfold_more</span>
                            )}
                          </span>
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="font-mono text-sm">
                    {pagedRows.map((row, ri) => (
                      <tr key={ri} className="hover:bg-main/10 border-b border-foreground/10 transition-colors">
                        {displayCols.map((col, ci) => {
                          const val = row[col]
                          const isNum = val !== null && !isNaN(Number(val)) && typeof val !== 'boolean'
                          return (
                            <td
                              key={ci}
                              className={`p-4 border-r-2 border-foreground/10 last:border-r-0 max-w-xs truncate ${isNum ? 'text-right tabular-nums' : ''}`}
                            >
                              {val === null ? (
                                <span className="text-foreground/25 italic text-xs">null</span>
                              ) : typeof val === 'boolean' ? (
                                <span className={`px-2 py-0.5 rounded-full brutalist-border text-[10px] font-bold ${
                                  val ? 'bg-success text-[#065f46]' : 'bg-foreground/10'
                                }`}>
                                  {val ? 'true' : 'false'}
                                </span>
                              ) : (
                                String(val)
                              )}
                            </td>
                          )
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Pagination */}
              {totalPages > 1 && (
                <div className="flex items-center justify-between px-5 py-3 border-t-2 border-border bg-[#f8fafc]">
                  <span className="font-mono text-xs text-foreground/50">
                    Page {currentPage + 1} of {totalPages} &nbsp;({sortedRows.length} rows)
                  </span>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => setCurrentPage(0)}
                      disabled={currentPage === 0}
                      className="px-2 py-1 brutalist-border rounded-lg font-heading text-xs disabled:opacity-30 hover:bg-main/20 active-press transition-colors"
                    >
                      «
                    </button>
                    <button
                      onClick={() => setCurrentPage(p => Math.max(0, p - 1))}
                      disabled={currentPage === 0}
                      className="px-3 py-1 brutalist-border rounded-lg font-heading text-xs disabled:opacity-30 hover:bg-main/20 active-press transition-colors"
                    >
                      PREV
                    </button>
                    <button
                      onClick={() => setCurrentPage(p => Math.min(totalPages - 1, p + 1))}
                      disabled={currentPage >= totalPages - 1}
                      className="px-3 py-1 brutalist-border rounded-lg font-heading text-xs disabled:opacity-30 hover:bg-main/20 active-press transition-colors"
                    >
                      NEXT
                    </button>
                    <button
                      onClick={() => setCurrentPage(totalPages - 1)}
                      disabled={currentPage >= totalPages - 1}
                      className="px-2 py-1 brutalist-border rounded-lg font-heading text-xs disabled:opacity-30 hover:bg-main/20 active-press transition-colors"
                    >
                      »
                    </button>
                  </div>
                </div>
              )}
            </>
          )}

          {/* Empty result */}
          {!isWriteResult && sortedRows.length === 0 && (
            <div className="py-12 text-center text-foreground/40">
              <span className="material-symbols-outlined text-4xl mb-2 block">inbox</span>
              <p className="font-heading">No rows returned</p>
            </div>
          )}

          {/* Warnings */}
          {result.warnings?.length > 0 && (
            <div className="px-5 py-3 border-t-2 border-border bg-warning/20 space-y-1">
              <span className="text-xs font-heading uppercase">Partial results — some databases failed:</span>
              {result.warnings.map((w, i) => (
                <p key={i} className="text-xs text-foreground/70 font-mono">{w}</p>
              ))}
            </div>
          )}

          {/* Explanation */}
          {sql_explanation && (
            <p className="px-6 py-4 text-sm text-foreground/70 leading-relaxed border-t-2 border-border bg-white">
              {sql_explanation}
            </p>
          )}

          {/* Footer */}
          <div className="flex items-center gap-4 px-5 py-3 bg-main/10 border-t-2 border-border text-xs text-foreground/50 font-mono">
            <span>{metadata?.ai_model}</span>
            {isMultiDb && (
              <span className="text-[#3b82f6]">
                {metadata.database_nicknames.join(', ')}
              </span>
            )}
            <span className="ml-auto">{metadata?.timestamp ? new Date(metadata.timestamp).toLocaleTimeString() : ''}</span>
          </div>
        </section>
      )}
    </div>

    {showExport && (
      <ExportModal result={result} onClose={() => setShowExport(false)} />
    )}
    </>
  )
}
