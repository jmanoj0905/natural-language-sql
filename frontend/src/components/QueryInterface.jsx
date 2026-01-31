import { useState, useEffect, useRef } from 'react'
import axios from 'axios'

const API_BASE = '/api/v1'

export default function QueryInterface({
  onSubmit,
  databases = [],
  selectedDatabases = [],
  onDatabaseSelectionChange
}) {
  const [question, setQuestion] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [readOnlyMode, setReadOnlyMode] = useState(true)
  const [executeQuery, setExecuteQuery] = useState(true)
  const [generatedResult, setGeneratedResult] = useState(null)
  const [lastWriteOperation, setLastWriteOperation] = useState(null)
  const [rollbackTimeLeft, setRollbackTimeLeft] = useState(0)
  const rollbackTimerRef = useRef(null)

  // Countdown timer for rollback window
  useEffect(() => {
    if (rollbackTimeLeft > 0) {
      rollbackTimerRef.current = setTimeout(() => {
        setRollbackTimeLeft(rollbackTimeLeft - 1)
      }, 1000)
    } else if (rollbackTimeLeft === 0 && lastWriteOperation) {
      // Time expired, clear the write operation
      setLastWriteOperation(null)
    }

    return () => {
      if (rollbackTimerRef.current) {
        clearTimeout(rollbackTimerRef.current)
      }
    }
  }, [rollbackTimeLeft, lastWriteOperation])

  // Detect dangerous SQL operations
  const detectDangerousSQL = (sql) => {
    if (!sql) return null

    const upperSQL = sql.toUpperCase()
    const operations = []

    if (upperSQL.includes('DELETE FROM') || upperSQL.includes('DELETE ')) {
      operations.push({ type: 'DELETE', severity: 'high', message: 'Will DELETE rows from table(s)' })
    }
    if (upperSQL.includes('UPDATE ') && upperSQL.includes(' SET ')) {
      operations.push({ type: 'UPDATE', severity: 'high', message: 'Will UPDATE existing rows' })
    }
    if (upperSQL.includes('DROP TABLE') || upperSQL.includes('DROP DATABASE')) {
      operations.push({ type: 'DROP', severity: 'critical', message: 'Will DROP table(s) or database - PERMANENT' })
    }
    if (upperSQL.includes('TRUNCATE')) {
      operations.push({ type: 'TRUNCATE', severity: 'critical', message: 'Will TRUNCATE table - all data will be deleted' })
    }
    if (upperSQL.includes('INSERT INTO')) {
      operations.push({ type: 'INSERT', severity: 'medium', message: 'Will INSERT new rows' })
    }
    if (upperSQL.includes('ALTER TABLE')) {
      operations.push({ type: 'ALTER', severity: 'high', message: 'Will ALTER table structure' })
    }

    return operations.length > 0 ? operations : null
  }

  // Check if SQL is a write operation
  const isWriteOperation = (sql) => {
    if (!sql) return false
    const upperSQL = sql.toUpperCase()
    return upperSQL.includes('UPDATE ') ||
           upperSQL.includes('DELETE ') ||
           upperSQL.includes('INSERT ')
  }

  // When switching to write mode, disable auto-execute for safety
  const handleReadOnlyToggle = () => {
    const newReadOnlyMode = !readOnlyMode
    setReadOnlyMode(newReadOnlyMode)

    // If enabling write mode, turn off auto-execute for safety
    if (!newReadOnlyMode) {
      setExecuteQuery(false)
    }
  }

  const handleSubmit = async (e, forceExecute = false) => {
    e?.preventDefault()
    if (!question.trim()) return

    setLoading(true)
    setError(null)

    try {
      const result = await onSubmit(question, {
        execute: forceExecute || executeQuery,
        include_schema_context: true,  // Always include schema context
        read_only: readOnlyMode  // Pass read-only mode to backend
      })

      // If not auto-executing, store the result to show execute button
      if (!executeQuery && !forceExecute) {
        setGeneratedResult(result)
      } else {
        // If auto-executed in write mode, still store result to show warnings
        if (!readOnlyMode && (forceExecute || executeQuery)) {
          setGeneratedResult(result)
        } else {
          setGeneratedResult(null)
        }
      }
    } catch (err) {
      setError(err.response?.data?.detail?.message || err.message || 'Query failed')
    } finally {
      setLoading(false)
    }
  }

  const handleExecuteGenerated = async () => {
    if (!generatedResult) return

    setLoading(true)
    setError(null)

    try {
      const result = await onSubmit(question, {
        execute: true,
        include_schema_context: true,
        read_only: readOnlyMode  // Pass read-only mode to backend
      })

      // If write operation in write mode, enable rollback
      if (!readOnlyMode && isWriteOperation(generatedResult.generated_sql)) {
        setLastWriteOperation({
          sql: generatedResult.generated_sql,
          question: question,
          result: result,
          timestamp: Date.now()
        })
        setRollbackTimeLeft(30) // 30 second rollback window
      }

      setGeneratedResult(null)
    } catch (err) {
      setError(err.response?.data?.detail?.message || err.message || 'Query failed')
    } finally {
      setLoading(false)
    }
  }

  // Handle rollback
  const handleRollback = async () => {
    if (!lastWriteOperation) return

    const confirmRollback = confirm(
      'Are you sure you want to rollback the last operation?\n\n' +
      'This will attempt to undo the changes made by:\n' +
      lastWriteOperation.question
    )

    if (!confirmRollback) return

    setLoading(true)
    setError(null)

    try {
      // Send rollback request to backend
      await axios.post(`${API_BASE}/query/rollback`, {
        original_sql: lastWriteOperation.sql,
        question: lastWriteOperation.question
      })

      // Clear the write operation
      setLastWriteOperation(null)
      setRollbackTimeLeft(0)

      // Show success message
      alert('Operation successfully rolled back!')
    } catch (err) {
      setError(err.response?.data?.detail?.message || 'Rollback failed. Changes may be permanent.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="card">
      <div className="mb-4">
        <h2 className="text-xl font-semibold text-gray-900 mb-2">
          Ask a Question
        </h2>
        <p className="text-sm text-gray-600">
          Type your question in plain English and we'll convert it to SQL
        </p>
      </div>

      {/* Database Selection */}
      {databases.length > 0 && (
        <div className="mb-4 p-3 bg-blue-50 rounded-lg">
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Select Database to Query:
          </label>
          <div className="flex flex-wrap gap-2">
            {databases.map(db => (
              <label
                key={db.database_id}
                className={`flex items-center gap-2 px-3 py-2 rounded border cursor-pointer transition-colors ${
                  selectedDatabases.includes(db.database_id)
                    ? 'bg-blue-600 text-white border-blue-600'
                    : 'bg-white border-gray-300 hover:border-blue-400'
                }`}
              >
                <input
                  type="checkbox"
                  checked={selectedDatabases.includes(db.database_id)}
                  onChange={() => onDatabaseSelectionChange && onDatabaseSelectionChange(db.database_id)}
                  className="hidden"
                />
                <span className="text-sm">
                  {db.database}
                  {db.nickname && db.nickname !== db.database && (
                    <span className="text-xs opacity-75"> ({db.nickname})</span>
                  )}
                  {!db.is_connected && (
                    <span className={selectedDatabases.includes(db.database_id) ? 'text-red-200' : 'text-red-500'}>
                      {' '}(disconnected)
                    </span>
                  )}
                </span>
              </label>
            ))}
          </div>
          {selectedDatabases.length === 0 && (
            <p className="text-xs text-gray-600 mt-2">
              No database selected. Will use default database.
            </p>
          )}
          {selectedDatabases.length > 1 && (
            <p className="text-xs text-orange-600 mt-2">
              Multiple databases selected. Only the first will be queried.
            </p>
          )}
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
            placeholder="e.g., Show me all users who signed up in the last 7 days"
            className="input-field resize-none h-24"
            disabled={loading}
          />
        </div>

        {/* Error Display */}
        {error && (
          <div className="p-4 bg-red-50 border border-red-200 rounded-lg">
            <div className="flex items-start gap-3">
              <svg className="w-5 h-5 text-red-600 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
              </svg>
              <div>
                <h3 className="text-sm font-medium text-red-800">Error</h3>
                <p className="text-sm text-red-700 mt-1">{error}</p>
              </div>
            </div>
          </div>
        )}

        {/* Query Settings Panel */}
        <div className="bg-gradient-to-r from-blue-50 to-indigo-50 border border-blue-200 rounded-lg p-4">
          <h3 className="text-xs font-semibold text-gray-700 uppercase tracking-wide mb-3">Query Settings</h3>

          <div className="space-y-3">
            {/* Read-Only Mode Toggle */}
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className={`w-2 h-2 rounded-full ${readOnlyMode ? 'bg-green-500' : 'bg-orange-500'}`} />
                <div>
                  <span className="text-sm font-medium text-gray-900">
                    {readOnlyMode ? 'Read-Only Mode' : 'Write Mode'}
                  </span>
                  <p className="text-xs text-gray-600">
                    {readOnlyMode
                      ? 'Only SELECT queries allowed'
                      : 'UPDATE, DELETE, INSERT enabled'}
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={handleReadOnlyToggle}
                disabled={loading}
                title={readOnlyMode
                  ? 'Switch to Write Mode (allows UPDATE, DELETE, INSERT queries)'
                  : 'Switch to Read-Only Mode (only SELECT queries)'
                }
                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 ${
                  readOnlyMode ? 'bg-green-600' : 'bg-orange-500'
                } ${loading ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}
              >
                <span
                  className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                    readOnlyMode ? 'translate-x-6' : 'translate-x-1'
                  }`}
                />
              </button>
            </div>

            {/* Divider */}
            <div className="border-t border-blue-200" />

            {/* Auto-Execute Toggle */}
            <div className="flex items-center justify-between">
              <div>
                <span className="text-sm font-medium text-gray-900">Auto-Execute</span>
                <p className="text-xs text-gray-600">
                  {executeQuery
                    ? 'Query runs automatically'
                    : 'Review SQL before running'}
                </p>
              </div>
              <button
                type="button"
                onClick={() => {
                  // In write mode, auto-execute is locked off for safety
                  if (!readOnlyMode) return
                  setExecuteQuery(!executeQuery)
                  setGeneratedResult(null)
                }}
                disabled={loading || !readOnlyMode}
                title={!readOnlyMode
                  ? 'Auto-execute is disabled in Write Mode for safety'
                  : executeQuery
                    ? 'Turn off auto-execute to review SQL before running'
                    : 'Turn on auto-execute to run queries immediately'
                }
                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 ${
                  executeQuery ? 'bg-blue-600' : 'bg-gray-300'
                } ${loading || !readOnlyMode ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}
              >
                <span
                  className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                    executeQuery ? 'translate-x-6' : 'translate-x-1'
                  }`}
                />
              </button>
            </div>

            {/* Warning when in write mode */}
            {!readOnlyMode && (
              <div className="flex items-start gap-2 p-2 bg-orange-50 border border-orange-200 rounded">
                <svg className="w-4 h-4 text-orange-600 mt-0.5 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                </svg>
                <p className="text-xs text-orange-800">
                  <span className="font-semibold">Caution:</span> Auto-execute is disabled in write mode. Always review queries before execution.
                </p>
              </div>
            )}
          </div>
        </div>

        {/* Submit Button */}
        <button
          type="submit"
          disabled={loading || !question.trim()}
          title={executeQuery
            ? `Generate SQL and execute immediately (${readOnlyMode ? 'read-only' : 'write mode'})`
            : 'Generate SQL and review before executing'
          }
          className={`w-full flex items-center justify-center gap-2 px-6 py-3 rounded-lg font-medium transition-colors ${
            readOnlyMode
              ? 'bg-blue-600 hover:bg-blue-700 text-white'
              : 'bg-orange-600 hover:bg-orange-700 text-white'
          } disabled:opacity-50 disabled:cursor-not-allowed`}
        >
          {loading ? (
            <>
              <svg className="animate-spin h-5 w-5" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
              <span>Processing...</span>
            </>
          ) : (
            <>
              {!readOnlyMode && executeQuery ? (
                <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                </svg>
              ) : (
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                </svg>
              )}
              <span>
                {executeQuery
                  ? (readOnlyMode ? 'Generate & Execute Query' : 'Generate & Execute (Write Mode)')
                  : 'Generate SQL Only'}
              </span>
            </>
          )}
        </button>
      </form>

      {/* Dangerous SQL Warning - Shows in write mode */}
      {!readOnlyMode && generatedResult && generatedResult.generated_sql && (
        <div className="mt-4">
          {(() => {
            const dangerousOps = detectDangerousSQL(generatedResult.generated_sql)
            if (!dangerousOps) return null

            const criticalOps = dangerousOps.filter(op => op.severity === 'critical')
            const highOps = dangerousOps.filter(op => op.severity === 'high')
            const hasCritical = criticalOps.length > 0

            return (
              <div className={`p-4 rounded-lg border-2 ${
                hasCritical
                  ? 'bg-red-50 border-red-500'
                  : 'bg-orange-50 border-orange-500'
              }`}>
                <div className="flex items-start gap-3">
                  <svg className={`w-6 h-6 flex-shrink-0 mt-0.5 ${
                    hasCritical ? 'text-red-600' : 'text-orange-600'
                  }`} fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                  </svg>
                  <div className="flex-1">
                    <h4 className={`font-bold text-sm ${
                      hasCritical ? 'text-red-900' : 'text-orange-900'
                    }`}>
                      {hasCritical ? '⚠️ CRITICAL WARNING: Destructive Operation Detected' : '⚠️ WARNING: Data Modification Detected'}
                    </h4>
                    <div className="mt-2 space-y-1">
                      {dangerousOps.map((op, idx) => (
                        <div key={idx} className={`text-sm flex items-center gap-2 ${
                          op.severity === 'critical' ? 'text-red-800 font-semibold' :
                          op.severity === 'high' ? 'text-orange-800 font-medium' :
                          'text-orange-700'
                        }`}>
                          <span className={`px-2 py-0.5 rounded text-xs font-bold ${
                            op.severity === 'critical' ? 'bg-red-200 text-red-900' :
                            op.severity === 'high' ? 'bg-orange-200 text-orange-900' :
                            'bg-yellow-200 text-yellow-900'
                          }`}>
                            {op.type}
                          </span>
                          {op.message}
                        </div>
                      ))}
                    </div>
                    <p className={`mt-3 text-xs ${
                      hasCritical ? 'text-red-800' : 'text-orange-800'
                    }`}>
                      <span className="font-bold">REVIEW CAREFULLY:</span> This query will modify or delete data.
                      {hasCritical && ' This operation is PERMANENT and CANNOT be undone.'}
                    </p>
                  </div>
                </div>
              </div>
            )
          })()}
        </div>
      )}

      {/* Execute Button - Shows when auto-execute is off and SQL is generated */}
      {!executeQuery && generatedResult && !loading && (
        <div className="mt-4">
          <button
            onClick={handleExecuteGenerated}
            title={readOnlyMode
              ? 'Execute the generated SQL query (read-only)'
              : 'Execute the generated SQL query (CAUTION: Write operations enabled)'
            }
            className={`w-full py-3 font-medium rounded-lg transition-colors flex items-center justify-center gap-2 ${
              readOnlyMode
                ? 'bg-green-600 hover:bg-green-700 text-white'
                : 'bg-orange-600 hover:bg-orange-700 text-white border-2 border-orange-700'
            }`}
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <span>{readOnlyMode ? 'Execute Query' : 'I Understand - Execute Query'}</span>
          </button>
        </div>
      )}

      {/* Rollback Panel - Shows after write operations */}
      {lastWriteOperation && rollbackTimeLeft > 0 && (
        <div className="mt-4 bg-gradient-to-r from-yellow-50 to-orange-50 border-2 border-orange-400 rounded-lg p-4 shadow-lg">
          <div className="flex items-start gap-3">
            <div className="flex-shrink-0">
              <svg className="w-6 h-6 text-orange-600" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm1-12a1 1 0 10-2 0v4a1 1 0 00.293.707l2.828 2.829a1 1 0 101.415-1.415L11 9.586V6z" clipRule="evenodd" />
              </svg>
            </div>
            <div className="flex-1">
              <div className="flex items-center justify-between mb-2">
                <h4 className="font-bold text-orange-900">
                  🔄 Rollback Available
                </h4>
                <div className="flex items-center gap-2">
                  <div className="flex items-center gap-1 text-sm font-medium text-orange-800">
                    <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm1-12a1 1 0 10-2 0v4a1 1 0 00.293.707l2.828 2.829a1 1 0 101.415-1.415L11 9.586V6z" clipRule="evenodd" />
                    </svg>
                    <span>{rollbackTimeLeft}s</span>
                  </div>
                </div>
              </div>

              <p className="text-sm text-orange-800 mb-3">
                Your last operation has been executed. You can undo it within the next {rollbackTimeLeft} seconds.
              </p>

              <div className="bg-white bg-opacity-50 rounded p-2 mb-3">
                <p className="text-xs font-medium text-orange-900 mb-1">Last Operation:</p>
                <p className="text-xs text-orange-800 italic">"{lastWriteOperation.question}"</p>
              </div>

              <div className="flex gap-2">
                <button
                  onClick={handleRollback}
                  disabled={loading}
                  className="flex-1 px-4 py-2 bg-orange-600 hover:bg-orange-700 text-white font-medium rounded-lg transition-colors flex items-center justify-center gap-2 disabled:opacity-50"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 10h10a8 8 0 018 8v2M3 10l6 6m-6-6l6-6" />
                  </svg>
                  Undo Changes
                </button>
                <button
                  onClick={() => {
                    setLastWriteOperation(null)
                    setRollbackTimeLeft(0)
                  }}
                  className="px-4 py-2 bg-gray-200 hover:bg-gray-300 text-gray-700 font-medium rounded-lg transition-colors"
                >
                  Keep Changes
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
