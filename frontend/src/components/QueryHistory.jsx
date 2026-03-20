function exportHistoryAsSQL(history) {
  const lines = history.map((item, i) => [
    `-- [${ i + 1 }] ${ item.timestamp }`,
    `-- ${ item.question }`,
    item.sql.trim().endsWith(';') ? item.sql.trim() : item.sql.trim() + ';',
    '',
  ].join('\n'))

  const content = [
    `-- NLSQL Query History Export`,
    `-- Exported: ${ new Date().toLocaleString() }`,
    `-- ${ history.length } queries`,
    '',
    ...lines,
  ].join('\n')

  const blob = new Blob([content], { type: 'text/plain;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `query_history_${ new Date().toISOString().slice(0, 10) }.sql`
  a.click()
  URL.revokeObjectURL(url)
}

export default function QueryHistory({ history }) {
  if (!history || history.length === 0) {
    return (
      <section className="brutalist-border bg-white p-12 soft-shadow-lg rounded-2xl text-center">
        <span className="material-symbols-outlined text-5xl text-foreground/20 mb-4 block">schedule</span>
        <h3 className="font-heading font-black text-xl text-foreground uppercase">NO QUERY HISTORY</h3>
        <p className="mt-2 text-sm text-foreground/50">Your executed queries will appear here</p>
      </section>
    )
  }

  return (
    <div className="space-y-6">
      <section className="brutalist-border bg-white p-6 soft-shadow-lg rounded-2xl">
        <div className="flex items-center justify-between gap-4">
          <div>
            <h2 className="font-heading font-black text-2xl uppercase tracking-tighter">QUERY_HISTORY</h2>
            <p className="text-sm text-foreground/50 mt-1">Last {history.length} queries executed</p>
          </div>
          <button
            onClick={() => exportHistoryAsSQL(history)}
            className="brutalist-border bg-white px-4 py-2 rounded-xl font-heading font-bold text-sm soft-shadow active-press hover:bg-main/20 transition-colors flex items-center gap-2 shrink-0"
          >
            <span className="material-symbols-outlined text-base">file_download</span>
            EXPORT SQL
          </button>
        </div>
      </section>

      {history.map((item) => (
        <section key={item.id} className="brutalist-border bg-white soft-shadow rounded-2xl overflow-hidden hover:translate-x-[2px] hover:translate-y-[2px] hover:shadow-none transition-all">
          <div className="p-5 space-y-3">
            <div className="flex items-start justify-between gap-4">
              <h3 className="text-sm font-heading font-bold text-foreground">{item.question}</h3>
              <div className="flex items-center gap-2 shrink-0">
                <span className="bg-main/30 px-2 py-0.5 rounded-full brutalist-border text-[10px] font-bold">{item.rowCount} rows</span>
                <span className="text-xs text-foreground/50 font-mono">{item.executionTime.toFixed(1)}ms</span>
              </div>
            </div>
            <p className="text-xs text-foreground/40 font-mono">{item.timestamp}</p>
          </div>

          <div className="bg-[#1a1c1d] px-5 py-4 border-t-2 border-border">
            <pre className="text-xs text-success font-mono overflow-x-auto">{item.sql}</pre>
          </div>

          {item.explanation && (
            <div className="px-5 py-3 bg-info/10 border-t-2 border-border">
              <p className="text-xs text-foreground/70">{item.explanation}</p>
            </div>
          )}
        </section>
      ))}
    </div>
  )
}
