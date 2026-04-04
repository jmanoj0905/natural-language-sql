import { useState } from 'react'
import axios from 'axios'
import { useToast } from '../hooks/useToast'
import { extractApiErrorMessage } from '../utils/queryErrors'

export default function MultiStepPlan({
  question,
  onClose,
  onRunSingle,
  selectedDbIds = [],
}) {
  const { showError } = useToast()
  const [steps, setSteps] = useState([])
  const [loading, setLoading] = useState(false)
  const [planLoaded, setPlanLoaded] = useState(false)
  const [warning, setWarning] = useState(null)
  const [suggestions, setSuggestions] = useState([])
  const [error, setError] = useState(null)

  const generatePlan = async () => {
    setLoading(true)
    setError(null)

    try {
      const url = selectedDbIds.length > 0
        ? `/api/v1/query/plan?database_ids=${selectedDbIds.join(',')}`
        : '/api/v1/query/plan'

      const resp = await axios.post(url, { question })

      if (resp.data.success) {
        setSteps(resp.data.steps || [])
        setWarning(resp.data.warning || null)
        setSuggestions(resp.data.suggestions || [])
        setPlanLoaded(true)
      } else {
        setError(resp.data.message || 'Failed to analyze query')
      }
    } catch (err) {
      const msg = extractApiErrorMessage(err, 'Failed to analyze query')
      setError(msg)
      showError(msg)
    } finally {
      setLoading(false)
    }
  }

  const runSingleQuery = (stepQuestion) => {
    onRunSingle(stepQuestion)
    onClose()
  }

  return (
    <div className="brutalist-border bg-white rounded-2xl overflow-hidden soft-shadow">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 bg-warning/20 border-b-2 border-border">
        <div className="flex items-center gap-3">
          <span className="material-symbols-outlined text-warning text-2xl">info</span>
          <div>
            <h2 className="font-heading font-black text-xl uppercase">Query Analysis</h2>
            <p className="text-xs text-foreground/60 mt-1">We detected a compound query</p>
          </div>
        </div>
        <button
          onClick={onClose}
          className="p-2 hover:bg-white/50 rounded-full transition-colors"
        >
          <span className="material-symbols-outlined">close</span>
        </button>
      </div>

      {/* Question */}
      <div className="px-6 py-4 bg-background/50 border-b border-border">
        <p className="text-sm text-foreground/70">
          <span className="font-heading font-bold uppercase text-xs text-main mr-2">Your query:</span>
          {question}
        </p>
      </div>

      {/* Error */}
      {error && (
        <div className="mx-6 mt-4 flex items-center gap-2 px-4 py-3 bg-danger brutalist-border rounded-xl font-label text-sm">
          <span className="material-symbols-outlined text-base">error</span>
          {error}
        </div>
      )}

      {/* Plan Results */}
      {planLoaded && (
        <div className="p-6 space-y-4">
          {/* Warning */}
          {warning && (
            <div className="flex items-start gap-3 px-4 py-3 bg-warning/20 brutalist-border rounded-xl">
              <span className="material-symbols-outlined text-warning mt-0.5">warning</span>
              <p className="text-sm text-foreground/80">{warning}</p>
            </div>
          )}

          {/* Suggestions */}
          {suggestions.length > 0 && (
            <div className="space-y-2">
              <h3 className="font-heading font-bold text-sm uppercase text-foreground/70">
                Suggested Breakdown
              </h3>
              {suggestions.map((suggestion, idx) => (
                <p key={idx} className="text-sm text-foreground/60 pl-2">
                  {suggestion}
                </p>
              ))}
            </div>
          )}

          {/* Step List */}
          {steps.length > 0 && (
            <div className="space-y-2">
              <h3 className="font-heading font-bold text-sm uppercase text-foreground/70">
                Run individually:
              </h3>
              {steps.map((step, idx) => (
                <div 
                  key={idx} 
                  className="flex items-center justify-between px-4 py-3 bg-[#f8fafc] brutalist-border rounded-xl"
                >
                  <div className="flex items-center gap-3">
                    <span className="flex items-center justify-center w-6 h-6 bg-main/20 text-main rounded-full font-heading font-bold text-xs">
                      {step.step}
                    </span>
                    <span className="text-sm text-foreground">{step.question}</span>
                  </div>
                  <button
                    onClick={() => runSingleQuery(step.question)}
                    className="text-xs font-heading text-main hover:underline"
                  >
                    Run →
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Actions */}
      <div className="flex items-center gap-3 p-6 bg-background/50 border-t-2 border-border">
        {!planLoaded ? (
          <button
            onClick={generatePlan}
            disabled={loading}
            className="brutalist-border bg-warning px-6 py-2.5 rounded-xl font-heading font-bold text-sm soft-shadow active-press hover:bg-warning/80 transition-colors disabled:opacity-40"
          >
            {loading ? 'Analyzing...' : 'Analyze Query'}
          </button>
        ) : (
          <button
            onClick={generatePlan}
            disabled={loading}
            className="brutalist-border bg-white px-6 py-2.5 rounded-xl font-heading font-bold text-sm soft-shadow active-press hover:bg-[#f1f5f9] transition-colors disabled:opacity-40"
          >
            Re-analyze
          </button>
        )}
        <button
          onClick={onClose}
          className="brutalist-border bg-white px-6 py-2.5 rounded-xl font-heading font-bold text-sm soft-shadow active-press hover:bg-[#f1f5f9] transition-colors ml-auto"
        >
          Close
        </button>
      </div>
    </div>
  )
}