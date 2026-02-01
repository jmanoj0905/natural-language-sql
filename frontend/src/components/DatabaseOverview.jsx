import { useState, useEffect } from 'react'
import axios from 'axios'
import { Database, Server, ChevronDown, ChevronUp, RefreshCw, CheckCircle, XCircle } from 'lucide-react'

export default function DatabaseOverview() {
  const [databases, setDatabases] = useState([])
  const [schemas, setSchemas] = useState({})
  const [expandedDatabases, setExpandedDatabases] = useState({})
  const [expandedTables, setExpandedTables] = useState({})
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    loadDatabases()
  }, [])

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

  const loadSchemaForDatabase = async (databaseId) => {
    if (schemas[databaseId]) return

    try {
      const response = await axios.get(`/api/v1/schema?database_id=${databaseId}`)
      setSchemas(prev => ({
        ...prev,
        [databaseId]: response.data.tables
      }))
    } catch (error) {
      setSchemas(prev => ({
        ...prev,
        [databaseId]: []
      }))
    }
  }

  const toggleDatabase = (databaseId) => {
    setExpandedDatabases(prev => {
      const newExpanded = { ...prev, [databaseId]: !prev[databaseId] }

      // Load schema when expanding
      if (newExpanded[databaseId]) {
        loadSchemaForDatabase(databaseId)
      }

      return newExpanded
    })
  }

  const toggleTable = (databaseId, tableName) => {
    const key = `${databaseId}:${tableName}`
    setExpandedTables(prev => ({
      ...prev,
      [key]: !prev[key]
    }))
  }

  const getProviderName = (db) => {
    // Try to determine provider from host or other fields
    if (db.host?.includes('rds.amazonaws.com')) return 'AWS RDS'
    if (db.host?.includes('supabase.co')) return 'Supabase'
    if (db.host?.includes('railway.app')) return 'Railway'
    if (db.host?.includes('render.com')) return 'Render'
    if (db.host?.includes('ondigitalocean.com')) return 'DigitalOcean'
    if (db.host?.includes('database.azure.com')) return 'Azure Database'
    if (db.host?.includes('neon.tech')) return 'Neon'
    if (db.host?.includes('psdb.cloud')) return 'PlanetScale'
    if (db.host === 'localhost' || db.host === '127.0.0.1') return 'Local'
    return 'Custom'
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <RefreshCw className="animate-spin h-8 w-8 text-blue-600 mx-auto mb-2" />
          <p className="text-gray-600">Loading databases...</p>
        </div>
      </div>
    )
  }

  if (databases.length === 0) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <Database size={48} className="text-gray-400 mx-auto mb-4" />
          <p className="text-gray-600 mb-2">No databases configured</p>
          <p className="text-sm text-gray-500">Go to Connectors tab to add a database</p>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold text-gray-900">Databases</h2>
          <p className="text-sm text-gray-600 mt-1">
            View database schemas and table structures
          </p>
        </div>
        <button
          onClick={loadDatabases}
          title="Refresh database list"
          className="px-4 py-2 text-sm border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors flex items-center gap-2"
        >
          <RefreshCw size={16} />
          Refresh
        </button>
      </div>

      {/* Database Cards */}
      <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-4">
        {databases.map(db => {
          const isExpanded = expandedDatabases[db.database_id]
          const dbSchema = schemas[db.database_id]
          const provider = getProviderName(db)

          return (
            <div
              key={db.database_id}
              className="bg-white border border-gray-200 rounded-lg shadow-sm hover:shadow-md transition-shadow overflow-hidden"
            >
              {/* Card Header - Always Visible */}
              <button
                onClick={() => toggleDatabase(db.database_id)}
                title={isExpanded ? 'Click to collapse details' : 'Click to view connection details and schema'}
                className="w-full p-5 text-left hover:bg-gray-50 transition-colors"
              >
                <div className="flex items-start justify-between mb-3">
                  <div className="flex items-center gap-3">
                    <div className="p-2 bg-blue-50 rounded-lg">
                      <Database size={24} className="text-blue-600" />
                    </div>
                    <div>
                      <h3 className="font-semibold text-gray-900">
                        {db.nickname || db.database_id}
                      </h3>
                      <p className="text-xs text-gray-500 mt-0.5">{provider}</p>
                    </div>
                  </div>
                  {isExpanded ? (
                    <ChevronUp size={20} className="text-gray-400" />
                  ) : (
                    <ChevronDown size={20} className="text-gray-400" />
                  )}
                </div>

                {/* Quick Info */}
                <div className="flex items-center gap-4 text-xs">
                  <div className="flex items-center gap-1.5">
                    {db.is_connected ? (
                      <CheckCircle size={14} className="text-green-600" />
                    ) : (
                      <XCircle size={14} className="text-red-600" />
                    )}
                    <span className={db.is_connected ? 'text-green-700' : 'text-red-700'}>
                      {db.is_connected ? 'Connected' : 'Disconnected'}
                    </span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <Server size={14} className="text-gray-500" />
                    <span className="text-gray-600">
                      {db.db_type === 'postgresql' ? 'PostgreSQL' : 'MySQL'}
                    </span>
                  </div>
                  {db.is_default && (
                    <span className="px-2 py-0.5 bg-blue-100 text-blue-700 rounded font-medium">
                      Default
                    </span>
                  )}
                </div>
              </button>

              {/* Expanded Details */}
              {isExpanded && (
                <div className="border-t border-gray-200 bg-gray-50">
                  {/* Connection Details */}
                  <div className="p-4 border-b border-gray-200 bg-white">
                    <h4 className="text-xs font-semibold text-gray-700 mb-2">Connection Details</h4>
                    <div className="space-y-1.5 text-xs">
                      <div className="flex justify-between">
                        <span className="text-gray-600">Host:</span>
                        <span className="text-gray-900 font-mono">{db.host}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-600">Port:</span>
                        <span className="text-gray-900 font-mono">{db.port}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-600">Database:</span>
                        <span className="text-gray-900 font-mono">{db.database}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-600">User:</span>
                        <span className="text-gray-900 font-mono">{db.username}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-600">SSL Mode:</span>
                        <span className="text-gray-900 font-mono">{db.ssl_mode || 'prefer'}</span>
                      </div>
                    </div>
                  </div>

                  {/* Schema Section */}
                  <div className="p-4">
                    <h4 className="text-xs font-semibold text-gray-700 mb-3">
                      Tables {dbSchema && `(${dbSchema.length})`}
                    </h4>

                    {!dbSchema ? (
                      <div className="text-center py-4 text-xs text-gray-500">
                        Loading schema...
                      </div>
                    ) : dbSchema.length === 0 ? (
                      <div className="text-center py-4 text-xs text-gray-500">
                        No tables found
                      </div>
                    ) : (
                      <div className="space-y-2 max-h-96 overflow-y-auto">
                        {dbSchema.map(table => {
                          const tableKey = `${db.database_id}:${table.name}`
                          const isTableExpanded = expandedTables[tableKey]

                          return (
                            <div
                              key={table.name}
                              className="border border-gray-200 rounded bg-white overflow-hidden"
                            >
                              <button
                                onClick={(e) => {
                                  e.stopPropagation()
                                  toggleTable(db.database_id, table.name)
                                }}
                                title={isTableExpanded ? 'Click to hide columns' : `Click to view columns in ${table.name}`}
                                className="w-full px-3 py-2 flex items-center justify-between hover:bg-gray-50 transition-colors"
                              >
                                <div className="flex items-center gap-2">
                                  <Server size={14} className="text-gray-600" />
                                  <span className="text-xs font-mono font-medium text-gray-900">
                                    {table.name}
                                  </span>
                                  <span className="text-xs text-gray-500">
                                    ({table.columns.length} columns)
                                  </span>
                                </div>
                                {isTableExpanded ? (
                                  <ChevronUp size={14} className="text-gray-400" />
                                ) : (
                                  <ChevronDown size={14} className="text-gray-400" />
                                )}
                              </button>

                              {isTableExpanded && (
                                <div className="px-3 py-2 bg-gray-50 border-t border-gray-200">
                                  <div className="space-y-1">
                                    {table.columns.map(col => (
                                      <div
                                        key={col.name}
                                        className="flex items-center justify-between text-xs py-1"
                                      >
                                        <span className="font-mono text-gray-900">{col.name}</span>
                                        <div className="flex items-center gap-2">
                                          <span className="text-gray-600">{col.type}</span>
                                          {!col.nullable && (
                                            <span className="px-1 text-xs text-red-600">NOT NULL</span>
                                          )}
                                        </div>
                                      </div>
                                    ))}
                                  </div>
                                </div>
                              )}
                            </div>
                          )
                        })}
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
