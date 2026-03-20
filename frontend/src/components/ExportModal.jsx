import { useState } from 'react'

// ── helpers ──────────────────────────────────────────────────────────────────

function csvCell(val) {
  if (val === null || val === undefined) return ''
  const str = String(val)
  if (str.includes(',') || str.includes('"') || str.includes('\n')) {
    return `"${str.replace(/"/g, '""')}"`
  }
  return str
}

function buildCSV(columns, rows) {
  const header = columns.map(csvCell).join(',')
  const body = rows.map(row => columns.map(col => csvCell(row[col])).join(','))
  return [header, ...body].join('\r\n')
}

function triggerDownload(content, filename, mimeType) {
  const blob = new Blob([content], { type: mimeType })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

function safeFilename(question) {
  if (!question) return 'query_result'
  return question.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '').slice(0, 40) || 'query_result'
}

// ── sub-component ─────────────────────────────────────────────────────────────

function ExportRow({ icon, label, description, accentClass, onClick, btnLabel, btnActive }) {
  return (
    <div className="flex items-center gap-3 p-3 brutalist-border rounded-xl bg-background hover:bg-main/5 transition-colors">
      <div className={`w-9 h-9 rounded-lg brutalist-border ${accentClass} flex items-center justify-center shrink-0`}>
        <span className="material-symbols-outlined text-sm">{icon}</span>
      </div>
      <div className="flex-1 min-w-0">
        <p className="font-heading font-bold text-sm leading-tight">{label}</p>
        <p className="text-[11px] text-foreground/50 font-label leading-tight mt-0.5">{description}</p>
      </div>
      <button
        onClick={onClick}
        className={`brutalist-border px-3 py-1.5 rounded-lg font-heading font-bold text-xs active-press shrink-0 transition-colors ${
          btnActive ? 'bg-success text-[#065f46]' : 'bg-white hover:bg-main/20'
        }`}
      >
        {btnLabel}
      </button>
    </div>
  )
}

// ── main component ────────────────────────────────────────────────────────────

export default function ExportModal({ result, onClose }) {
  const [copied, setCopied] = useState(false)

  const { execution_result, question, generated_sql } = result
  const allRows = execution_result?.rows || []
  const allColumns = execution_result?.columns || []

  // Filter meta-columns that aren't real data
  const SKIP = new Set(['operation', 'affected_rows', 'message', '_write_summary'])
  const columns = allColumns.filter(c => !SKIP.has(c))

  // For write-only results (no real columns), fall back to all columns
  const cols = columns.length > 0 ? columns : allColumns
  const rows = allRows.filter(row => !row._write_summary && row.operation !== 'write')

  const base = safeFilename(question)
  const dateStr = new Date().toISOString().slice(0, 10)
  const filename = `${base}_${dateStr}`

  // ── handlers ──

  const handleCSV = () => {
    triggerDownload(buildCSV(cols, rows), `${filename}.csv`, 'text/csv;charset=utf-8;')
  }

  const handleJSON = () => {
    const data = rows.map(row => Object.fromEntries(cols.map(c => [c, row[c] ?? null])))
    triggerDownload(JSON.stringify(data, null, 2), `${filename}.json`, 'application/json')
  }

  const handleCopy = async () => {
    const header = cols.join('\t')
    const body = rows.map(row => cols.map(col => {
      const v = row[col]
      return v === null || v === undefined ? '' : String(v)
    }).join('\t'))
    await navigator.clipboard.writeText([header, ...body].join('\n'))
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: 'rgba(26,28,29,0.65)' }}
      onClick={e => { if (e.target === e.currentTarget) onClose() }}
    >
      <div className="bg-white brutalist-border soft-shadow-lg rounded-2xl w-full max-w-sm overflow-hidden">

        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b-2 border-border bg-main/20">
          <div>
            <h2 className="font-heading font-black uppercase tracking-tight text-lg leading-none">EXPORT_DATA</h2>
            <p className="text-xs text-foreground/50 font-mono mt-1">
              {rows.length} rows · {cols.length} columns
            </p>
          </div>
          <button
            onClick={onClose}
            className="material-symbols-outlined p-1 rounded-full hover:bg-foreground/10 transition-colors"
          >
            close
          </button>
        </div>

        {/* Options */}
        <div className="p-4 space-y-2.5">
          <ExportRow
            icon="table_chart"
            label="Download CSV"
            description="Comma-separated — opens in Excel, Sheets, Numbers"
            accentClass="bg-success"
            onClick={handleCSV}
            btnLabel="CSV"
          />
<ExportRow
            icon="content_paste"
            label="Copy to Clipboard"
            description="Tab-separated — paste into Excel or Google Sheets"
            accentClass="bg-main"
            onClick={handleCopy}
            btnLabel={copied ? 'COPIED!' : 'COPY'}
            btnActive={copied}
          />
          <ExportRow
            icon="data_object"
            label="Download JSON"
            description="Raw JSON array — for APIs and data pipelines"
            accentClass="bg-warning"
            onClick={handleJSON}
            btnLabel="JSON"
          />
        </div>

        {/* SQL preview footer */}
        {generated_sql && (
          <div className="px-5 py-3 border-t-2 border-border bg-[#1a1c1d]">
            <p className="text-[10px] font-mono text-success/70 truncate">{generated_sql.slice(0, 80)}{generated_sql.length > 80 ? '…' : ''}</p>
          </div>
        )}
      </div>
    </div>
  )
}
