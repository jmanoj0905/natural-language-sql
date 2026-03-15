import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'

export default function DatabaseStatus({ health, databases = [], onRefresh }) {
  const [refreshing, setRefreshing] = useState(false)

  const handleRefresh = async () => {
    setRefreshing(true)
    await onRefresh()
    setTimeout(() => setRefreshing(false), 500)
  }

  const connectedCount = databases.filter(db => db.is_connected).length
  const totalCount = databases.length

  const isHealthy = totalCount > 0
    ? connectedCount > 0
    : health?.database_configured && health?.database_connected

  const getStatusColor = () => {
    if (totalCount === 0) return 'bg-danger'
    if (connectedCount === totalCount) return 'bg-success'
    if (connectedCount > 0) return 'bg-warning'
    return 'bg-danger'
  }

  const getStatusText = () => {
    if (totalCount === 0) return 'No databases'
    if (connectedCount === totalCount) return `${totalCount} DB${totalCount > 1 ? 's' : ''} connected`
    if (connectedCount > 0) return `${connectedCount}/${totalCount} DBs connected`
    return `${totalCount} DB${totalCount > 1 ? 's' : ''} disconnected`
  }

  return (
    <div className="flex items-center gap-2">
      <Badge variant="neutral" className="gap-2">
        <div className={`h-2.5 w-2.5 rounded-full ${getStatusColor()} ${isHealthy ? 'animate-pulse' : ''}`} />
        <span className="uppercase text-xs">{getStatusText()}</span>
      </Badge>
      <Button
        variant="neutral"
        size="icon"
        onClick={handleRefresh}
        disabled={refreshing}
        className="h-8 w-8"
      >
        <svg className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
        </svg>
      </Button>
    </div>
  )
}
