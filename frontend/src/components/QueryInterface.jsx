import { useState, useRef, useEffect } from 'react'
import axios from 'axios'
import { useToast } from '../hooks/useToast.jsx'
import DbIcon from './DbIcon'
import QueryProgress from './QueryProgress'
import { detectWriteOp } from '../utils/sql'

const INITIAL_STAGES = [
  { id: 'connect', status: 'pending' },
  { id: 'schema', status: 'pending' },
  { id: 'ai', status: 'pending' },
  { id: 'validate', status: 'pending' },
  { id: 'execute', status: 'pending' },
]

function parseSSE(buffer) {
  const parsed = []
  const lines = buffer.split('\n')
  let remainder = ''
  let currentEvent = null
  let currentData = ''

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]
    if (i === lines.length - 1 && !buffer.endsWith('\n')) {
      remainder = line
      break
    }
    if (line.startsWith('event: ')) {
      currentEvent = line.slice(7).trim()
    } else if (line.startsWith('data: ')) {
      currentData = line.slice(6)
    } else if (line === '') {
      if (currentEvent && currentData) {
        try { parsed.push({ event: currentEvent, data: JSON.parse(currentData) }) } catch { }
      }
      currentEvent = null
      currentData = ''
    }
  }
  return { parsed, remainder }
}

