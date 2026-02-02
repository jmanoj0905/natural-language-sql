export default function ResultsDisplay({ result }) {
  if (!result) return null

  const { generated_sql, sql_explanation, execution_result, metadata, is_multi_query, query_steps } = result

  return (
    <div className="space-y-6">
      {/* Multi-Query Plan Display */}
      {is_multi_query && query_steps && query_steps.length > 0 ? (
        <div className="card bg-purple-50 border border-purple-200">
          <div className="flex items-start gap-3 mb-4">
            <svg className="w-6 h-6 text-purple-600 mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01" />
            </svg>
            <div>
              <h3 className="text-lg font-semibold text-purple-900">Multi-Query Execution Plan</h3>
              <p className="text-sm text-purple-700 mt-1">
                This complex operation was broken down into {query_steps.length} sequential steps
              </p>
            </div>
          </div>

          <div className="space-y-4">
            {query_steps.map((step, index) => (
              <div key={index} className={`border-l-4 pl-4 ${
                step.skipped ? 'border-gray-300 bg-gray-50' : 'border-purple-400 bg-white'
              } rounded-r-lg p-4`}>
                <div className="flex items-center justify-between mb-2">
                  <h4 className="text-sm font-semibold text-gray-900">
                    Step {step.step_number}: {step.explanation}
                  </h4>
                  {step.skipped && (
                    <span className="px-2 py-1 bg-gray-200 text-gray-600 rounded text-xs font-medium">
                      Skipped: {step.skip_reason}
                    </span>
                  )}
                  {!step.skipped && step.execution_result && (
                    <span className="px-2 py-1 bg-green-100 text-green-700 rounded text-xs font-medium">
                      Executed
                    </span>
                  )}
                </div>

                <div className="bg-gray-900 rounded p-3 mb-2 overflow-x-auto">
                  <pre className="text-xs text-green-400 font-mono">
                    {step.sql}
                  </pre>
                </div>

                {!step.skipped && step.execution_result && (
                  <div className="text-xs text-gray-600">
                    {step.execution_result.row_count} rows • {step.execution_result.execution_time_ms.toFixed(2)}ms
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      ) : (
        <>
          {/* SQL Query (Single Query Mode) */}
          <div className="card">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-lg font-semibold text-gray-900">Generated SQL</h3>
              <button
                onClick={() => navigator.clipboard.writeText(generated_sql)}
                className="px-3 py-1 text-sm text-blue-600 hover:bg-blue-50 rounded-lg transition-colors"
              >
                Copy SQL
              </button>
            </div>
            <div className="bg-gray-900 rounded-lg p-4 overflow-x-auto">
              <pre className="text-sm text-green-400 font-mono">
                {generated_sql}
              </pre>
            </div>
          </div>

          {/* Explanation */}
          <div className="card bg-blue-50 border border-blue-200">
            <div className="flex items-start gap-3">
              <svg className="w-6 h-6 text-blue-600 mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <div>
                <h4 className="text-sm font-semibold text-blue-900 mb-1">Explanation</h4>
                <p className="text-sm text-blue-800">{sql_explanation}</p>
              </div>
            </div>
          </div>
        </>
      )}

      {/* Results */}
      {execution_result && (
        <div className="card">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-lg font-semibold text-gray-900">Results</h3>
              <p className="text-sm text-gray-600 mt-1">
                {execution_result.row_count} rows • {execution_result.execution_time_ms.toFixed(2)}ms
              </p>
            </div>
            <span className="px-3 py-1 bg-green-100 text-green-800 rounded-full text-sm font-medium">
              Success
            </span>
          </div>

          {execution_result.rows && execution_result.rows.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    {execution_result.columns.map((column, index) => (
                      <th
                        key={index}
                        className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
                      >
                        {column}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {execution_result.rows.map((row, rowIndex) => (
                    <tr key={rowIndex} className="hover:bg-gray-50">
                      {execution_result.columns.map((column, colIndex) => (
                        <td
                          key={colIndex}
                          className="px-6 py-4 whitespace-nowrap text-sm text-gray-900"
                        >
                          {row[column] === null ? (
                            <span className="text-gray-400 italic">null</span>
                          ) : typeof row[column] === 'boolean' ? (
                            <span className={row[column] ? 'text-green-600' : 'text-red-600'}>
                              {row[column] ? 'true' : 'false'}
                            </span>
                          ) : (
                            String(row[column])
                          )}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="text-center py-12 text-gray-500">
              <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4" />
              </svg>
              <p className="mt-2 text-sm">No results found</p>
            </div>
          )}
        </div>
      )}

      {/* Metadata */}
      <div className="flex items-center justify-between text-xs text-gray-500 px-1">
        <span>Model: {metadata?.ai_model || metadata?.gemini_model || metadata?.model || 'Unknown'}</span>
        <span>Executed: {metadata?.executed ? 'Yes' : 'No'}</span>
        <span>Timestamp: {metadata?.timestamp ? new Date(metadata.timestamp).toLocaleString() : '-'}</span>
      </div>
    </div>
  )
}
