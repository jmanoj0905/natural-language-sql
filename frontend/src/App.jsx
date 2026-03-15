import { useState, useEffect } from 'react'
import axios from 'axios'
import AppSidebar from './components/AppSidebar'
import QueryInterface from './components/QueryInterface'
import ResultsDisplay from './components/ResultsDisplay'
import QueryHistory from './components/QueryHistory'
import DatabaseStatus from './components/DatabaseStatus'
import { useToast } from './hooks/useToast.jsx'

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
      databaseId: result.metadata?.database_id,
    }, ...prev].slice(0, 20))
  }

  return (
    <div className="flex h-screen overflow-hidden bg-gray-100">
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
        <header className="bg-white border-b border-gray-200 px-6 py-3 flex items-center justify-between flex-shrink-0">
          <div className="flex items-center gap-3">
            <h1 className="text-xl font-bold text-gray-900">Natural Language SQL</h1>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={() => setShowHistory(prev => !prev)}
              className={`flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-lg transition-colors ${
                showHistory ? 'bg-blue-100 text-blue-700' : 'text-gray-600 hover:bg-gray-100'
              }`}
              title="Query history"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              History
            </button>

            <button
              onClick={() => setHowToUseOpen(true)}
              className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
              title="How to use"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              Help
            </button>

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
            <div className="w-80 flex-shrink-0 border-l border-gray-200 bg-white overflow-y-auto p-4">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-sm font-semibold text-gray-900 uppercase tracking-wide">Query History</h2>
                <button
                  onClick={() => setShowHistory(false)}
                  className="text-gray-400 hover:text-gray-600"
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
      {howToUseOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50"
          onClick={() => setHowToUseOpen(false)}
        >
          <div
            className="bg-white rounded-lg shadow-xl max-w-2xl w-full mx-4 p-6"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-2xl font-bold text-gray-900">How to Use</h2>
              <button onClick={() => setHowToUseOpen(false)} className="text-gray-400 hover:text-gray-600">
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            <div className="space-y-5">
              {[
                { n: 1, title: 'Add a Database', text: 'Click "+ Add Connection" in the sidebar and enter your PostgreSQL or MySQL credentials.' },
                { n: 2, title: 'Select a Database', text: 'Click a database in the sidebar to select it for querying. The selected one highlights in blue.' },
                { n: 3, title: 'Ask in Plain English', text: 'Type your question naturally — e.g. "Show me all users who signed up in the last 7 days".' },
                { n: 4, title: 'Review & Execute', text: 'The AI generates SQL and executes it automatically. Toggle Write Mode to run INSERT/UPDATE/DELETE.' },
              ].map(({ n, title, text }) => (
                <div key={n} className="flex gap-4">
                  <div className="flex-shrink-0 w-8 h-8 bg-blue-600 text-white rounded-full flex items-center justify-center font-bold text-sm">{n}</div>
                  <div>
                    <h3 className="font-semibold text-gray-900 mb-0.5">{title}</h3>
                    <p className="text-sm text-gray-600">{text}</p>
                  </div>
                </div>
              ))}
            </div>
            <div className="mt-6 flex justify-end">
              <button
                onClick={() => setHowToUseOpen(false)}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-medium"
              >
                Got it!
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default App
