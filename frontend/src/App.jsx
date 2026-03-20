import { useState, useEffect } from 'react'
import axios from 'axios'
import AppSidebar from './components/AppSidebar'
import QueryInterface from './components/QueryInterface'
import ResultsDisplay from './components/ResultsDisplay'
import QueryHistory from './components/QueryHistory'
import DatabaseStatus from './components/DatabaseStatus'
import SettingsModal from './components/SettingsModal'
import { useToast } from './hooks/useToast.jsx'
import { API_BASE } from './config'

function App() {
  useToast()
  const [databases, setDatabases] = useState([])
  const [selectedDbIds, setSelectedDbIds] = useState([])
  const [queryHistory, setQueryHistory] = useState([])
  const [currentResult, setCurrentResult] = useState(null)
  const [activeTab, setActiveTab] = useState('query')
  const [aiMode, setAiMode] = useState(true)
  const [settingsOpen, setSettingsOpen] = useState(false)

  useEffect(() => {
    loadDatabases()
    const interval = setInterval(loadDatabases, 30000)
    return () => clearInterval(interval)
  }, [])

  const loadDatabases = async () => {
    try {
      const resp = await axios.get(`${API_BASE}/databases`)
      setDatabases(resp.data.databases)
    } catch (err) {
      console.error('Failed to load databases:', err)
    }
  }

  const handleSelectionChange = (dbId) => {
    setSelectedDbIds(prev =>
      prev.includes(dbId) ? prev.filter(id => id !== dbId) : [...prev, dbId]
    )
  }

  const handleQueryResult = (result) => {
    setCurrentResult(result)
    setQueryHistory(prev => [{
      id: Date.now(),
      question: result.question,
      sql: result.generated_sql,
      explanation: result.sql_explanation,
      rowCount: result.execution_result?.row_count || 0,
      executionTime: result.execution_result?.execution_time_ms || 0,
      timestamp: new Date().toLocaleString(),
      databaseId: result.metadata?.multi_db
        ? result.metadata.database_ids
        : result.metadata?.database_id,
    }, ...prev].slice(0, 20))
  }

  const navLinkClass = (tab) =>
    `font-heading font-bold uppercase tracking-tight transition-colors cursor-pointer ${
      activeTab === tab
        ? 'text-[#7d4e58] border-b-2 border-[#7d4e58] pb-1'
        : 'text-foreground hover:bg-[#e2e8f0] px-3 py-1 rounded-full active:translate-x-[1px] active:translate-y-[1px]'
    }`

  return (
    <div className="bg-background text-foreground min-h-screen">
      {/* Top Nav Bar */}
      <header className="flex justify-between items-center w-full px-6 h-16 sticky top-0 z-50 bg-white border-b-2 border-border">
        <div className="flex items-center gap-8">
          <span className="text-2xl font-black text-foreground uppercase font-heading tracking-tight">NLSQL</span>
          <nav className="hidden md:flex gap-6 items-center">
            <button className={navLinkClass('query')} onClick={() => setActiveTab('query')}>Query</button>
            <button className={navLinkClass('history')} onClick={() => setActiveTab('history')}>History</button>
          </nav>
        </div>
        <div className="flex items-center gap-3">
          {/* AI / Raw SQL mode toggle */}
          <button
            onClick={() => setAiMode(prev => !prev)}
            className={`flex items-center gap-2 px-4 py-1.5 font-mono text-xs brutalist-border font-bold rounded-full uppercase transition-all active-press cursor-pointer select-none ${
              aiMode
                ? 'bg-success text-[#065f46] soft-shadow'
                : 'bg-[#1a1c1d] text-success soft-shadow'
            }`}
          >
            <span className={`material-symbols-outlined text-sm ${!aiMode ? 'text-success' : ''}`}>
              {aiMode ? 'smart_toy' : 'code'}
            </span>
            {aiMode ? 'AI Mode' : 'Raw SQL'}
          </button>

          <DatabaseStatus databases={databases} />
          <button
            onClick={loadDatabases}
            className="material-symbols-outlined p-2 text-foreground hover:bg-[#e2e8f0] transition-colors rounded-full active:translate-x-[1px] active:translate-y-[1px]"
            title="Reload"
          >
            refresh
          </button>
          <button
            onClick={() => setSettingsOpen(true)}
            className="material-symbols-outlined p-2 text-foreground hover:bg-[#e2e8f0] transition-colors rounded-full active:translate-x-[1px] active:translate-y-[1px]"
            title="Settings"
          >
            settings
          </button>
        </div>
      </header>

      <div className="flex">
        {/* Sidebar */}
        <AppSidebar
          databases={databases}
          selectedDbIds={selectedDbIds}
          onSelectionChange={handleSelectionChange}
          onDatabasesChanged={loadDatabases}
        />

        {/* Main Content */}
        <main className="ml-64 w-full min-h-[calc(100vh-64px)] p-8 hatch-pattern">
          <div className="max-w-6xl mx-auto space-y-8">
            {activeTab === 'query' && (
              <>
                <QueryInterface
                  onResult={handleQueryResult}
                  databases={databases}
                  selectedDbIds={selectedDbIds}
                  onDatabaseSelectionChange={handleSelectionChange}
                  aiMode={aiMode}
                />
                {currentResult && <ResultsDisplay result={currentResult} />}
              </>
            )}
            {activeTab === 'history' && (
              <QueryHistory history={queryHistory} />
            )}

            <footer className="flex justify-between items-center font-mono text-[10px] uppercase opacity-50 pb-12 text-foreground">
              <div>ENGINE: OLLAMA | MODE: LOCAL_AI</div>
              <div>&copy; {new Date().getFullYear()} NLSQL SYSTEM</div>
            </footer>
          </div>
        </main>
      </div>

      {settingsOpen && (
        <SettingsModal
          onClose={() => setSettingsOpen(false)}
          onClearHistory={() => setQueryHistory([])}
        />
      )}
    </div>
  )
}

export default App
