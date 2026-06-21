import { useState, useEffect } from 'react'
import axios from 'axios'
import { useToast } from '../hooks/useToast.jsx'
import { API_BASE } from '../config'

const HOW_TO_USE_STEPS = [
  { icon: 'chat', text: 'Type a question in plain English, e.g. "Show me top 10 customers by revenue".' },
  { icon: 'smart_toy', text: 'AI Mode generates SQL automatically. Toggle to Raw SQL to write queries yourself.' },
  { icon: 'table_view', text: 'Results appear below the query — export or copy the generated SQL as needed.' },
  { icon: 'history', text: 'Past queries are saved in the History tab for the current session.' },
]

const CLOUD_PROVIDERS = [
  {
    id: 'openai',
    label: 'OpenAI',
    color: '#E9D5FF',
    textColor: '#5b21b6',
    keyLink: 'https://platform.openai.com/api-keys',
    keyLinkLabel: 'platform.openai.com',
    models: ['gpt-4o', 'gpt-4o-mini', 'gpt-3.5-turbo'],
    placeholder: 'sk-...',
  },
  {
    id: 'google',
    label: 'Google',
    color: '#FDE68A',
    textColor: '#92400e',
    keyLink: 'https://aistudio.google.com/app/apikey',
    keyLinkLabel: 'aistudio.google.com',
    models: ['gemini-2.0-flash', 'gemini-1.5-flash', 'gemini-1.5-pro'],
    placeholder: 'AIza...',
  },
  {
    id: 'groq',
    label: 'Groq',
    color: '#D1FAE5',
    textColor: '#065f46',
    keyLink: 'https://console.groq.com/keys',
    keyLinkLabel: 'console.groq.com',
    models: ['llama-3.3-70b-versatile', 'llama-3.1-8b-instant', 'mixtral-8x7b-32768', 'gemma2-9b-it'],
    placeholder: 'gsk_...',
  },
]

