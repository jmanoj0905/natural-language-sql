import { useState, useRef } from 'react'
import { useToast } from '../hooks/useToast.jsx'
import { getEmoji, getLabel } from '../data/providers'
import QueryProgress from './QueryProgress'

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
        try {
          parsed.push({ event: currentEvent, data: JSON.parse(currentData) })
        } catch {
          // skip malformed JSON
        }
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
}) {
  const { showError } = useToast()
  const [question, setQuestion] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [readOnlyMode, setReadOnlyMode] = useState(true)
  const [executeQuery, setExecuteQuery] = useState(true)
  const [generatedResult, setGeneratedResult] = useState(null)
  const [stages, setStages] = useState(INITIAL_STAGES)
  const [showProgress, setShowProgress] = useState(false)
  const [progressError, setProgressError] = useState(null)
  const abortRef = useRef(null)

  const detectDangerousSQL = (sql) => {
    if (!sql) return null
    const u = sql.toUpperCase()
    const ops = []
    if (u.includes('DELETE FROM') || u.includes('DELETE ')) ops.push({ type: 'DELETE', severity: 'high', message: 'Will DELETE rows from table(s)' })
    if (u.includes('UPDATE ') && u.includes(' SET ')) ops.push({ type: 'UPDATE', severity: 'high', message: 'Will UPDATE existing rows' })
    if (u.includes('DROP TABLE') || u.includes('DROP DATABASE')) ops.push({ type: 'DROP', severity: 'critical', message: 'Will DROP table(s) or database — PERMANENT' })
    if (u.includes('TRUNCATE')) ops.push({ type: 'TRUNCATE', severity: 'critical', message: 'Will TRUNCATE table — all data deleted' })
    if (u.includes('INSERT INTO')) ops.push({ type: 'INSERT', severity: 'medium', message: 'Will INSERT new rows' })
    if (u.includes('ALTER TABLE')) ops.push({ type: 'ALTER', severity: 'high', message: 'Will ALTER table structure' })
    return ops.length > 0 ? ops : null
  }

  const handleReadOnlyToggle = () => {
    const next = !readOnlyMode
    setReadOnlyMode(next)
    if (!next) setExecuteQuery(false)
  }

  const updateStage = (stageId, status, duration_ms, message) => {
    setStages(prev => prev.map(s => s.id === stageId ? { ...s, status, duration_ms, message } : s))
  }

  const handleCancel = () => {
    if (abortRef.current) {
      abortRef.current.abort()
      abortRef.current = null
    }
  }

  const runSSEQuery = async (queryQuestion, options) => {
    // Cancel any in-flight request
    if (abortRef.current) abortRef.current.abort()
    const controller = new AbortController()
    abortRef.current = controller

    setLoading(true)
    setError(null)
    setProgressError(null)
    setStages(INITIAL_STAGES.map(s => ({ ...s })))
    setShowProgress(true)

    const targetDbId = selectedDbIds.length > 0 ? selectedDbIds[0] : null
    const url = targetDbId
      ? `/api/v1/query/natural/stream?database_id=${targetDbId}`
      : `/api/v1/query/natural/stream`

    try {
      const response = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: queryQuestion, options }),
        signal: controller.signal,
      })

      if (!response.ok) {
        const errorText = await response.text()
        let errorMessage = 'Query failed'
        try {
          const j = JSON.parse(errorText)
          errorMessage = j.detail?.message || j.detail || errorMessage
        } catch {
          errorMessage = errorText || errorMessage
        }
        throw new Error(errorMessage)
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
            const msg = evt.data.error || evt.data.message || 'An error occurred'
            setError(msg)
            setProgressError(msg)
            showError(msg)
            if (evt.data.stage) updateStage(evt.data.stage, 'error')
          } else if (evt.event === 'result') {
            onResult(evt.data)
            if (!options.execute || !options.read_only) {
              setGeneratedResult(evt.data)
            } else {
              setGeneratedResult(null)
            }
          }
        }
      }
    } catch (err) {
      if (err.name === 'AbortError') return // user cancelled
      const msg = err.message || 'Connection failed'
      setError(msg)
      setProgressError(msg)
      showError(msg)
    } finally {
      abortRef.current = null
      setLoading(false)
    }
  }

  const handleSubmit = async (e) => {
    e?.preventDefault()
    if (!question.trim()) return
    await runSSEQuery(question, { execute: executeQuery, read_only: readOnlyMode })
  }

  const handleExecuteGenerated = async () => {
    if (!generatedResult) return
    await runSSEQuery(question, { execute: true, read_only: readOnlyMode })
    setGeneratedResult(null)
  }

  // Selected DB chips
  const selectedDbs = databases.filter(db => selectedDbIds.includes(db.database_id))

  return (
    <div className="card">
      <div className="mb-4">
        <h2 className="text-xl font-semibold text-gray-900 mb-1">Ask a Question</h2>
        <p className="text-sm text-gray-600">Type your question in plain English — the AI converts it to SQL</p>
      </div>

      {/* Selected DB chips */}
      {selectedDbs.length > 0 ? (
        <div className="flex flex-wrap gap-2 mb-4">
          {selectedDbs.map(db => (
            <span
              key={db.database_id}
              className="flex items-center gap-1.5 px-2.5 py-1 bg-blue-100 text-blue-800 rounded-full text-xs font-medium"
            >
              <span>{getEmoji(db.db_type)}</span>
              <span>{db.nickname || db.database_id}</span>
              {!db.is_connected && <span className="text-red-500">(offline)</span>}
              <button
                onClick={() => onDatabaseSelectionChange && onDatabaseSelectionChange(db.database_id)}
                className="ml-0.5 text-blue-500 hover:text-blue-800"
              >
                ×
              </button>
            </span>
          ))}
        </div>
      ) : (
        <div className="mb-4 p-2 bg-amber-50 border border-amber-200 rounded-lg">
          <p className="text-xs text-amber-700">No database selected — click a database in the sidebar to target it.</p>
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-4">
        {/* Question Input */}
        <div>
          <label htmlFor="question" className="block text-sm font-medium text-gray-700 mb-2">
            Your Question
          </label>
          <textarea
            id="question"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder='e.g., "Show me all users who signed up in the last 7 days"'
            className="input-field resize-none h-24"
            disabled={loading}
          />
        </div>

        {/* Error Display */}
        {error && !showProgress && (
          <div className="p-3 bg-red-50 border border-red-200 rounded-lg flex items-start gap-2">
            <svg className="w-4 h-4 text-red-600 mt-0.5 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
            </svg>
            <p className="text-sm text-red-700">{error}</p>
          </div>
        )}

        {/* Query Settings */}
        <div className="bg-gradient-to-r from-blue-50 to-indigo-50 border border-blue-200 rounded-lg p-4 space-y-3">
          <h3 className="text-xs font-semibold text-gray-700 uppercase tracking-wide">Query Settings</h3>

          {/* Read-Only Toggle */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className={`w-2 h-2 rounded-full ${readOnlyMode ? 'bg-green-500' : 'bg-orange-500'}`} />
              <div>
                <span className="text-sm font-medium text-gray-900">{readOnlyMode ? 'Read-Only Mode' : 'Write Mode'}</span>
                <p className="text-xs text-gray-600">{readOnlyMode ? 'Only SELECT queries allowed' : 'UPDATE, DELETE, INSERT enabled'}</p>
              </div>
            </div>
            <button
              type="button"
              onClick={handleReadOnlyToggle}
              disabled={loading}
              className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                readOnlyMode ? 'bg-green-600' : 'bg-orange-500'
              } ${loading ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}
            >
              <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${readOnlyMode ? 'translate-x-6' : 'translate-x-1'}`} />
            </button>
          </div>

          <div className="border-t border-blue-200" />

          {/* Auto-Execute Toggle */}
          <div className="flex items-center justify-between">
            <div>
              <span className="text-sm font-medium text-gray-900">Auto-Execute</span>
              <p className="text-xs text-gray-600">{executeQuery ? 'Query runs automatically' : 'Review SQL before running'}</p>
            </div>
            <button
              type="button"
              onClick={() => {
                if (!readOnlyMode) return
                setExecuteQuery(!executeQuery)
                setGeneratedResult(null)
              }}
              disabled={loading || !readOnlyMode}
              className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                executeQuery ? 'bg-blue-600' : 'bg-gray-300'
              } ${loading || !readOnlyMode ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}
            >
              <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${executeQuery ? 'translate-x-6' : 'translate-x-1'}`} />
            </button>
          </div>

          {!readOnlyMode && (
            <div className="flex items-start gap-2 p-2 bg-orange-50 border border-orange-200 rounded">
              <svg className="w-4 h-4 text-orange-600 mt-0.5 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
              </svg>
              <p className="text-xs text-orange-800"><span className="font-semibold">Caution:</span> Auto-execute disabled in write mode. Review queries before execution.</p>
            </div>
          )}
        </div>

        {/* Submit / Cancel */}
        <div className="flex gap-3">
          <button
            type="submit"
            disabled={loading || !question.trim()}
            className={`flex-1 flex items-center justify-center gap-2 px-6 py-3 rounded-lg font-medium transition-colors ${
              readOnlyMode ? 'bg-blue-600 hover:bg-blue-700 text-white' : 'bg-orange-600 hover:bg-orange-700 text-white'
            } disabled:opacity-50 disabled:cursor-not-allowed`}
          >
            {loading ? (
              <>
                <svg className="animate-spin h-5 w-5" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
                <span>Processing...</span>
              </>
            ) : (
              <>
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                </svg>
                <span>
                  {executeQuery
                    ? (readOnlyMode ? 'Generate & Execute' : 'Generate & Execute (Write Mode)')
                    : 'Generate SQL Only'}
                </span>
              </>
            )}
          </button>

          {loading && (
            <button
              type="button"
              onClick={handleCancel}
              className="px-4 py-3 rounded-lg font-medium text-gray-700 bg-gray-200 hover:bg-gray-300 transition-colors"
            >
              Cancel
            </button>
          )}
        </div>
      </form>

      {/* Query Progress */}
      {showProgress && (loading || progressError || stages.some(s => s.status !== 'pending')) && (
        <div className="mt-4">
          <QueryProgress stages={stages} error={progressError} />
        </div>
      )}

      {/* Dangerous SQL Warning */}
      {!readOnlyMode && generatedResult?.generated_sql && (() => {
        const ops = detectDangerousSQL(generatedResult.generated_sql)
        if (!ops) return null
        const hasCritical = ops.some(op => op.severity === 'critical')
        return (
          <div className={`mt-4 p-4 rounded-lg border-2 ${hasCritical ? 'bg-red-50 border-red-500' : 'bg-orange-50 border-orange-500'}`}>
            <h4 className={`font-bold text-sm mb-2 ${hasCritical ? 'text-red-900' : 'text-orange-900'}`}>
              {hasCritical ? 'CRITICAL: Destructive Operation' : 'WARNING: Data Modification'}
            </h4>
            <div className="space-y-1">
              {ops.map((op, i) => (
                <div key={i} className={`text-sm flex items-center gap-2 ${op.severity === 'critical' ? 'text-red-800 font-semibold' : 'text-orange-800'}`}>
                  <span className={`px-2 py-0.5 rounded text-xs font-bold ${op.severity === 'critical' ? 'bg-red-200 text-red-900' : op.severity === 'high' ? 'bg-orange-200 text-orange-900' : 'bg-yellow-200 text-yellow-900'}`}>
                    {op.type}
                  </span>
                  {op.message}
                </div>
              ))}
            </div>
          </div>
        )
      })()}

      {/* Execute Button when auto-execute is off */}
      {!executeQuery && generatedResult && !loading && (
        <div className="mt-4">
          <button
            onClick={handleExecuteGenerated}
            className={`w-full py-3 font-medium rounded-lg transition-colors flex items-center justify-center gap-2 ${
              readOnlyMode ? 'bg-green-600 hover:bg-green-700 text-white' : 'bg-orange-600 hover:bg-orange-700 text-white border-2 border-orange-700'
            }`}
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <span>{readOnlyMode ? 'Execute Query' : 'I Understand — Execute Query'}</span>
          </button>
        </div>
      )}
    </div>
  )
}
