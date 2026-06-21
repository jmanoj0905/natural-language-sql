import { useEffect, useState, useRef } from 'react'
import axios from 'axios'
import { API_BASE } from '../config'

const POLL_INTERVAL_MS = 3000

/**
 * SetupGate — polls GET /api/v1/health/ollama every 3 s and blocks the main
 * UI while the local Ollama model is not yet available.
 *
 * Props:
 *   provider  — string, e.g. 'ollama' | 'openai' | 'anthropic'. Cloud
 *               providers bypass the gate entirely.
 *   children  — rendered once the model is ready (or bypassed).
 */
export default function SetupGate({ provider, children }) {
  const [ready, setReady] = useState(false)
  const [modelName, setModelName] = useState('')
  const intervalRef = useRef(null)

  const isCloud = provider && provider !== 'ollama'

  useEffect(() => {
    // Cloud provider: gate is irrelevant — render children immediately.
    if (isCloud) {
      setReady(true)
      return
    }

    const check = async () => {
      try {
        const res = await axios.get(`${API_BASE}/health/ollama`)
        const { status, model_available, configured_model } = res.data
        if (configured_model) setModelName(configured_model)
        if (status === 'healthy' && model_available) {
          setReady(true)
          clearInterval(intervalRef.current)
        }
      } catch {
        // Backend not yet up — keep polling.
      }
    }

    // Check immediately, then on interval.
    check()
    intervalRef.current = setInterval(check, POLL_INTERVAL_MS)

    return () => clearInterval(intervalRef.current)
  }, [isCloud])

  if (ready) return children

  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-6">
      <div className="bg-white border-2 border-border rounded-base soft-shadow max-w-md w-full p-8 text-center space-y-6">
        {/* Spinning indicator */}
        <div className="flex justify-center">
          <div
            className="w-12 h-12 border-4 border-border rounded-full animate-spin"
            style={{ borderTopColor: '#7d4e58' }}
            aria-label="Loading"
          />
        </div>

        <div className="space-y-2">
          <h2 className="font-heading font-black text-xl uppercase tracking-tight text-foreground">
            Setting up local model…
          </h2>
          <p className="font-mono text-sm text-foreground/70 leading-relaxed">
            First launch downloads a few GB — this can take several minutes.
            The app will open automatically when ready.
          </p>
          {modelName && (
            <p className="font-mono text-xs text-foreground/50 uppercase tracking-wide mt-1">
              Model: {modelName}
            </p>
          )}
        </div>

        <div className="flex items-center gap-2 bg-secondary-background border-2 border-border rounded-base px-4 py-2">
          <span className="material-symbols-outlined text-sm text-foreground/60">info</span>
          <p className="font-mono text-xs text-foreground/60 text-left leading-relaxed">
            Run <code className="bg-border px-1 rounded text-foreground">ollama pull {modelName || '&lt;model&gt;'}</code> in a terminal to track download progress.
          </p>
        </div>
      </div>
    </div>
  )
}
