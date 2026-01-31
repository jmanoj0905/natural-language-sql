import { useState } from 'react'

export default function DatabaseStatus({ health, databases = [], onRefresh }) {
  const [refreshing, setRefreshing] = useState(false)

  const handleRefresh = async () => {
    setRefreshing(true)
    await onRefresh()
    setTimeout(() => setRefreshing(false), 500)
  }

  // Multi-database status
  const connectedCount = databases.filter(db => db.is_connected).length
  const totalCount = databases.length

  // Fallback to single database health check for backwards compatibility
  const isHealthy = totalCount > 0
    ? connectedCount > 0
    : health?.database_configured && health?.database_connected

  const getStatusColor = () => {
    if (totalCount === 0) return 'bg-gray-400'
    if (connectedCount === totalCount) return 'bg-green-500'
    if (connectedCount > 0) return 'bg-yellow-500'
    return 'bg-red-500'
  }

  const getStatusText = () => {
    if (totalCount === 0) return 'No databases configured'
    if (connectedCount === totalCount) return `${totalCount} database${totalCount > 1 ? 's' : ''} connected`
    if (connectedCount > 0) return `${connectedCount}/${totalCount} databases connected`
    return `${totalCount} database${totalCount > 1 ? 's' : ''} disconnected`
  }

  return (
    <div className="flex items-center gap-3">
      <div className="flex items-center gap-2">
        <div className={`h-3 w-3 rounded-full ${getStatusColor()} ${isHealthy ? 'animate-pulse' : ''}`} />
        <span className="text-sm font-medium text-gray-700">
          {getStatusText()}
        </span>
      </div>
      <button
        onClick={handleRefresh}
        disabled={refreshing}
        className="p-2 text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-lg transition-colors"
        title="Refresh status"
      >
        <svg className={`w-5 h-5 ${refreshing ? 'animate-spin' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
        </svg>
      </button>
    </div>
  )
}
