import { useState } from 'react'
import axios from 'axios'
import { useToast } from '../hooks/useToast.jsx'
import { API_BASE } from '../config'

const HOW_TO_USE_STEPS = [
  { icon: 'cable', text: 'Connect a database from the sidebar — enter host, port, credentials, and click Save.' },
  { icon: 'chat', text: 'Type a question in plain English, e.g. "Show me top 10 customers by revenue".' },
  { icon: 'smart_toy', text: 'AI Mode generates SQL via Ollama locally. Toggle to Raw SQL to write queries yourself.' },
  { icon: 'table_view', text: 'Results appear below the query — export or copy the generated SQL as needed.' },
  { icon: 'history', text: 'Past queries are saved in the History tab for the current session.' },
]

export default function SettingsModal({ onClose, onClearHistory }) {
  const { showSuccess, showError } = useToast()
  const [clearingCache, setClearingCache] = useState(false)
  const [howToOpen, setHowToOpen] = useState(false)

  const handleClearCache = async () => {
    setClearingCache(true)
    try {
      await axios.post(`${API_BASE}/schema/cache/clear`)
      showSuccess('Schema cache cleared')
    } catch (err) {
      showError(err.response?.data?.detail?.message || err.message)
    } finally {
      setClearingCache(false)
    }
  }

  const handleClearHistory = () => {
    onClearHistory()
    showSuccess('Query history cleared')
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      style={{ background: 'rgba(26,28,29,0.6)' }}
      onClick={e => { if (e.target === e.currentTarget) onClose() }}
    >
      <div className="brutalist-border bg-white soft-shadow-lg rounded-2xl w-full max-w-md mx-4 overflow-hidden flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b-2 border-border bg-[#f1f5f9] shrink-0">
          <div className="flex items-center gap-3">
            <span className="material-symbols-outlined text-xl">settings</span>
            <h2 className="font-heading font-black text-xl uppercase tracking-tighter">Settings</h2>
          </div>
          <button
            onClick={onClose}
            className="material-symbols-outlined p-1.5 hover:bg-[#e2e8f0] rounded-full transition-colors"
          >
            close
          </button>
        </div>

        <div className="p-6 space-y-6 overflow-y-auto">
          {/* AI Engine */}
          <div className="space-y-3">
            <h3 className="font-heading font-black uppercase text-xs tracking-widest text-foreground/50">
              AI Engine
            </h3>
            <div className="brutalist-border rounded-xl overflow-hidden">
              <div className="divide-y divide-foreground/10">
                <Row label="Provider" value="Ollama (local)" />
                <Row label="Model" value={
                  <span className="font-mono text-xs">mannix/defog-llama3-sqlcoder-8b</span>
                } />
                <Row label="Endpoint" value={
                  <span className="font-mono text-xs">localhost:11434</span>
                } />
              </div>
            </div>
          </div>

          {/* How to Use */}
          <div className="space-y-3">
            <h3 className="font-heading font-black uppercase text-xs tracking-widest text-foreground/50">
              Help
            </h3>
            <button
              onClick={() => setHowToOpen(prev => !prev)}
              className="flex items-center justify-between w-full px-4 py-3 brutalist-border rounded-xl font-label text-sm font-medium hover:bg-[#f1f5f9] active-press transition-colors"
            >
              <span className="flex items-center gap-2">
                <span className="material-symbols-outlined text-base">help_outline</span>
                How to use
              </span>
              <span className="material-symbols-outlined text-base text-foreground/40 transition-transform" style={{ transform: howToOpen ? 'rotate(90deg)' : 'none' }}>
                chevron_right
              </span>
            </button>

            {howToOpen && (
              <div className="brutalist-border rounded-xl overflow-hidden divide-y divide-foreground/10">
                {HOW_TO_USE_STEPS.map((step, i) => (
                  <div key={i} className="flex items-start gap-3 px-4 py-3">
                    <span className="material-symbols-outlined text-base text-foreground/40 mt-0.5 shrink-0">{step.icon}</span>
                    <p className="font-label text-sm text-foreground leading-snug">{step.text}</p>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Links */}
          <div className="space-y-3">
            <h3 className="font-heading font-black uppercase text-xs tracking-widest text-foreground/50">
              Links
            </h3>
            <div className="brutalist-border rounded-xl overflow-hidden divide-y divide-foreground/10">
              <a
                href="https://github.com/jmanoj0905/natural-language-sql"
                target="_blank"
                rel="noreferrer"
                className="flex items-center justify-between px-4 py-3 hover:bg-[#f1f5f9] active-press transition-colors group"
              >
                <span className="flex items-center gap-2 font-label text-sm font-medium">
                  <span className="material-symbols-outlined text-base">code</span>
                  GitHub — natural-language-sql
                </span>
                <span className="material-symbols-outlined text-base text-foreground/40 group-hover:text-foreground transition-colors">open_in_new</span>
              </a>
              <a
                href="https://jmanoj.pages.dev"
                target="_blank"
                rel="noreferrer"
                className="flex items-center justify-between px-4 py-3 hover:bg-[#f1f5f9] active-press transition-colors group"
              >
                <span className="flex items-center gap-2 font-label text-sm font-medium">
                  <span className="material-symbols-outlined text-base">language</span>
                  jmanoj.pages.dev
                </span>
                <span className="material-symbols-outlined text-base text-foreground/40 group-hover:text-foreground transition-colors">open_in_new</span>
              </a>
            </div>
          </div>

          {/* Actions */}
          <div className="space-y-3">
            <h3 className="font-heading font-black uppercase text-xs tracking-widest text-foreground/50">
              Actions
            </h3>
            <div className="flex flex-col gap-2">
              <button
                onClick={handleClearCache}
                disabled={clearingCache}
                className="flex items-center justify-between w-full px-4 py-3 brutalist-border rounded-xl font-label text-sm font-medium hover:bg-[#f1f5f9] active-press transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <span className="flex items-center gap-2">
                  <span className="material-symbols-outlined text-base">database</span>
                  Clear schema cache
                </span>
                <span className={`material-symbols-outlined text-base text-foreground/40 ${clearingCache ? 'animate-spin' : ''}`}>
                  {clearingCache ? 'refresh' : 'chevron_right'}
                </span>
              </button>

              <button
                onClick={handleClearHistory}
                className="flex items-center justify-between w-full px-4 py-3 brutalist-border rounded-xl font-label text-sm font-medium hover:bg-[#f1f5f9] active-press transition-colors"
              >
                <span className="flex items-center gap-2">
                  <span className="material-symbols-outlined text-base">history</span>
                  Clear query history
                </span>
                <span className="material-symbols-outlined text-base text-foreground/40">chevron_right</span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

function Row({ label, value }) {
  return (
    <div className="flex items-center justify-between px-4 py-3 gap-4">
      <span className="font-label text-xs font-medium uppercase tracking-wide text-foreground/50 shrink-0">{label}</span>
      <span className="font-label text-sm text-foreground text-right">{value}</span>
    </div>
  )
}
