import { useEffect, useState } from 'react'
import { Alert, AlertDescription } from '@/components/ui/alert'

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
      <svg className="w-4 h-4 text-foreground" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
      </svg>
    )
  }
  if (status === 'error') {
    return (
      <svg className="w-4 h-4 text-foreground" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M6 18L18 6M6 6l12 12" />
      </svg>
    )
  }
  if (status === 'skipped') {
    return (
      <svg className="w-3.5 h-3.5 text-foreground/40" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M20 12H4" />
      </svg>
    )
  }
  return <span className="text-xs font-heading">{index + 1}</span>
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

  useEffect(() => {
    if (!allDone || error) return
    const timer = setTimeout(() => setVisible(false), 5000)
    return () => clearTimeout(timer)
  }, [allDone, error])

  useEffect(() => {
    if (!allDone) setVisible(true)
  }, [allDone])

  if (!visible && !error) return null

  return (
    <div className={`transition-opacity duration-500 ${allDone && !error ? 'opacity-70' : 'opacity-100'}`}>
      <div className="bg-secondary-background border-2 border-border rounded-base shadow-shadow p-4">
        <div className="flex items-center justify-between">
          {stages.map((stage, i) => (
            <div key={stage.id} className="flex items-center flex-1">
              {/* Step circle + label */}
              <div className="flex flex-col items-center min-w-0">
                <div
                  className={`w-7 h-7 flex items-center justify-center transition-all duration-300 border-2 border-border rounded-base ${
                    stage.status === 'completed'
                      ? 'bg-success'
                      : stage.status === 'in_progress'
                        ? 'bg-main animate-pulse'
                        : stage.status === 'error'
                          ? 'bg-danger'
                          : stage.status === 'skipped'
                            ? 'bg-foreground/10'
                            : 'bg-secondary-background'
                  }`}
                >
                  <StageIcon status={stage.status} index={i} />
                </div>
                <span className={`text-xs mt-1 font-heading truncate max-w-[80px] text-center ${
                  stage.status === 'completed' || stage.status === 'in_progress'
                    ? 'text-foreground'
                    : stage.status === 'error'
                      ? 'text-danger'
                      : 'text-foreground/50'
                }`}>
                  {STAGE_CONFIG[i].label}
                </span>
                {stage.status === 'completed' && stage.duration_ms != null && (
                  <span className="text-[10px] text-foreground/40 font-mono">
                    {formatDuration(stage.duration_ms)}
                  </span>
                )}
                {stage.status === 'skipped' && (
                  <span className="text-[10px] text-foreground/40 font-heading">skipped</span>
                )}
                {stage.status === 'in_progress' && stage.message && (
                  <span className="text-[10px] text-foreground/60 truncate max-w-[100px] font-heading">
                    {stage.message}
                  </span>
                )}
              </div>

              {/* Connector line */}
              {i < stages.length - 1 && (
                <div className={`flex-1 h-[3px] mx-2 transition-colors duration-300 ${
                  stage.status === 'completed'
                    ? 'bg-success'
                    : 'bg-foreground/20'
                }`} />
              )}
            </div>
          ))}
        </div>

        {/* Error message */}
        {error && (
          <Alert className="bg-danger/20 mt-3 shadow-none">
            <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
            </svg>
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}
      </div>
    </div>
  )
}
