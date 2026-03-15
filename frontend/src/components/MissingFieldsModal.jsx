import { useState } from 'react'

export default function MissingFieldsModal({ missingFields, onSubmit, onCancel }) {
  const [fieldValues, setFieldValues] = useState({})

  const handleSubmit = (e) => {
    e.preventDefault()
    onSubmit(fieldValues)
  }

  const handleChange = (field, value) => {
    setFieldValues(prev => ({
      ...prev,
      [`${field.table}.${field.column}`]: value
    }))
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full mx-4 max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="bg-amber-50 border-b border-amber-200 px-6 py-4">
          <div className="flex items-center gap-3">
            <svg className="w-6 h-6 text-amber-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
            <div>
              <h2 className="text-lg font-semibold text-amber-900">Additional Information Required</h2>
              <p className="text-sm text-amber-700 mt-1">
                The following fields are required but weren't provided in your question
              </p>
            </div>
          </div>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="p-6">
          <div className="space-y-4">
            {missingFields.map((field, index) => (
              <div key={index} className="border border-gray-200 rounded-lg p-4">
                <label className="block">
                  <div className="flex items-start justify-between mb-2">
                    <div>
                      <span className="text-sm font-medium text-gray-700">
                        {field.table}.{field.column}
                      </span>
                      {field.data_type && (
                        <span className="ml-2 text-xs text-gray-500">
                          ({field.data_type})
                        </span>
                      )}
                    </div>
                    <span className="text-xs bg-red-100 text-red-700 px-2 py-1 rounded">
                      Required
                    </span>
                  </div>

                  <p className="text-sm text-gray-600 mb-3">
                    {field.description}
                  </p>

                  {field.example && (
                    <p className="text-xs text-gray-500 mb-2">
                      Example: <code className="bg-gray-100 px-1 rounded">{field.example}</code>
                    </p>
                  )}

                  <input
                    type="text"
                    required
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none"
                    placeholder={field.example || `Enter ${field.column}...`}
                    value={fieldValues[`${field.table}.${field.column}`] || ''}
                    onChange={(e) => handleChange(field, e.target.value)}
                  />
                </label>
              </div>
            ))}
          </div>

          {/* Info Box */}
          <div className="mt-6 bg-blue-50 border border-blue-200 rounded-lg p-4">
            <div className="flex gap-3">
              <svg className="w-5 h-5 text-blue-600 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <div className="text-sm text-blue-800">
                <p className="font-medium mb-1">Why am I seeing this?</p>
                <p>
                  These fields are marked as "NOT NULL" in the database schema and don't have default values.
                  You need to provide values for them to create the record successfully.
                </p>
              </div>
            </div>
          </div>

          {/* Actions */}
          <div className="flex gap-3 mt-6">
            <button
              type="submit"
              className="flex-1 bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 focus:ring-4 focus:ring-blue-200 transition-colors font-medium"
            >
              Generate SQL with These Values
            </button>
            <button
              type="button"
              onClick={onCancel}
              className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 focus:ring-4 focus:ring-gray-200 transition-colors font-medium text-gray-700"
            >
              Cancel
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
