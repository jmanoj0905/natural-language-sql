import { useState, useRef } from 'react'
import { useToast } from '../hooks/useToast.jsx'
import { getEmoji } from '../data/providers'
import QueryProgress from './QueryProgress'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Badge } from '@/components/ui/badge'
import { Alert, AlertTitle, AlertDescription } from '@/components/ui/alert'
import { Card, CardContent } from '@/components/ui/card'

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

function detectWriteOp(sql) {
  if (!sql) return null
  const u = sql.trim().toUpperCase()
  if (u.startsWith('DROP TABLE') || u.startsWith('DROP DATABASE') || u.startsWith('TRUNCATE'))
    return { label: 'DESTRUCTIVE', variant: 'danger', tip: 'This will permanently delete data.' }
  if (u.startsWith('DELETE'))
    return { label: 'DELETE', variant: 'danger', tip: 'This will remove rows from your database.' }
  if (u.startsWith('UPDATE'))
    return { label: 'UPDATE', variant: 'warning', tip: 'This will modify existing rows.' }
  if (u.startsWith('INSERT'))
    return { label: 'INSERT', variant: 'warning', tip: 'This will add new rows to your database.' }
  if (u.startsWith('ALTER'))
    return { label: 'ALTER', variant: 'warning', tip: 'This will change your table structure.' }
  return null
}

export default function QueryInterface({
  onResult,
  databases = [],
  selectedDbIds = [],
  onDatabaseSelectionChange,
}) {
  const { showError } = useToast()
  const [question, setQuestion] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [stages, setStages] = useState(INITIAL_STAGES)
  const [showProgress, setShowProgress] = useState(false)
  const [progressError, setProgressError] = useState(null)
  const [pendingResult, setPendingResult] = useState(null)
  const abortRef = useRef(null)

  const updateStage = (stageId, status, duration_ms, message) =>
    setStages(prev => prev.map(s => s.id === stageId ? { ...s, status, duration_ms, message } : s))

  const handleCancel = () => {
    abortRef.current?.abort()
    abortRef.current = null
  }

  const runSSEQuery = async (execute) => {
    if (!question.trim()) return
    if (abortRef.current) abortRef.current.abort()

    const controller = new AbortController()
    abortRef.current = controller

    setLoading(true)
    setError(null)
    setProgressError(null)
    setPendingResult(null)
    setStages(INITIAL_STAGES.map(s => ({ ...s })))
    setShowProgress(true)

    const targetDbId = selectedDbIds[0] ?? null
    const url = targetDbId
      ? `/api/v1/query/natural/stream?database_id=${targetDbId}`
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
      setLoading(false)
    }
  }

  const handleRunPending = async () => {
    if (!pendingResult) return
    setPendingResult(null)
    await runSSEQuery(true)
  }

  const selectedDbs = databases.filter(db => selectedDbIds.includes(db.database_id))
  const writeWarning = pendingResult ? detectWriteOp(pendingResult.generated_sql) : null

  return (
    <Card className="gap-4 py-4">
      <CardContent className="space-y-4">
        {/* DB chips */}
        {selectedDbs.length > 0 ? (
          <div className="flex flex-wrap gap-2">
            {selectedDbs.map(db => (
              <Badge key={db.database_id} variant="neutral" className="gap-1.5 pr-1.5">
                <span>{getEmoji(db.db_type)}</span>
                <span>{db.nickname || db.database_id}</span>
                {!db.is_connected && <span className="text-danger ml-0.5">(offline)</span>}
                <button
                  onClick={() => onDatabaseSelectionChange?.(db.database_id)}
                  className="ml-0.5 text-foreground hover:text-danger leading-none"
                  title="Deselect"
                >×</button>
              </Badge>
            ))}
          </div>
        ) : (
          <Alert className="bg-warning/20">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
            <AlertTitle>Select a database in the sidebar to get started.</AlertTitle>
          </Alert>
        )}

        {/* Textarea */}
        <Textarea
          value={question}
          onChange={e => setQuestion(e.target.value)}
          onKeyDown={e => {
            if (e.key === 'Enter' && (e.metaKey || e.ctrlKey) && !loading) runSSEQuery(true)
          }}
          placeholder='e.g. "Show all users who signed up in the last 7 days"'
          className="resize-none h-24"
          disabled={loading}
        />

        {/* Error */}
        {error && !showProgress && (
          <Alert className="bg-danger/20">
            <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
            </svg>
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {/* Action buttons */}
        <div className="flex gap-2">
          <Button
            onClick={() => runSSEQuery(true)}
            disabled={loading || !question.trim() || selectedDbs.length === 0}
          >
            {loading ? (
              <>
                <svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
                PROCESSING...
              </>
            ) : (
              <>
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                GENERATE & RUN
              </>
            )}
          </Button>

          <Button
            variant="neutral"
            onClick={() => runSSEQuery(false)}
            disabled={loading || !question.trim() || selectedDbs.length === 0}
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
            </svg>
            PREVIEW SQL
          </Button>

          {loading && (
            <Button variant="neutral" onClick={handleCancel} className="hover:bg-danger/20">
              CANCEL
            </Button>
          )}

          <span className="ml-auto text-xs text-foreground/40 self-center hidden sm:block font-mono">
            ⌘↵ to run
          </span>
        </div>

        {/* Progress */}
        {showProgress && (loading || progressError || stages.some(s => s.status !== 'pending')) && (
          <QueryProgress stages={stages} error={progressError} />
        )}

        {/* Preview SQL result */}
        {pendingResult && !loading && (
          <div className="border-2 border-border rounded-base shadow-shadow overflow-hidden">
            <div className="flex items-center justify-between px-4 py-2 bg-main/10 border-b-2 border-border">
              <span className="text-xs font-heading text-foreground uppercase tracking-wide">Generated SQL — not yet executed</span>
              <button
                onClick={() => navigator.clipboard.writeText(pendingResult.generated_sql)}
                className="text-xs text-foreground hover:text-info font-heading transition-colors"
              >
                COPY
              </button>
            </div>
            <pre className="p-4 text-sm text-success font-mono bg-black overflow-x-auto whitespace-pre-wrap">
              {pendingResult.generated_sql}
            </pre>

            {pendingResult.sql_explanation && (
              <div className="px-4 py-2.5 border-t-2 border-border text-sm text-foreground/70 bg-secondary-background">
                {pendingResult.sql_explanation}
              </div>
            )}

            {/* Write op warning */}
            {writeWarning && (
              <Alert className={`rounded-none border-x-0 border-b-0 shadow-none ${
                writeWarning.variant === 'danger' ? 'bg-danger/20' : 'bg-warning/20'
              }`}>
                <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                </svg>
                <AlertDescription>
                  <span className="font-heading">{writeWarning.label}: </span>
                  {writeWarning.tip} Review the SQL above before running.
                </AlertDescription>
              </Alert>
            )}

            <div className="flex gap-2 p-3 bg-main/10 border-t-2 border-border">
              <Button
                onClick={handleRunPending}
                className={writeWarning?.variant === 'danger' ? 'bg-danger' : 'bg-success'}
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                {writeWarning ? 'RUN ANYWAY' : 'RUN THIS QUERY'}
              </Button>
              <Button variant="neutral" onClick={() => setPendingResult(null)}>
                DISCARD
              </Button>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
