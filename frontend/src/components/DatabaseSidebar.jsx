import { Plus, Minus, Copy, RefreshCw, Database } from 'lucide-react'
import ConnectionStatusIndicator from './ConnectionStatusIndicator'

export default function DatabaseSidebar({
  databases,
  selectedDatabaseId,
  onSelectDatabase,
  onAddDatabase,
  onRemoveDatabase,
  onDuplicateDatabase,
  onRefresh
}) {
  return (
    <div className="h-full flex flex-col bg-gray-50 border-r border-gray-200">
      {/* Header */}
      <div className="p-5 border-b border-gray-200 bg-white">
        <h3 className="text-base font-semibold text-gray-800 mb-4">Data Sources</h3>

        {/* Toolbar */}
        <div className="flex gap-2">
          <button
            onClick={onAddDatabase}
            className="flex-1 p-2.5 hover:bg-gray-100 rounded-lg transition-colors"
            title="Add new database connection"
          >
            <Plus size={20} className="mx-auto text-gray-700" />
          </button>
          <button
            onClick={() => selectedDatabaseId && onRemoveDatabase(selectedDatabaseId)}
            disabled={!selectedDatabaseId}
            className="flex-1 p-2.5 hover:bg-gray-100 rounded-lg transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
            title={selectedDatabaseId ? 'Remove selected database connection' : 'Select a database to remove'}
          >
            <Minus size={20} className="mx-auto text-gray-700" />
          </button>
          <button
            onClick={() => selectedDatabaseId && onDuplicateDatabase(selectedDatabaseId)}
            disabled={!selectedDatabaseId}
            className="flex-1 p-2.5 hover:bg-gray-100 rounded-lg transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
            title={selectedDatabaseId ? 'Duplicate selected database connection' : 'Select a database to duplicate'}
          >
            <Copy size={20} className="mx-auto text-gray-700" />
          </button>
          <button
            onClick={onRefresh}
            className="flex-1 p-2.5 hover:bg-gray-100 rounded-lg transition-colors"
            title="Refresh database list"
          >
            <RefreshCw size={20} className="mx-auto text-gray-700" />
          </button>
        </div>
      </div>

      {/* Connection List */}
      <div className="flex-1 overflow-y-auto">
        {databases.length === 0 ? (
          <div className="p-6 text-center text-sm text-gray-500">
            <p className="mb-1">No connections configured.</p>
            <p className="text-xs">Click <Plus size={12} className="inline" /> to add a database.</p>
          </div>
        ) : (
          <div className="py-2">
            {databases.map(db => (
              <button
                key={db.database_id}
                onClick={() => onSelectDatabase(db.database_id)}
                title={`Select ${db.nickname || db.database_id} - ${db.is_connected ? 'Connected' : 'Disconnected'}`}
                className={`w-full px-5 py-3.5 flex items-center gap-3 hover:bg-gray-100 transition-colors border-l-4 ${
                  selectedDatabaseId === db.database_id
                    ? 'bg-blue-50 border-blue-600'
                    : 'border-transparent'
                }`}
              >
                <ConnectionStatusIndicator isConnected={db.is_connected} />
                <Database size={18} className="text-gray-600 flex-shrink-0" />
                <div className="flex-1 text-left min-w-0">
                  <div className="text-sm font-semibold text-gray-900 truncate">
                    {db.nickname || db.database_id}
                  </div>
                  <div className="text-xs text-gray-500 truncate">
                    {db.db_type === 'postgresql' ? 'PostgreSQL' : 'MySQL'}
                    {db.host && db.port && ` • ${db.host}:${db.port}`}
                  </div>
                </div>
                {db.is_default && (
                  <span className="text-xs px-2 py-0.5 bg-blue-100 text-blue-700 rounded font-medium flex-shrink-0">
                    Default
                  </span>
                )}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
