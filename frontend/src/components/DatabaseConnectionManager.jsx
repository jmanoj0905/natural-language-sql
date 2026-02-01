import { useState, useEffect } from 'react'
import axios from 'axios'
import DatabaseSidebar from './DatabaseSidebar'
import ConnectionConfigPanel from './ConnectionConfigPanel'
import DatabaseProviderGrid from './DatabaseProviderGrid'
import { getProviderById } from '../data/providers'

export default function DatabaseConnectionManager() {
  const [databases, setDatabases] = useState([])
  const [selectedDatabaseId, setSelectedDatabaseId] = useState(null)
  const [isNewConnection, setIsNewConnection] = useState(false)
  const [showProviderSelection, setShowProviderSelection] = useState(false)
  const [loading, setLoading] = useState(false)
  const [testingConnection, setTestingConnection] = useState(false)
  const [testResult, setTestResult] = useState(null)

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

  // Load databases on mount
  useEffect(() => {
    loadDatabases()
  }, [])

  // Load selected database data when selection changes
  useEffect(() => {
    if (selectedDatabaseId && !isNewConnection) {
      const db = databases.find(d => d.database_id === selectedDatabaseId)
      if (db) {
        setFormData({
          database_id: db.database_id,
          nickname: db.nickname || '',
          db_type: db.db_type,
          host: db.host,
          port: db.port,
          database: db.database,
          username: db.username,
          password: '', // Don't show password for security
          ssl_mode: db.ssl_mode || 'prefer'
        })
        setTestResult(null)
      }
    }
  }, [selectedDatabaseId, databases, isNewConnection])

  const loadDatabases = async () => {
    try {
      setLoading(true)
      const response = await axios.get('/api/v1/databases')
      setDatabases(response.data.databases)
    } catch (error) {
      // Silent fail - will show empty state
    } finally {
      setLoading(false)
    }
  }

  const handleAddDatabase = () => {
    // Show provider selection instead of blank form
    setShowProviderSelection(true)
    setIsNewConnection(false)
    setSelectedDatabaseId(null)
    setTestResult(null)
  }

  const handleProviderSelect = (provider) => {
    // Auto-fill form based on selected provider
    setShowProviderSelection(false)
    setIsNewConnection(true)
    setSelectedDatabaseId(null)
    setFormData({
      database_id: '',
      nickname: '', // Let user set custom name
      db_type: provider.dbType,
      host: provider.config.host || 'localhost',
      port: provider.config.port || (provider.dbType === 'mysql' ? 3306 : 5432),
      database: '',
      username: '',
      password: '',
      ssl_mode: provider.config.ssl_mode || 'prefer'
    })
    setTestResult(null)
  }

  const handleCancelProviderSelection = () => {
    setShowProviderSelection(false)
  }

  const handleRemoveDatabase = async (databaseId) => {
    const db = databases.find(d => d.database_id === databaseId)
    const confirmMessage = `Remove database "${db?.nickname || databaseId}"?`

    if (!confirm(confirmMessage)) return

    try {
      await axios.delete(`/api/v1/databases/${databaseId}`)
      await loadDatabases()

      // Clear selection if deleted database was selected
      if (selectedDatabaseId === databaseId) {
        setSelectedDatabaseId(null)
        setIsNewConnection(false)
      }
    } catch (error) {
      alert('Failed to remove database')
    }
  }

  const handleDuplicateDatabase = async (databaseId) => {
    const db = databases.find(d => d.database_id === databaseId)
    if (!db) return

    // Create form data for new connection with copied values
    // Skip provider selection for duplicate
    setShowProviderSelection(false)
    setIsNewConnection(true)
    setSelectedDatabaseId(null)
    setFormData({
      database_id: `${db.database_id}-copy`,
      nickname: db.nickname ? `${db.nickname} (Copy)` : '',
      db_type: db.db_type,
      host: db.host,
      port: db.port,
      database: db.database,
      username: db.username,
      password: '', // Don't copy password for security
      ssl_mode: db.ssl_mode || 'prefer'
    })
    setTestResult(null)
  }

  const handleSelectDatabase = (databaseId) => {
    setShowProviderSelection(false)
    setSelectedDatabaseId(databaseId)
    setIsNewConnection(false)
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

  const handleSave = async () => {
    try {
      if (isNewConnection) {
        // Create new database connection
        await axios.post('/api/v1/databases', formData)
        await loadDatabases()
        setIsNewConnection(false)
        setSelectedDatabaseId(formData.database_id)
      } else {
        // Update existing database connection
        const updateData = { ...formData }
        // Only include password if it was changed (non-empty)
        if (!updateData.password) {
          delete updateData.password
        }

        await axios.put(`/api/v1/databases/${formData.database_id}`, updateData)
        await loadDatabases()
      }

      setTestResult(null)
    } catch (error) {
      const errorMsg = error.response?.data?.detail?.message || 'Failed to save database'
      alert(errorMsg)
    }
  }

  const selectedDatabase = databases.find(d => d.database_id === selectedDatabaseId)

  return (
    <div className="h-[calc(100vh-12rem)] flex bg-white rounded-lg shadow border border-gray-200 overflow-hidden">
      {/* Left Sidebar - Data Sources */}
      <div className="w-96 flex-shrink-0 min-w-[24rem]">
        <DatabaseSidebar
          databases={databases}
          selectedDatabaseId={selectedDatabaseId}
          onSelectDatabase={handleSelectDatabase}
          onAddDatabase={handleAddDatabase}
          onRemoveDatabase={handleRemoveDatabase}
          onDuplicateDatabase={handleDuplicateDatabase}
          onRefresh={loadDatabases}
        />
      </div>

      {/* Right Panel - 70% */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {showProviderSelection ? (
          <DatabaseProviderGrid
            onProviderSelect={handleProviderSelect}
            onCancel={handleCancelProviderSelection}
          />
        ) : (
          <ConnectionConfigPanel
            selectedDatabase={selectedDatabase}
            formData={formData}
            onFormDataChange={setFormData}
            onSave={handleSave}
            testConnection={testConnection}
            testingConnection={testingConnection}
            testResult={testResult}
            isNewConnection={isNewConnection}
          />
        )}
      </div>
    </div>
  )
}
