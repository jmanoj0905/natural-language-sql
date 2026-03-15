import { useEffect, useState } from 'react'

const STAGE_CONFIG = [
  { id: 'connect', label: 'Connecting' },
  { id: 'schema', label: 'Reading Schema' },
  { id: 'ai', label: 'Generating SQL' },
  { id: 'validate', label: 'Validating' },
  { id: 'execute', label: 'Executing' },
]

function StageIcon({ status, index }) {
  if (status === 'completed') {
    return (
      <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
      </svg>
    )
  }
  if (status === 'error') {
    return (
      <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M6 18L18 6M6 6l12 12" />
      </svg>
    )
  }
  if (status === 'skipped') {
    return (
      <svg className="w-3.5 h-3.5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M20 12H4" />
      </svg>
    )
  }
  return <span className="text-xs font-bold">{index + 1}</span>
}

function formatDuration(ms) {
  if (ms == null) return ''
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(1)}s`
}

export default function QueryProgress({ stages, error }) {
  const [visible, setVisible] = useState(true)

  const allDone = stages.every(
    s => s.status === 'completed' || s.status === 'skipped'
  )

  // Auto-hide after success
  useEffect(() => {
    if (!allDone || error) return
    const timer = setTimeout(() => setVisible(false), 5000)
    return () => clearTimeout(timer)
  }, [allDone, error])

  // Reset visibility when stages change to non-complete
  useEffect(() => {
    if (!allDone) setVisible(true)
  }, [allDone])

  if (!visible && !error) return null

  return (
    <div className={`transition-opacity duration-500 ${allDone && !error ? 'opacity-70' : 'opacity-100'}`}>
      <div className="bg-white border border-gray-200 rounded-lg p-4">
        <div className="flex items-center justify-between">
          {stages.map((stage, i) => (
            <div key={stage.id} className="flex items-center flex-1">
              {/* Step circle + label */}
              <div className="flex flex-col items-center min-w-0">
                <div
                  className={`w-7 h-7 rounded-full flex items-center justify-center transition-all duration-300 ${
                    stage.status === 'completed'
                      ? 'bg-green-500 text-white'
                      : stage.status === 'in_progress'
                        ? 'bg-blue-500 text-white animate-pulse'
                        : stage.status === 'error'
                          ? 'bg-red-500 text-white'
                          : stage.status === 'skipped'
                            ? 'bg-gray-200 text-gray-400'
                            : 'bg-gray-200 text-gray-500'
                  }`}
                >
                  <StageIcon status={stage.status} index={i} />
                </div>
                <span className={`text-xs mt-1 font-medium truncate max-w-[80px] text-center ${
                  stage.status === 'completed'
                    ? 'text-green-700'
                    : stage.status === 'in_progress'
                      ? 'text-blue-700'
                      : stage.status === 'error'
                        ? 'text-red-700'
                        : 'text-gray-400'
                }`}>
                  {STAGE_CONFIG[i].label}
                </span>
                {stage.status === 'completed' && stage.duration_ms != null && (
                  <span className="text-[10px] text-gray-400 font-mono">
                    {formatDuration(stage.duration_ms)}
                  </span>
                )}
                {stage.status === 'skipped' && (
                  <span className="text-[10px] text-gray-400">skipped</span>
                )}
                {stage.status === 'in_progress' && stage.message && (
                  <span className="text-[10px] text-blue-500 truncate max-w-[100px]">
                    {stage.message}
                  </span>
                )}
              </div>

              {/* Connector line */}
              {i < stages.length - 1 && (
                <div className={`flex-1 h-0.5 mx-2 transition-colors duration-300 ${
                  stage.status === 'completed'
                    ? 'bg-green-300'
                    : 'bg-gray-200'
                }`} />
              )}
            </div>
          ))}
        </div>

        {/* Error message */}
        {error && (
          <div className="mt-3 p-2 bg-red-50 border border-red-200 rounded text-sm text-red-700">
            {error}
          </div>
        )}
      </div>
    </div>
  )
}
