import { useState, useEffect } from 'react'
import axios from 'axios'

export default function SchemaViewer({ databaseId }) {
  const [schema, setSchema] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [expandedTables, setExpandedTables] = useState({})

  useEffect(() => {
    if (databaseId) {
      loadSchema()
    }
  }, [databaseId])

  const loadSchema = async () => {
    setLoading(true)
    setError(null)
    try {
      const url = databaseId ? `/api/v1/schema?database_id=${databaseId}` : '/api/v1/schema'
      const response = await axios.get(url)

      if (response.data.success && response.data.tables) {
        setSchema({ tables: response.data.tables })
      } else {
        setError('No schema data available')
      }

    } catch (err) {
      setError(err.response?.data?.detail?.message || 'Failed to load schema')
    } finally {
      setLoading(false)
    }
  }

  const toggleTable = (tableName) => {
    setExpandedTables(prev => ({
      ...prev,
      [tableName]: !prev[tableName]
    }))
  }

  // Sample schema for demo purposes
  const sampleSchema = {
    tables: [
      {
        name: 'users',
        columns: [
          { name: 'id', type: 'integer', nullable: false, primary_key: true },
          { name: 'username', type: 'varchar(100)', nullable: false },
          { name: 'email', type: 'varchar(255)', nullable: false },
          { name: 'created_at', type: 'timestamp', nullable: false },
        ]
      },
      {
        name: 'products',
        columns: [
          { name: 'id', type: 'integer', nullable: false, primary_key: true },
          { name: 'name', type: 'varchar(255)', nullable: false },
          { name: 'price', type: 'decimal(10,2)', nullable: false },
          { name: 'stock_quantity', type: 'integer', nullable: false },
        ]
      },
      {
        name: 'orders',
        columns: [
          { name: 'id', type: 'integer', nullable: false, primary_key: true },
          { name: 'user_id', type: 'integer', nullable: false },
          { name: 'total_amount', type: 'decimal(10,2)', nullable: false },
          { name: 'status', type: 'varchar(50)', nullable: false },
        ]
      }
    ]
  }

  if (loading) {
    return (
      <div className="card text-center py-12">
        <svg className="animate-spin h-8 w-8 text-blue-600 mx-auto" fill="none" viewBox="0 0 24 24">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
        </svg>
        <p className="mt-4 text-gray-600">Loading schema...</p>
      </div>
    )
  }

  // Use real schema if available, otherwise use sample
  const displaySchema = schema || sampleSchema

  return (
    <div className="p-4 bg-gray-50 border-t border-gray-200 max-h-64 overflow-y-auto">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-gray-700">Schema</h3>
        <button
          onClick={loadSchema}
          className="text-xs px-2 py-1 text-gray-600 hover:text-gray-900 hover:bg-gray-200 rounded transition-colors"
        >
          Refresh
        </button>
      </div>

      {error && (
        <div className="p-2 bg-red-50 border border-red-200 rounded mb-3">
          <p className="text-xs text-red-800">{error}</p>
        </div>
      )}

      <div className="space-y-2">
        {displaySchema.tables.map((table) => (
          <div key={table.name} className="border border-gray-200 rounded overflow-hidden bg-white">
            <button
              onClick={() => toggleTable(table.name)}
              className="w-full px-3 py-2 bg-white hover:bg-gray-50 flex items-center justify-between transition-colors"
            >
              <div className="flex items-center gap-2">
                <svg className="w-4 h-4 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 10h18M3 14h18m-9-4v8m-7 0h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
                </svg>
                <span className="font-mono text-xs font-medium text-gray-900">{table.name}</span>
              </div>
              <svg
                className={`w-4 h-4 text-gray-500 transform transition-transform ${
                  expandedTables[table.name] ? 'rotate-180' : ''
                }`}
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </button>

            {expandedTables[table.name] && (
              <div className="bg-gray-50 px-3 py-2">
                <div className="space-y-1">
                  {table.columns.map((column) => (
                    <div key={column.name} className="flex items-center justify-between text-xs">
                      <span className="font-mono text-gray-900">{column.name}</span>
                      <span className="text-gray-600">{column.type}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
