export default function QueryHistory({ history }) {
  if (!history || history.length === 0) {
    return (
      <div className="card text-center py-12">
        <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        <h3 className="mt-4 text-lg font-medium text-gray-900">No query history</h3>
        <p className="mt-2 text-sm text-gray-600">
          Your executed queries will appear here
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="card">
        <h2 className="text-xl font-semibold text-gray-900 mb-2">Query History</h2>
        <p className="text-sm text-gray-600">
          Last {history.length} queries executed
        </p>
      </div>

      {history.map((item) => (
        <div key={item.id} className="card hover:shadow-lg transition-shadow">
          <div className="flex items-start justify-between mb-3">
            <div className="flex-1">
              <h3 className="text-sm font-medium text-gray-900 mb-1">
                {item.question}
              </h3>
              <p className="text-xs text-gray-500">{item.timestamp}</p>
            </div>
            <div className="flex items-center gap-4 text-xs text-gray-600">
              <span>{item.rowCount} rows</span>
              <span>{item.executionTime.toFixed(2)}ms</span>
            </div>
          </div>

          <div className="bg-gray-900 rounded-lg p-3 overflow-x-auto">
            <pre className="text-xs text-green-400 font-mono">{item.sql}</pre>
          </div>

          {item.explanation && (
            <div className="mt-3 p-3 bg-blue-50 rounded-lg">
              <p className="text-xs text-blue-800">{item.explanation}</p>
            </div>
          )}
        </div>
      ))}
    </div>
  )
}
