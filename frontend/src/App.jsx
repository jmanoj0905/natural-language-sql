import { useState, useEffect } from 'react'
import axios from 'axios'
import AppSidebar from './components/AppSidebar'
import QueryInterface from './components/QueryInterface'
import ResultsDisplay from './components/ResultsDisplay'
import QueryHistory from './components/QueryHistory'
import DatabaseStatus from './components/DatabaseStatus'
import { useToast } from './hooks/useToast.jsx'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '@/components/ui/dialog'

const API_BASE = '/api/v1'

function App() {
  const { showError } = useToast()
  const [databases, setDatabases] = useState([])
  const [selectedDbIds, setSelectedDbIds] = useState([])
  const [queryHistory, setQueryHistory] = useState([])
  const [currentResult, setCurrentResult] = useState(null)
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [showHistory, setShowHistory] = useState(false)
  const [howToUseOpen, setHowToUseOpen] = useState(false)
  const [dbHealth, setDbHealth] = useState(null)

  useEffect(() => {
    loadDatabases()
    const interval = setInterval(loadDatabases, 30000)
    return () => clearInterval(interval)
  }, [])

  useEffect(() => {
    checkDatabaseHealth()
    const interval = setInterval(checkDatabaseHealth, 30000)
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

  const checkDatabaseHealth = async () => {
    try {
      const resp = await axios.get(`${API_BASE}/health/database`)
      setDbHealth(resp.data)
    } catch {
      setDbHealth({ database_configured: false, database_connected: false })
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

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      {/* Sidebar */}
      <AppSidebar
        databases={databases}
        selectedDbIds={selectedDbIds}
        onSelectionChange={handleSelectionChange}
        onDatabasesChanged={() => { loadDatabases(); checkDatabaseHealth() }}
        collapsed={!sidebarOpen}
        onToggleCollapse={() => setSidebarOpen(prev => !prev)}
      />

      {/* Main area */}
      <div className="flex flex-col flex-1 min-w-0 overflow-hidden">
        {/* Header */}
        <header className="bg-main border-b-2 border-border px-6 py-3 flex items-center justify-between shrink-0">
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-heading uppercase tracking-tight">NLSQL</h1>
          </div>
          <div className="flex items-center gap-3">
            <Button
              variant="neutral"
              size="sm"
              onClick={() => setShowHistory(prev => !prev)}
              className={showHistory ? 'bg-info/30' : ''}
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              History
            </Button>

            <Button
              variant="neutral"
              size="sm"
              onClick={() => setHowToUseOpen(true)}
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              Help
            </Button>

            <DatabaseStatus
              health={dbHealth}
              databases={databases}
              onRefresh={() => { checkDatabaseHealth(); loadDatabases() }}
            />
          </div>
        </header>

        {/* Content area */}
        <div className="flex flex-1 overflow-hidden">
          {/* Query + Results column */}
          <div className="flex-1 overflow-y-auto p-6 space-y-6 min-w-0">
            <QueryInterface
              onResult={handleQueryResult}
              databases={databases}
              selectedDbIds={selectedDbIds}
              onDatabaseSelectionChange={handleSelectionChange}
            />
            {currentResult && <ResultsDisplay result={currentResult} />}
          </div>

          {/* History panel */}
          {showHistory && (
            <div className="w-80 shrink-0 border-l-2 border-border bg-background overflow-y-auto p-4">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-sm uppercase tracking-wide">Query History</h2>
                <button
                  onClick={() => setShowHistory(false)}
                  className="text-foreground hover:text-danger"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
              <QueryHistory history={queryHistory} />
            </div>
          )}
        </div>
      </div>

      {/* How to Use Modal */}
      <Dialog open={howToUseOpen} onOpenChange={setHowToUseOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle className="text-2xl">HOW TO USE</DialogTitle>
            <DialogDescription>Get started in 4 simple steps</DialogDescription>
          </DialogHeader>
          <div className="space-y-5">
            {[
              { n: 1, title: 'Add a Database', text: 'Click "+ Add Connection" in the sidebar and enter your PostgreSQL or MySQL credentials.' },
              { n: 2, title: 'Select a Database', text: 'Click a database in the sidebar to select it for querying. The selected one highlights in yellow.' },
              { n: 3, title: 'Ask in Plain English', text: 'Type your question naturally — e.g. "Show me all users who signed up in the last 7 days".' },
              { n: 4, title: 'Review & Execute', text: 'The AI generates SQL and executes it automatically. Toggle Write Mode to run INSERT/UPDATE/DELETE.' },
            ].map(({ n, title, text }) => (
              <div key={n} className="flex gap-4">
                <div className="shrink-0 w-8 h-8 bg-sidebar border-2 border-border flex items-center justify-center font-heading text-sm text-foreground">{n}</div>
                <div>
                  <h3 className="font-heading mb-0.5">{title}</h3>
                  <p className="text-sm font-base">{text}</p>
                </div>
              </div>
            ))}
          </div>
          <DialogFooter>
            <Button onClick={() => setHowToUseOpen(false)}>
              GOT IT!
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}

export default App
