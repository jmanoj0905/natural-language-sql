import { useState, useEffect } from 'react'
import axios from 'axios'
import QueryInterface from './components/QueryInterface'
import ResultsDisplay from './components/ResultsDisplay'
import QueryHistory from './components/QueryHistory'
import DatabaseStatus from './components/DatabaseStatus'
import DatabaseConnectionManager from './components/DatabaseConnectionManager'
import DatabaseOverview from './components/DatabaseOverview'

const API_BASE = '/api/v1'

function App() {
  const [activeTab, setActiveTab] = useState('query')
  const [queryHistory, setQueryHistory] = useState([])
  const [dbHealth, setDbHealth] = useState(null)
  const [currentResult, setCurrentResult] = useState(null)
  const [databases, setDatabases] = useState([])
  const [defaultDatabaseId, setDefaultDatabaseId] = useState(null)
  const [selectedDatabases, setSelectedDatabases] = useState([])
  const [menuOpen, setMenuOpen] = useState(false)

  // Load databases on mount
  useEffect(() => {
    loadDatabases()
    const interval = setInterval(loadDatabases, 30000)
    return () => clearInterval(interval)
  }, [])

  // Check database health on mount
  useEffect(() => {
    checkDatabaseHealth()
    const interval = setInterval(checkDatabaseHealth, 30000) // Check every 30s
    return () => clearInterval(interval)
  }, [])

  const loadDatabases = async () => {
    try {
      const response = await axios.get(`${API_BASE}/databases`)
      setDatabases(response.data.databases)
      setDefaultDatabaseId(response.data.default_database_id)
    } catch (error) {
      console.error('Failed to load databases:', error)
    }
  }

  const checkDatabaseHealth = async () => {
    try {
      const response = await axios.get(`${API_BASE}/health/database`)
      setDbHealth(response.data)
    } catch (error) {
      console.error('Health check failed:', error)
      setDbHealth({ database_configured: false, database_connected: false })
    }
  }

  const handleDatabaseSelectionChange = (databaseId) => {
    setSelectedDatabases(prev => {
      if (prev.includes(databaseId)) {
        return prev.filter(id => id !== databaseId)
      } else {
        return [...prev, databaseId]
      }
    })
  }

  const handleQuerySubmit = async (question, options) => {
    try {
      // Use selected database or default
      const targetDatabaseId = selectedDatabases.length === 1
        ? selectedDatabases[0]
        : defaultDatabaseId

      const url = targetDatabaseId
        ? `${API_BASE}/query/natural?database_id=${targetDatabaseId}`
        : `${API_BASE}/query/natural`

      const response = await axios.post(url, {
        question,
        options
      })

      const result = response.data

      // Add to history
      setQueryHistory(prev => [{
        id: Date.now(),
        question,
        sql: result.generated_sql,
        explanation: result.sql_explanation,
        rowCount: result.execution_result?.row_count || 0,
        executionTime: result.execution_result?.execution_time_ms || 0,
        timestamp: new Date().toLocaleString(),
        databaseId: result.metadata?.database_id
      }, ...prev].slice(0, 20)) // Keep last 20

      // Set current result
      setCurrentResult(result)

      return result
    } catch (error) {
      throw error
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 flex flex-col">
      {/* Header */}
      <header className="bg-white shadow-sm border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              {/* Hamburger Menu */}
              <button
                onClick={() => setMenuOpen(!menuOpen)}
                className="p-2 rounded-lg hover:bg-gray-100 transition-colors"
                title="Menu"
              >
                <svg className="w-6 h-6 text-gray-700" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
                </svg>
              </button>
              <div>
                <h1 className="text-2xl font-bold text-gray-900">
                  Natural Language SQL Engine
                </h1>
              </div>
            </div>
            <DatabaseStatus
              health={dbHealth}
              databases={databases}
              onRefresh={() => {
                checkDatabaseHealth()
                loadDatabases()
              }}
            />
          </div>
        </div>
      </header>

      {/* Hamburger Menu Dropdown */}
      {menuOpen && (
        <div className="fixed inset-0 z-50" onClick={() => setMenuOpen(false)}>
          <div className="absolute top-16 left-4 bg-white rounded-lg shadow-lg border border-gray-200 py-2 min-w-[200px]" onClick={(e) => e.stopPropagation()}>
            <button
              onClick={() => {
                setActiveTab('history')
                setMenuOpen(false)
              }}
              className="w-full px-4 py-2 text-left hover:bg-gray-50 flex items-center gap-3"
            >
              <svg className="w-5 h-5 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <span className="text-gray-700">Query History</span>
            </button>
          </div>
        </div>
      )}

      {/* Navigation Tabs */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 mt-6">
        <div className="border-b border-gray-200">
          <nav className="-mb-px flex space-x-8">
            {[
              { id: 'query', label: 'Query' },
              { id: 'databases', label: 'Databases' },
              { id: 'connectors', label: 'Connectors' }
            ].map(tab => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`${
                  activeTab === tab.id
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                } whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm transition-colors`}
              >
                {tab.label}
              </button>
            ))}
          </nav>
        </div>
      </div>

      {/* Main Content */}
      <main className="flex-grow max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 w-full">
        {activeTab === 'query' && (
          <div className="space-y-6">
            <QueryInterface
              onSubmit={handleQuerySubmit}
              databases={databases}
              selectedDatabases={selectedDatabases}
              onDatabaseSelectionChange={handleDatabaseSelectionChange}
            />
            {currentResult && <ResultsDisplay result={currentResult} />}
          </div>
        )}

        {activeTab === 'databases' && <DatabaseOverview />}

        {activeTab === 'connectors' && <DatabaseConnectionManager />}

        {activeTab === 'history' && <QueryHistory history={queryHistory} />}
      </main>

    </div>
  )
}

export default App
