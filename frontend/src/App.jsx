import { useState, useEffect } from 'react'
import axios from 'axios'
import QueryInterface from './components/QueryInterface'
import ResultsDisplay from './components/ResultsDisplay'
import QueryHistory from './components/QueryHistory'
import DatabaseStatus from './components/DatabaseStatus'
import DatabaseConnectionManager from './components/DatabaseConnectionManager'
import DatabaseOverview from './components/DatabaseOverview'
import { useToast } from './hooks/useToast.jsx'

const API_BASE = '/api/v1'

function App() {
  const { showError, showSuccess, showWarning } = useToast()
  const [activeTab, setActiveTab] = useState('query')
  const [queryHistory, setQueryHistory] = useState([])
  const [dbHealth, setDbHealth] = useState(null)
  const [currentResult, setCurrentResult] = useState(null)
  const [databases, setDatabases] = useState([])
  const [defaultDatabaseId, setDefaultDatabaseId] = useState(null)
  const [selectedDatabases, setSelectedDatabases] = useState([])
  const [menuOpen, setMenuOpen] = useState(false)
  const [howToUseOpen, setHowToUseOpen] = useState(false)

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
      showError(error.response?.data?.detail || 'Failed to load databases')
    }
  }

  const checkDatabaseHealth = async () => {
    try {
      const response = await axios.get(`${API_BASE}/health/database`)
      setDbHealth(response.data)
    } catch (error) {
      setDbHealth({ database_configured: false, database_connected: false })
      console.error('Database health check failed:', error)
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
            {/* How to Use */}
            <button
              onClick={() => {
                setHowToUseOpen(true)
                setMenuOpen(false)
              }}
              className="w-full px-4 py-2 text-left hover:bg-gray-50 flex items-center gap-3"
            >
              <svg className="w-5 h-5 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <span className="text-gray-700">How to Use</span>
            </button>

            {/* Query History */}
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

            {/* Divider */}
            <div className="border-t border-gray-100 my-2" />

            {/* Git Repo */}
            <a
              href="https://github.com/jmanoj0905/natural-language-sql"
              target="_blank"
              rel="noopener noreferrer"
              className="w-full px-4 py-2 text-left hover:bg-gray-50 flex items-center gap-3 text-gray-700"
            >
              <svg className="w-5 h-5 text-gray-600" fill="currentColor" viewBox="0 0 24 24">
                <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/>
              </svg>
              <span>Git Repository</span>
            </a>

            {/* About */}
            <a
              href="https://jmanoj.pages.dev"
              target="_blank"
              rel="noopener noreferrer"
              className="w-full px-4 py-2 text-left hover:bg-gray-50 flex items-center gap-3 text-gray-700"
            >
              <svg className="w-5 h-5 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <span>Made by Manoj J</span>
            </a>
          </div>
        </div>
      )}

      {/* How to Use Modal */}
      {howToUseOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50" onClick={() => setHowToUseOpen(false)}>
          <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full mx-4 p-6" onClick={(e) => e.stopPropagation()}>
            {/* Header */}
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-2xl font-bold text-gray-900">How to Use Natural Language SQL</h2>
              <button
                onClick={() => setHowToUseOpen(false)}
                className="text-gray-400 hover:text-gray-600 transition-colors"
              >
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            {/* Content */}
            <div className="space-y-6">
              {/* Step 1 */}
              <div className="flex gap-4">
                <div className="flex-shrink-0 w-8 h-8 bg-blue-600 text-white rounded-full flex items-center justify-center font-bold">
                  1
                </div>
                <div>
                  <h3 className="font-semibold text-gray-900 mb-1">Connect Your Database</h3>
                  <p className="text-gray-600 text-sm">
                    Go to the <span className="font-medium">Connectors</span> tab and add your database connection. Supports PostgreSQL, MySQL, SQLite, and more.
                  </p>
                </div>
              </div>

              {/* Step 2 */}
              <div className="flex gap-4">
                <div className="flex-shrink-0 w-8 h-8 bg-blue-600 text-white rounded-full flex items-center justify-center font-bold">
                  2
                </div>
                <div>
                  <h3 className="font-semibold text-gray-900 mb-1">Ask Questions in Plain English</h3>
                  <p className="text-gray-600 text-sm mb-2">
                    Type your question naturally. For example:
                  </p>
                  <ul className="text-sm text-gray-600 space-y-1 ml-4 list-disc">
                    <li>"Show me all users created in the last 7 days"</li>
                    <li>"What are the top 5 products by price?"</li>
                    <li>"Find orders with status pending"</li>
                  </ul>
                </div>
              </div>

              {/* Step 3 */}
              <div className="flex gap-4">
                <div className="flex-shrink-0 w-8 h-8 bg-blue-600 text-white rounded-full flex items-center justify-center font-bold">
                  3
                </div>
                <div>
                  <h3 className="font-semibold text-gray-900 mb-1">Review Generated SQL</h3>
                  <p className="text-gray-600 text-sm">
                    The AI will generate SQL for your question. Review it to ensure it matches your intent. Toggle between <span className="font-medium">Read-Only</span> and <span className="font-medium">Write Mode</span> as needed.
                  </p>
                </div>
              </div>

              {/* Step 4 */}
              <div className="flex gap-4">
                <div className="flex-shrink-0 w-8 h-8 bg-blue-600 text-white rounded-full flex items-center justify-center font-bold">
                  4
                </div>
                <div>
                  <h3 className="font-semibold text-gray-900 mb-1">Execute and View Results</h3>
                  <p className="text-gray-600 text-sm">
                    Click <span className="font-medium">Execute Query</span> to run the SQL. View results in a clean table format with row counts and execution time.
                  </p>
                </div>
              </div>

              {/* Tips */}
              <div className="mt-6 p-4 bg-blue-50 rounded-lg border border-blue-200">
                <h4 className="font-semibold text-blue-900 mb-2 flex items-center gap-2">
                  <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                    <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z"/>
                  </svg>
                  Pro Tips
                </h4>
                <ul className="text-sm text-blue-800 space-y-1 ml-4 list-disc">
                  <li>Use specific table and column names from your schema</li>
                  <li>Check the <span className="font-medium">Databases</span> tab to view your schema</li>
                  <li>Enable auto-execute in read-only mode for faster queries</li>
                  <li>Use write mode carefully - always review before executing</li>
                </ul>
              </div>
            </div>

            {/* Footer */}
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
