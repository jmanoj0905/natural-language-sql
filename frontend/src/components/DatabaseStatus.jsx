export default function DatabaseStatus({ databases = [] }) {
  const connectedCount = databases.filter(db => db.is_connected).length
  const totalCount = databases.length

  const getStatusColor = () => {
    if (totalCount === 0) return 'bg-[#fca5a5]'
    if (connectedCount === totalCount) return 'bg-[#86EFAC]'
    if (connectedCount > 0) return 'bg-warning'
    return 'bg-[#fca5a5]'
  }

  const getStatusText = () => {
    if (totalCount === 0) return 'No databases'
    if (connectedCount === totalCount) return `${totalCount} DB${totalCount > 1 ? 's' : ''} connected`
    if (connectedCount > 0) return `${connectedCount}/${totalCount} DBs connected`
    return `${totalCount} DB${totalCount > 1 ? 's' : ''} disconnected`
  }

  return (
    <div className="inline-flex items-center gap-2 h-9 px-3 rounded-full brutalist-border bg-white text-foreground font-label text-xs font-medium whitespace-nowrap">
      <div className={`h-2.5 w-2.5 rounded-full ${getStatusColor()}`} />
      <span className="uppercase">{getStatusText()}</span>
    </div>
  )
}
