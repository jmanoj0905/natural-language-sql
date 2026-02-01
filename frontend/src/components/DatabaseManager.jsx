import { useState, useEffect } from 'react'
import axios from 'axios'
import ProviderSelector from './ProviderSelector'
import ConnectionForm from './ConnectionForm'

export default function DatabaseManager() {
  const [databases, setDatabases] = useState([])
  const [schemas, setSchemas] = useState({})
  const [expandedTables, setExpandedTables] = useState({})
  const [loading, setLoading] = useState(false)

  // New two-step flow state
  const [showProviderSelector, setShowProviderSelector] = useState(false)
  const [showConnectionForm, setShowConnectionForm] = useState(false)
  const [selectedProvider, setSelectedProvider] = useState(null)

  // Form state
  const [formData, setFormData] = useState({
    database_id: '',
    nickname: '',
    db_type: 'postgresql',
    host: 'localhost',
    port: 5432,
    database: '',
    username: '',
    password: '',
    ssl_mode: 'prefer'
  })
  const [testingConnection, setTestingConnection] = useState(false)
  const [testResult, setTestResult] = useState(null)

  useEffect(() => {
    loadDatabases()
  }, [])

  const loadDatabases = async () => {
    try {
      setLoading(true)
      const response = await axios.get('/api/v1/databases')
      const dbs = response.data.databases
      setDatabases(dbs)

      // Load schemas for all connected databases automatically
      for (const db of dbs) {
        if (db.is_connected) {
          loadSchemaForDatabase(db.database_id)
        }
      }
    } catch (error) {
      // Silent fail - will show empty state
    } finally {
      setLoading(false)
    }
  }

  const loadSchemaForDatabase = async (databaseId) => {
    if (schemas[databaseId]) return

    try {
      const response = await axios.get(`/api/v1/schema?database_id=${databaseId}`)
      setSchemas(prev => ({
        ...prev,
        [databaseId]: response.data.tables
      }))
    } catch (error) {
      // Silent fail - schema will not be available
    }
  }

  const toggleTableSchema = (databaseId, tableName) => {
    const key = `${databaseId}:${tableName}`
    setExpandedTables(prev => ({
      ...prev,
      [key]: !prev[key]
    }))
  }

  const testConnection = async () => {
    setTestingConnection(true)
    setTestResult(null)
    try {
      const response = await axios.post('/api/v1/databases/test', formData)
      setTestResult({ success: true, data: response.data })
    } catch (error) {
      setTestResult({
        success: false,
        error: error.response?.data?.detail?.message || 'Connection failed'
      })
    } finally {
      setTestingConnection(false)
    }
  }

  const addDatabase = async () => {
    try {
      await axios.post('/api/v1/databases', formData)
      await loadDatabases()
      setShowConnectionForm(false)
      resetForm()
    } catch (error) {
      const errorMsg = error.response?.data?.detail?.message || 'Failed to add database'
      setTestResult({ success: false, error: errorMsg })
    }
  }

  const removeDatabase = async (databaseId) => {
    if (!confirm(`Remove database "${databaseId}"?`)) return

    try {
      await axios.delete(`/api/v1/databases/${databaseId}`)
      await loadDatabases()
    } catch (error) {
      alert('Failed to remove database')
    }
  }

  const setDefault = async (databaseId) => {
    try {
      await axios.post(`/api/v1/databases/${databaseId}/set-default`)
      await loadDatabases()
    } catch (error) {
      alert('Failed to set default database')
    }
  }

  const resetForm = () => {
    setFormData({
      database_id: '',
      nickname: '',
      db_type: 'postgresql',
      host: 'localhost',
      port: 5432,
      database: '',
      username: '',
      password: '',
      ssl_mode: 'prefer'
    })
    setSelectedProvider(null)
    setTestResult(null)
  }

  // Step 1: User clicks "Add Database"
  const handleAddDatabase = () => {
    setShowProviderSelector(true)
  }

  // Step 2: User selects a provider
  const handleProviderSelect = (provider) => {
    setSelectedProvider(provider)
    setShowProviderSelector(false)

    // Auto-fill form data based on provider
    setFormData({
      database_id: '',
      nickname: provider.fullName,
      db_type: provider.dbType,
      host: provider.config.host || 'localhost',
      port: provider.config.port || (provider.dbType === 'mysql' ? 3306 : 5432),
      database: '',
      username: '',
      password: '',
      ssl_mode: provider.config.ssl_mode || 'prefer'
    })

    setShowConnectionForm(true)
  }

  // User wants to change provider from connection form
  const handleChangeProvider = () => {
    setShowConnectionForm(false)
    setShowProviderSelector(true)
    setTestResult(null)
  }

  // Cancel provider selection
  const handleCancelProviderSelection = () => {
    setShowProviderSelector(false)
    resetForm()
  }

  // Cancel connection form
  const handleCancelConnectionForm = () => {
    setShowConnectionForm(false)
    resetForm()
  }

  return (
    <div className="space-y-6">
      {/* Header with Add Button */}
      <div className="card">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-xl font-semibold">Database Connections</h2>
            <p className="text-sm text-gray-600 mt-1">
              Manage multiple database connections
            </p>
          </div>
          <button
            onClick={handleAddDatabase}
            className="btn-primary"
          >
            + Add Database
          </button>
        </div>
      </div>

      {/* Loading State */}
      {loading && (
        <div className="card text-center py-8">
          <div className="text-gray-500">Loading databases...</div>
        </div>
      )}

      {/* No Databases Message */}
      {!loading && databases.length === 0 && (
        <div className="card text-center py-8">
          <div className="text-gray-500">
            No databases configured. Click "Add Database" to get started.
          </div>
        </div>
      )}

      {/* Database List */}
      {databases.map(db => (
        <div key={db.database_id} className="card">
          <div className="flex items-start justify-between mb-4">
            <div className="flex-1">
              <div className="flex items-center gap-3">
                <div className={`h-3 w-3 rounded-full ${
                  db.is_connected ? 'bg-green-500' : 'bg-red-500'
                }`} />
                <h3 className="font-semibold text-lg">
                  {db.nickname || db.database_id}
                </h3>
                {db.database_id === databases.find(d => d.is_default)?.database_id && (
                  <span className="text-xs px-2 py-1 bg-blue-100 text-blue-800 rounded">
                    Default
                  </span>
                )}
              </div>
              <p className="text-sm text-gray-600 mt-1">
                {db.host}:{db.port}/{db.database} • {db.username}
              </p>
              {db.table_count !== null && (
                <p className="text-xs text-gray-500 mt-1">
                  {db.table_count} tables
                </p>
              )}
            </div>

            <div className="flex gap-2">
              <button
                onClick={() => setDefault(db.database_id)}
                className="text-sm px-3 py-1 border border-gray-300 rounded hover:bg-gray-50"
              >
                Set Default
              </button>
              <button
                onClick={() => removeDatabase(db.database_id)}
                className="text-sm px-3 py-1 border border-red-300 text-red-600 rounded hover:bg-red-50"
              >
                Remove
              </button>
            </div>
          </div>

          {/* Tables - Always Visible */}
          {schemas[db.database_id] && schemas[db.database_id].length > 0 && (
            <div className="border-t pt-4">
              <h4 className="text-sm font-medium text-gray-700 mb-3">Tables</h4>
              <div className="space-y-2">
                {schemas[db.database_id].map(table => {
                  const tableKey = `${db.database_id}:${table.name}`
                  const isExpanded = expandedTables[tableKey]

                  return (
                    <div key={table.name} className="border border-gray-200 rounded-lg overflow-hidden">
                      {/* Table Header - Always Visible */}
                      <button
                        onClick={() => toggleTableSchema(db.database_id, table.name)}
                        className="w-full px-4 py-3 bg-gray-50 hover:bg-gray-100 flex items-center justify-between transition-colors"
                      >
                        <div className="flex items-center gap-2">
                          <svg className={`w-4 h-4 text-gray-600 transition-transform ${isExpanded ? 'rotate-90' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                          </svg>
                          <span className="font-medium text-gray-900">{table.name}</span>
                        </div>
                        <span className="text-xs text-gray-500">
                          {table.columns.length} columns
                        </span>
                      </button>

                      {/* Table Schema - Expandable */}
                      {isExpanded && (
                        <div className="px-4 py-3 bg-white">
                          <div className="overflow-x-auto">
                            <table className="min-w-full text-sm">
                              <thead>
                                <tr className="border-b border-gray-200">
                                  <th className="text-left py-2 px-3 font-medium text-gray-700">Column</th>
                                  <th className="text-left py-2 px-3 font-medium text-gray-700">Type</th>
                                  <th className="text-left py-2 px-3 font-medium text-gray-700">Nullable</th>
                                  <th className="text-left py-2 px-3 font-medium text-gray-700">Default</th>
                                </tr>
                              </thead>
                              <tbody>
                                {table.columns.map((col, idx) => (
                                  <tr key={idx} className="border-b border-gray-100">
                                    <td className="py-2 px-3 font-mono text-xs text-gray-900">{col.name}</td>
                                    <td className="py-2 px-3 font-mono text-xs text-blue-600">{col.type}</td>
                                    <td className="py-2 px-3 text-xs text-gray-600">{col.nullable ? 'Yes' : 'No'}</td>
                                    <td className="py-2 px-3 font-mono text-xs text-gray-500">{col.default || '-'}</td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            </div>
          )}

          {/* Loading State */}
          {db.is_connected && !schemas[db.database_id] && (
            <div className="border-t pt-4 text-center text-sm text-gray-500">
              Loading tables...
            </div>
          )}

          {/* Not Connected State */}
          {!db.is_connected && (
            <div className="border-t pt-4 text-center text-sm text-gray-500">
              Database not connected
            </div>
          )}
        </div>
      ))}

      {/* Step 1: Provider Selection Modal */}
      {showProviderSelector && (
        <ProviderSelector
          onSelect={handleProviderSelect}
          onCancel={handleCancelProviderSelection}
        />
      )}

      {/* Step 2: Connection Form */}
      {showConnectionForm && selectedProvider && (
        <ConnectionForm
          provider={selectedProvider}
          formData={formData}
          onFormDataChange={setFormData}
          onSave={addDatabase}
          onCancel={handleCancelConnectionForm}
          onChangeProvider={handleChangeProvider}
          testConnection={testConnection}
          testingConnection={testingConnection}
          testResult={testResult}
        />
      )}
    </div>
  )
}