export default function QueryInterface({
  onResult,
  databases = [],
  selectedDbIds = [],
  onDatabaseSelectionChange,
  aiMode = true,
}) {
  const { showError } = useToast()
  const [question, setQuestion] = useState('')
  const [rawSql, setRawSql] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [stages, setStages] = useState(INITIAL_STAGES)
  const [showProgress, setShowProgress] = useState(false)
  const [progressError, setProgressError] = useState(null)
  const [pendingResult, setPendingResult] = useState(null)
  const [editedSql, setEditedSql] = useState('')
  const abortRef = useRef(null)
  const aiTimeoutRef = useRef(null)

  // Sync editedSql when pendingResult arrives
  useEffect(() => {
    if (pendingResult) {
      setEditedSql(pendingResult.generated_sql)
    }
  }, [pendingResult])

  // Escape key cancels active query
  useEffect(() => {
    const handler = (e) => {
      if (e.key === 'Escape' && loading) handleCancel()
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [loading])

  const updateStage = (stageId, status, duration_ms, message) =>
    setStages(prev => prev.map(s => s.id === stageId ? { ...s, status, duration_ms, message } : s))

  const handleCancel = () => {
    abortRef.current?.abort()
    abortRef.current = null
    clearTimeout(aiTimeoutRef.current)
  }

  // ── AI mode: SSE streaming ──────────────────────────────
  const runSSEQuery = async (execute) => {
    if (!question.trim()) return
    if (abortRef.current) abortRef.current.abort()
    clearTimeout(aiTimeoutRef.current)

    const controller = new AbortController()
    abortRef.current = controller

    setLoading(true)
    setError(null)
    setProgressError(null)
    setPendingResult(null)
    setStages(INITIAL_STAGES.map(s => ({ ...s })))
    setShowProgress(true)

    const url = selectedDbIds.length > 0
      ? `/api/v1/query/natural/stream?database_ids=${selectedDbIds.join(',')}`
      : `/api/v1/query/natural/stream`

    try {
      const response = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question, options: { execute, read_only: false } }),
        signal: controller.signal,
      })

      if (!response.ok) {
        const text = await response.text()
        let msg = 'Query failed'
        try { msg = JSON.parse(text).detail?.message || JSON.parse(text).detail || msg } catch { }
        throw new Error(msg)
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const { parsed, remainder } = parseSSE(buffer)
        buffer = remainder

        for (const evt of parsed) {
          if (evt.event === 'progress') {
            updateStage(evt.data.stage, evt.data.status, evt.data.duration_ms, evt.data.message)
            // Start slow-Ollama warning timer when AI stage begins
            if (evt.data.stage === 'ai' && evt.data.status === 'in_progress') {
              aiTimeoutRef.current = setTimeout(() => {
                setStages(prev => prev.map(s =>
                  s.id === 'ai' && s.status === 'in_progress'
                    ? { ...s, message: 'Still working... Ollama may be slow on first run.' }
                    : s
                ))
              }, 20000)
            } else if (evt.data.stage === 'ai' && evt.data.status === 'completed') {
              clearTimeout(aiTimeoutRef.current)
            }
          } else if (evt.event === 'error') {
            const msg = evt.data.error || 'An error occurred'
            setError(msg)
            setProgressError(msg)
            showError(msg)
            if (evt.data.stage) updateStage(evt.data.stage, 'error')
          } else if (evt.event === 'result') {
            if (!execute) {
              setPendingResult(evt.data)
            } else {
              onResult(evt.data)
            }
          }
        }
      }
    } catch (err) {
      if (err.name === 'AbortError') return
      const msg = err.message || 'Connection failed'
      setError(msg)
      setProgressError(msg)
      showError(msg)
    } finally {
      abortRef.current = null
      clearTimeout(aiTimeoutRef.current)
      setLoading(false)
    }
  }

  const handleRunPending = async () => {
    if (!pendingResult) return
    const { question, sql_explanation: explanation } = pendingResult
    const sql = editedSql  // use potentially edited SQL
    setPendingResult(null)
    setLoading(true)
    setError(null)

    try {
      if (selectedDbIds.length <= 1) {
        const dbId = selectedDbIds[0]
        const resp = await axios.post(`/api/v1/query/sql?database_id=${dbId}`, { sql })
        onResult({ ...resp.data, question, sql_explanation: explanation })
      } else {
        // Multi-DB: execute in parallel, merge rows (mirrors SSE multi-DB path)
        const nicknames = Object.fromEntries(
          databases
            .filter(db => selectedDbIds.includes(db.database_id))
            .map(db => [db.database_id, db.nickname || db.database_id])
        )
        const settled = await Promise.allSettled(
          selectedDbIds.map(dbId => axios.post(`/api/v1/query/sql?database_id=${dbId}`, { sql }))
        )
        const mergedRows = []
        let execTime = 0
        let origCols = []
        const warnings = []
        for (let i = 0; i < selectedDbIds.length; i++) {
          const dbId = selectedDbIds[i]
          if (settled[i].status === 'fulfilled') {
            const er = settled[i].value.data.execution_result
            execTime = Math.max(execTime, er.execution_time_ms || 0)
            if (!origCols.length) origCols = er.columns || []
            for (const row of (er.rows || [])) {
              mergedRows.push({ __source_db__: nicknames[dbId], ...row })
            }
          } else {
            warnings.push(`${nicknames[dbId]}: ${settled[i].reason?.message || 'failed'}`)
          }
        }
        onResult({
          question,
          generated_sql: sql,
          sql_explanation: explanation,
          execution_result: {
            rows: mergedRows,
            row_count: mergedRows.length,
            execution_time_ms: execTime,
            columns: mergedRows.length ? ['__source_db__', ...origCols] : [],
          },
          warnings,
          metadata: { database_ids: selectedDbIds, multi_db: true },
        })
      }
    } catch (err) {
      const msg = err.response?.data?.detail?.message || err.response?.data?.detail || err.message
      setError(msg)
      showError(msg)
    } finally {
      setLoading(false)
    }
  }

  // ── Raw SQL mode: direct execution ──────────────────────
  const runRawSQL = async () => {
    const sql = rawSql.trim()
    if (!sql || selectedDbIds.length === 0) return

    setLoading(true)
    setError(null)

    try {
      const dbId = selectedDbIds[0]
      const resp = await axios.post(
        `/api/v1/query/sql?database_id=${dbId}`,
        { sql }
      )
      onResult({
        question: sql,
        generated_sql: sql,
        sql_explanation: null,
        execution_result: resp.data.execution_result,
        metadata: {
          ...resp.data.metadata,
          database_id: dbId,
        },
      })
    } catch (err) {
      const msg = err.response?.data?.detail?.message || err.response?.data?.detail || err.message
      setError(msg)
      showError(msg)
    } finally {
      setLoading(false)
    }
  }

  const selectedDbs = databases.filter(db => selectedDbIds.includes(db.database_id))
  const selectedTypes = new Set(selectedDbs.map(db => db.db_type))
  const isMixedTypes = selectedTypes.size > 1
  const writeWarning = pendingResult ? detectWriteOp(editedSql) : null
  const rawWriteWarning = !aiMode ? detectWriteOp(rawSql) : null
  const hasNoDbs = selectedDbs.length === 0

  // ── Shared: DB chips ────────────────────────────────────
  const dbChips = selectedDbs.length > 0 ? (
    <div className="flex flex-wrap gap-2">
      {selectedDbs.map(db => (
        <span key={db.database_id} className="inline-flex items-center gap-1.5 px-3 py-1.5 brutalist-border rounded-full bg-main/20 font-label text-xs font-medium">
          <DbIcon dbType={db.db_type} className="w-3.5 h-3.5" />
          {db.nickname || db.database_id}
          {!db.is_connected && <span className="text-[#dc2626] ml-0.5">(offline)</span>}
          <button onClick={() => onDatabaseSelectionChange?.(db.database_id)} className="ml-0.5 text-foreground/60 hover:text-[#dc2626] leading-none text-base">&times;</button>
        </span>
      ))}
    </div>
  ) : null

  // ══════════════════════════════════════════════════════════
  //  RAW SQL MODE
  // ══════════════════════════════════════════════════════════
  if (!aiMode) {
    return (
      <section className="brutalist-border bg-white p-8 soft-shadow-lg rounded-2xl">
        <div className="flex flex-col gap-6">
          {/* Header */}
          <div className="flex items-center justify-between flex-wrap gap-3">
            <h1 className="font-heading font-black text-3xl uppercase tracking-tighter">SQL_EDITOR</h1>
          </div>

          {dbChips}

          {/* Empty state */}
          {hasNoDbs && (
            <div className="flex flex-col items-center justify-center py-12 gap-4 brutalist-border rounded-2xl bg-[#f8fafc]">
              <span className="material-symbols-outlined text-5xl text-foreground/30">cable</span>
              <div className="text-center">
                <p className="font-heading font-bold text-lg text-foreground/60">No database selected</p>
                <p className="font-label text-sm text-foreground/40 mt-1">Connect a database from the sidebar to start running SQL.</p>
              </div>
            </div>
          )}

          {!hasNoDbs && (
            <>
              {/* SQL editor */}
              <div className="brutalist-border bg-[#1a1c1d] rounded-xl overflow-hidden">
                <div className="flex items-center justify-between px-4 py-2 border-b border-white/10">
                  <div className="flex gap-2">
                    <div className="w-2.5 h-2.5 rounded-full bg-danger brutalist-border"></div>
                    <div className="w-2.5 h-2.5 rounded-full bg-main brutalist-border"></div>
                    <div className="w-2.5 h-2.5 rounded-full bg-success brutalist-border"></div>
                  </div>
                  <span className="font-mono text-[10px] text-white/40 uppercase">sql_input</span>
                </div>
                <textarea
                  value={rawSql}
                  onChange={e => setRawSql(e.target.value)}
                  onKeyDown={e => {
                    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey) && !loading) runRawSQL()
                  }}
                  className="w-full h-40 p-6 font-mono text-base text-success bg-transparent outline-none resize-none placeholder:text-white/20"
                  placeholder="SELECT * FROM users LIMIT 10;"
                  disabled={loading}
                  spellCheck={false}
                />
              </div>

              {/* Write warning */}
              {rawWriteWarning && (
                <div className={`flex items-center gap-2 px-4 py-3 brutalist-border rounded-xl font-label text-sm ${
                  rawWriteWarning.variant === 'danger' ? 'bg-danger' : 'bg-warning/30'
                }`}>
                  <span className="material-symbols-outlined text-base">warning</span>
                  <span className="font-heading">{rawWriteWarning.label}: </span>
                  {rawWriteWarning.tip}
                </div>
              )}

              {/* Action buttons */}
              <div className="flex items-center gap-3 flex-wrap">
                <span className="text-xs text-foreground/40 font-mono mr-auto hidden sm:block">&#8984;&#x23CE; to run · Esc to cancel</span>

                {loading && (
                  <button
                    onClick={() => setLoading(false)}
                    className="brutalist-border bg-danger px-5 py-2.5 rounded-xl font-heading font-bold text-sm active-press hover:bg-[#fca5a5] transition-colors"
                  >
                    CANCEL
                  </button>
                )}

                <button
                  onClick={runRawSQL}
                  disabled={loading || !rawSql.trim()}
                  className="brutalist-border bg-success px-8 py-3 rounded-xl font-heading font-black text-base soft-shadow active-press hover:bg-[#86EFAC] transition-colors disabled:opacity-40 disabled:cursor-not-allowed disabled:active:transform-none disabled:active:shadow-[4px_4px_0px_0px_#1a1c1d] flex items-center gap-2"
                >
                  <span className="material-symbols-outlined text-xl">play_arrow</span>
                  {loading ? 'EXECUTING...' : 'RUN QUERY'}
                </button>
              </div>

              {/* Error */}
              {error && (
                <div className="flex items-center gap-2 px-4 py-3 bg-danger brutalist-border rounded-xl font-label text-sm">
                  <span className="material-symbols-outlined text-base">error</span>
                  {error}
                </div>
              )}
            </>
          )}
        </div>
      </section>
    )
  }

  // ══════════════════════════════════════════════════════════
  //  AI MODE (natural language)
  // ══════════════════════════════════════════════════════════
  return (
    <section className="brutalist-border bg-white p-8 soft-shadow-lg rounded-2xl">
      <div className="flex flex-col gap-6">
        {/* Header */}
        <div className="flex items-center flex-wrap gap-3">
          <h1 className="font-heading font-black text-3xl uppercase tracking-tighter">QUERY_BUILDER</h1>
        </div>

        {dbChips}

        {/* Empty state when no DB selected */}
        {hasNoDbs ? (
          <div className="flex flex-col items-center justify-center py-16 gap-4 brutalist-border rounded-2xl bg-[#f8fafc]">
            <span className="material-symbols-outlined text-5xl text-foreground/30">storage</span>
            <div className="text-center">
              <p className="font-heading font-bold text-xl text-foreground/60">Connect a database first</p>
              <p className="font-label text-sm text-foreground/40 mt-1">Select a database from the sidebar to start querying.</p>
            </div>
            <button
              onClick={() => document.querySelector('[data-action="connect-new"]')?.click()}
              className="brutalist-border bg-main px-6 py-2.5 rounded-xl font-heading font-bold text-sm soft-shadow active-press hover:bg-[#d8b4fe] transition-colors"
            >
              Connect a database
            </button>
          </div>
        ) : (
          <>
            {isMixedTypes && (
              <div className="flex items-center gap-2 px-4 py-3 bg-danger brutalist-border rounded-xl font-label text-sm">
                <span className="material-symbols-outlined text-base">error</span>
                Mixed database types — multi-DB queries require all databases to be the same type.
              </div>
            )}

            {/* Textarea */}
            <div className="relative">
              <textarea
                value={question}
                onChange={e => setQuestion(e.target.value)}
                onKeyDown={e => {
                  if (e.key === 'Enter' && (e.metaKey || e.ctrlKey) && !loading) runSSEQuery(true)
                }}
                className="w-full h-32 brutalist-border p-6 rounded-xl font-sans text-lg focus:ring-4 focus:ring-main outline-none resize-none bg-background/50"
                placeholder="Type your natural language request here..."
                disabled={loading}
              />
            </div>

            {/* Action buttons */}
            <div className="flex items-center gap-3 flex-wrap">
              <span className="text-xs text-foreground/40 font-mono mr-auto hidden sm:block">&#8984;&#x23CE; to run · Esc to cancel</span>

              {loading && (
                <button
                  onClick={handleCancel}
                  className="brutalist-border bg-danger px-5 py-2.5 rounded-xl font-heading font-bold text-sm active-press hover:bg-[#fca5a5] transition-colors"
                >
                  CANCEL
                </button>
              )}

              <button
                onClick={() => runSSEQuery(false)}
                disabled={loading || !question.trim() || isMixedTypes}
                className="brutalist-border bg-white px-6 py-2.5 rounded-xl font-heading font-bold text-sm soft-shadow active-press hover:bg-[#f1f5f9] transition-colors disabled:opacity-40 disabled:cursor-not-allowed disabled:active:transform-none disabled:active:shadow-[4px_4px_0px_0px_#1a1c1d]"
              >
                PREVIEW SQL
              </button>

              <button
                onClick={() => runSSEQuery(true)}
                disabled={loading || !question.trim() || isMixedTypes}
                className="brutalist-border bg-main px-8 py-3 rounded-xl font-heading font-black text-base soft-shadow active-press hover:bg-[#d8b4fe] transition-colors disabled:opacity-40 disabled:cursor-not-allowed disabled:active:transform-none disabled:active:shadow-[4px_4px_0px_0px_#1a1c1d]"
              >
                {loading ? 'PROCESSING...' : 'GENERATE SQL'}
              </button>
            </div>

            {/* Error */}
            {error && !showProgress && (
              <div className="flex items-center gap-2 px-4 py-3 bg-danger brutalist-border rounded-xl font-label text-sm">
                <span className="material-symbols-outlined text-base">error</span>
                {error}
              </div>
            )}

            {/* Progress */}
            {showProgress && (loading || progressError || stages.some(s => s.status !== 'pending')) && (
              <QueryProgress stages={stages} error={progressError} />
            )}

            {/* Preview SQL result — editable */}
            {pendingResult && !loading && (
              <div className="brutalist-border rounded-2xl overflow-hidden soft-shadow">
                <div className="flex items-center justify-between px-6 py-3 bg-main/10 border-b-2 border-border">
                  <span className="text-xs font-heading text-foreground uppercase tracking-wide">Generated SQL — edit before running</span>
                  <button
                    onClick={() => navigator.clipboard.writeText(editedSql)}
                    className="text-xs text-foreground hover:text-[#3b82f6] font-heading transition-colors"
                  >
                    COPY
                  </button>
                </div>

                {/* Editable SQL textarea */}
                <div className="bg-[#1a1c1d]">
                  <textarea
                    value={editedSql}
                    onChange={e => setEditedSql(e.target.value)}
                    className="w-full min-h-[120px] p-6 text-sm text-[#86EFAC] font-mono bg-transparent outline-none resize-y placeholder:text-white/20"
                    spellCheck={false}
                  />
                </div>

                {pendingResult.sql_explanation && (
                  <div className="px-6 py-3 border-t-2 border-border text-sm text-foreground/70 bg-white">
                    {pendingResult.sql_explanation}
                  </div>
                )}

                {writeWarning && (
                  <div className={`flex items-center gap-2 px-6 py-3 border-t-2 border-border text-sm font-label ${
                    writeWarning.variant === 'danger' ? 'bg-danger' : 'bg-warning/30'
                  }`}>
                    <span className="material-symbols-outlined text-base">warning</span>
                    <span className="font-heading">{writeWarning.label}: </span>
                    {writeWarning.tip}
                  </div>
                )}

                <div className="flex gap-3 p-4 bg-main/10 border-t-2 border-border">
                  <button
                    onClick={handleRunPending}
                    className={`brutalist-border px-6 py-2.5 rounded-xl font-heading font-bold text-sm soft-shadow active-press transition-colors ${
                      writeWarning?.variant === 'danger' ? 'bg-danger hover:bg-[#fca5a5]' : 'bg-success hover:bg-[#86EFAC]'
                    }`}
                  >
                    {writeWarning ? 'RUN ANYWAY' : 'RUN THIS QUERY'}
                  </button>
                  <button
                    onClick={() => setPendingResult(null)}
                    className="brutalist-border bg-white px-6 py-2.5 rounded-xl font-heading font-bold text-sm soft-shadow active-press hover:bg-[#f1f5f9] transition-colors"
                  >
                    DISCARD
                  </button>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </section>
  )
}