export default function SettingsModal({
  onClose,
  onClearHistory,
  modelConfig = { provider: 'ollama', model: '', apiKey: '' },
  onModelConfigChange,
}) {
  const { showSuccess, showError } = useToast()
  const [clearingCache, setClearingCache] = useState(false)
  const [howToOpen, setHowToOpen] = useState(false)

  // Derive the current mode from modelConfig
  const currentMode = modelConfig.provider === 'ollama' ? 'local' : 'cloud'

  // Local AI provider state
  const [mode, setMode] = useState(currentMode)
  const [cloudProvider, setCloudProvider] = useState(
    CLOUD_PROVIDERS.find(p => p.id === modelConfig.provider) ? modelConfig.provider : 'openai'
  )
  const [cloudModel, setCloudModel] = useState(modelConfig.provider !== 'ollama' ? modelConfig.model : '')
  const [cloudKey, setCloudKey] = useState(modelConfig.provider !== 'ollama' ? modelConfig.apiKey : '')
  const [showKey, setShowKey] = useState(false)

  // Ollama detection
  const [ollamaModels, setOllamaModels] = useState([])
  const [ollamaLoading, setOllamaLoading] = useState(false)
  const [ollamaError, setOllamaError] = useState(null)
  const [ollamaModel, setOllamaModel] = useState(modelConfig.provider === 'ollama' ? modelConfig.model : '')
  const [ollamaUrl, setOllamaUrl] = useState(modelConfig.ollamaUrl || '')

  const fetchOllamaModels = () => {
    setOllamaLoading(true)
    setOllamaError(null)
    axios.get(`${API_BASE}/health/ollama`)
      .then(res => {
        const models = res.data.models || []
        setOllamaModels(models)
        if (models.length && !ollamaModel) setOllamaModel(models[0])
      })
      .catch(() => setOllamaError('Cannot reach Ollama. Is it running?'))
      .finally(() => setOllamaLoading(false))
  }

  useEffect(() => {
    if (mode === 'local') fetchOllamaModels()
  }, [mode])

  const handleApply = async () => {
    if (mode === 'local') {
      try {
        const res = await axios.post(`${API_BASE}/settings`, {
          provider: 'ollama',
          model: ollamaModel,
          ollama_url: ollamaUrl,
        })
        onModelConfigChange({
          provider: res.data.provider,
          model: res.data.model,
          apiKey: '',
          ollamaUrl: res.data.ollama_url || '',
        })
        showSuccess('Using local Ollama' + (res.data.model ? ` · ${res.data.model}` : ''))
      } catch (err) {
        showError(err.response?.data?.detail?.message || err.message || 'Failed to save settings')
      }
    } else {
      const meta = CLOUD_PROVIDERS.find(p => p.id === cloudProvider)
      if (!cloudKey.trim()) {
        showError('API key is required for cloud providers')
        return
      }
      if (!cloudModel) {
        showError('Please select a model')
        return
      }
      try {
        const res = await axios.post(`${API_BASE}/settings`, {
          provider: cloudProvider,
          model: cloudModel,
          ollama_url: '',
          api_key: cloudKey.trim(),
        })
        onModelConfigChange({
          provider: res.data.provider,
          model: res.data.model,
          apiKey: '',
          ollamaUrl: res.data.ollama_url || '',
        })
        showSuccess(`Using ${meta?.label} · ${res.data.model}`)
      } catch (err) {
        showError(err.response?.data?.detail?.message || err.message || 'Failed to save settings')
      }
    }
  }

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

  const selectedCloudMeta = CLOUD_PROVIDERS.find(p => p.id === cloudProvider)

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
          <button onClick={onClose} className="material-symbols-outlined p-1.5 hover:bg-[#e2e8f0] rounded-full transition-colors">
            close
          </button>
        </div>

        <div className="p-6 space-y-6 overflow-y-auto">

          {/* AI Provider */}
          <div className="space-y-3">
            <h3 className="font-heading font-black uppercase text-xs tracking-widest text-foreground/50">AI Provider</h3>

            {/* Local / Cloud API toggle */}
            <div className="flex gap-2 p-1 bg-[#f1f5f9] brutalist-border rounded-xl">
              {[
                { id: 'local', label: 'Local', icon: 'memory' },
                { id: 'cloud', label: 'Cloud API', icon: 'cloud' },
              ].map(opt => (
                <button
                  key={opt.id}
                  onClick={() => setMode(opt.id)}
                  className={`flex-1 flex items-center justify-center gap-2 py-2 px-3 rounded-lg text-xs font-heading font-bold uppercase tracking-tight transition-all cursor-pointer ${
                    mode === opt.id
                      ? 'bg-[#1a1c1d] text-white soft-shadow'
                      : 'text-foreground/50 hover:text-foreground'
                  }`}
                >
                  <span className="material-symbols-outlined text-sm">{opt.icon}</span>
                  {opt.label}
                </button>
              ))}
            </div>

            {/* Local — Ollama */}
            {mode === 'local' && (
              <div className="space-y-3">
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <span className="font-label text-xs text-foreground/50 uppercase tracking-wide">Detected models</span>
                    <button onClick={fetchOllamaModels} className="material-symbols-outlined text-sm text-foreground/40 hover:text-foreground transition-colors" title="Refresh">
                      refresh
                    </button>
                  </div>

                  {ollamaLoading && (
                    <div className="flex items-center gap-2 py-2 text-xs text-foreground/50">
                      <span className="material-symbols-outlined text-sm animate-spin">refresh</span>
                      Detecting models...
                    </div>
                  )}
                  {ollamaError && (
                    <div className="bg-danger/20 rounded-xl px-3 py-2 text-xs text-foreground/60">
                      {ollamaError} — or type a model name below
                    </div>
                  )}
                  {!ollamaLoading && !ollamaError && ollamaModels.length === 0 && (
                    <div className="bg-warning/20 rounded-xl px-3 py-2 text-xs text-foreground/60">
                      No models detected — type one below or run <code className="font-mono bg-white/60 px-1 rounded">ollama pull llama3.2</code>
                    </div>
                  )}
                  {!ollamaLoading && ollamaModels.length > 0 && (
                    <div className="flex flex-col gap-1 max-h-36 overflow-y-auto">
                      {ollamaModels.map(m => (
                        <button
                          key={m}
                          onClick={() => setOllamaModel(m)}
                          className={`flex items-center justify-between px-3 py-2 rounded-xl text-xs font-mono text-left transition-all cursor-pointer brutalist-border ${
                            ollamaModel === m
                              ? 'bg-success text-[#065f46] soft-shadow'
                              : 'border-transparent hover:border-border hover:bg-[#f1f5f9]'
                          }`}
                        >
                          <span className="truncate">{m}</span>
                          {ollamaModel === m && <span className="material-symbols-outlined text-sm shrink-0">check_circle</span>}
                        </button>
                      ))}
                    </div>
                  )}
                </div>

                <div className="space-y-1.5 pt-1 border-t-2 border-border">
                  <label className="font-label text-xs text-foreground/50 uppercase tracking-wide">Or enter model name</label>
                  <input
                    type="text"
                    value={ollamaModel}
                    onChange={e => setOllamaModel(e.target.value)}
                    placeholder="e.g. llama3.2, mistral, codellama"
                    className="w-full px-3 py-2 brutalist-border rounded-xl font-mono text-xs bg-white focus:outline-none focus:ring-2 focus:ring-foreground/20"
                  />
                </div>

                <div className="space-y-1.5 pt-1 border-t-2 border-border">
                  <label className="font-label text-xs text-foreground/50 uppercase tracking-wide">Ollama URL (optional)</label>
                  <input
                    type="text"
                    value={ollamaUrl}
                    onChange={e => setOllamaUrl(e.target.value)}
                    placeholder="http://localhost:11434"
                    className="w-full px-3 py-2 brutalist-border rounded-xl font-mono text-xs bg-white focus:outline-none focus:ring-2 focus:ring-foreground/20"
                  />
                  <p className="font-label text-[11px] text-foreground/40">Point at host Ollama with <code className="font-mono">http://host.docker.internal:11434</code></p>
                </div>
              </div>
            )}

            {/* Cloud API */}
            {mode === 'cloud' && (
              <div className="space-y-3">
                {/* Provider pills */}
                <div className="flex gap-1.5">
                  {CLOUD_PROVIDERS.map(p => (
                    <button
                      key={p.id}
                      onClick={() => { setCloudProvider(p.id); setCloudModel('') }}
                      className={`flex-1 py-2 px-2 rounded-xl text-xs font-heading font-bold uppercase tracking-tight transition-all cursor-pointer brutalist-border ${
                        cloudProvider === p.id ? 'soft-shadow' : 'border-transparent hover:border-border'
                      }`}
                      style={cloudProvider === p.id ? { background: p.color, color: p.textColor } : {}}
                    >
                      {p.label}
                    </button>
                  ))}
                </div>

                {/* API key creation link */}
                {selectedCloudMeta && (
                  <a
                    href={selectedCloudMeta.keyLink}
                    target="_blank"
                    rel="noreferrer"
                    className="flex items-center justify-between px-3 py-2 brutalist-border rounded-xl text-xs font-label hover:bg-[#f1f5f9] transition-colors group"
                  >
                    <span className="flex items-center gap-2 text-foreground/60">
                      <span className="material-symbols-outlined text-sm">key</span>
                      Get {selectedCloudMeta.label} API key
                    </span>
                    <span className="flex items-center gap-1 font-mono text-foreground/40 group-hover:text-foreground transition-colors">
                      {selectedCloudMeta.keyLinkLabel}
                      <span className="material-symbols-outlined text-sm">open_in_new</span>
                    </span>
                  </a>
                )}

                {/* API key input */}
                <div className="space-y-1.5">
                  <label className="font-label text-xs text-foreground/50 uppercase tracking-wide">API Key</label>
                  <div className="relative">
                    <input
                      type={showKey ? 'text' : 'password'}
                      value={cloudKey}
                      onChange={e => setCloudKey(e.target.value)}
                      placeholder={selectedCloudMeta?.placeholder || 'Paste API key...'}
                      className="w-full px-3 py-2 pr-9 brutalist-border rounded-xl font-mono text-xs bg-white focus:outline-none focus:ring-2 focus:ring-foreground/20"
                    />
                    <button
                      type="button"
                      onClick={() => setShowKey(v => !v)}
                      className="absolute right-2 top-1/2 -translate-y-1/2 material-symbols-outlined text-sm text-foreground/40 hover:text-foreground transition-colors"
                    >
                      {showKey ? 'visibility_off' : 'visibility'}
                    </button>
                  </div>
                </div>

                {/* Model selection */}
                <div className="space-y-1.5">
                  <label className="font-label text-xs text-foreground/50 uppercase tracking-wide">Model</label>
                  <div className="flex flex-col gap-1">
                    {selectedCloudMeta?.models.map(m => (
                      <button
                        key={m}
                        onClick={() => setCloudModel(m)}
                        className={`flex items-center justify-between px-3 py-2 rounded-xl text-xs font-mono text-left transition-all cursor-pointer brutalist-border ${
                          cloudModel === m
                            ? 'soft-shadow'
                            : 'border-transparent hover:border-border hover:bg-[#f1f5f9]'
                        }`}
                        style={cloudModel === m ? { background: selectedCloudMeta.color, color: selectedCloudMeta.textColor } : {}}
                      >
                        <span>{m}</span>
                        {cloudModel === m && <span className="material-symbols-outlined text-sm">check_circle</span>}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {/* Apply button */}
            <button
              onClick={handleApply}
              className="w-full px-4 py-2.5 bg-[#1a1c1d] text-white font-heading font-bold text-xs rounded-xl uppercase tracking-tight hover:bg-[#333] transition-colors cursor-pointer active-press brutalist-border soft-shadow"
            >
              Apply
            </button>

            {/* Current config indicator */}
            <div className="flex items-center gap-2 px-3 py-2 bg-[#f8fafc] rounded-xl border border-foreground/10">
              <span className="material-symbols-outlined text-sm text-foreground/40">
                {modelConfig.provider === 'ollama' ? 'memory' : 'cloud'}
              </span>
              <span className="font-mono text-xs text-foreground/50">
                {modelConfig.provider === 'ollama' ? 'Local' : modelConfig.provider.toUpperCase()}
                {' · '}
                {modelConfig.model || 'auto'}
              </span>
            </div>
          </div>

          {/* How to Use */}
          <div className="space-y-3">
            <h3 className="font-heading font-black uppercase text-xs tracking-widest text-foreground/50">Help</h3>
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
            <h3 className="font-heading font-black uppercase text-xs tracking-widest text-foreground/50">Links</h3>
            <div className="brutalist-border rounded-xl overflow-hidden divide-y divide-foreground/10">
              <a href="https://github.com/jmanoj0905/natural-language-sql" target="_blank" rel="noreferrer"
                className="flex items-center justify-between px-4 py-3 hover:bg-[#f1f5f9] active-press transition-colors group">
                <span className="flex items-center gap-2 font-label text-sm font-medium">
                  <span className="material-symbols-outlined text-base">code</span>
                  GitHub — natural-language-sql
                </span>
                <span className="material-symbols-outlined text-base text-foreground/40 group-hover:text-foreground transition-colors">open_in_new</span>
              </a>
              <a href="https://jmanoj.pages.dev" target="_blank" rel="noreferrer"
                className="flex items-center justify-between px-4 py-3 hover:bg-[#f1f5f9] active-press transition-colors group">
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
            <h3 className="font-heading font-black uppercase text-xs tracking-widest text-foreground/50">Actions</h3>
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
