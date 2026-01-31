import { useState } from 'react'
import { CheckCircle, XCircle, Loader2, Eye, EyeOff } from 'lucide-react'

export default function GeneralTab({
  formData,
  onFormDataChange,
  testConnection,
  testingConnection,
  testResult,
  isNewConnection
}) {
  const [showPassword, setShowPassword] = useState(false)

  const handlePasswordToggle = () => setShowPassword(!showPassword)

  const handleInputChange = (e) => {
    const { name, value } = e.target
    onFormDataChange(prev => ({
      ...prev,
      [name]: value
    }))
  }

  // Generate connection URL for display
  const generateConnectionUrl = () => {
    if (!formData.host || !formData.database) return ''

    const { db_type, username, host, port, database } = formData
    return `${db_type}://${username ? username + '@' : ''}${host}:${port}/${database}`
  }

  return (
    <div className="space-y-5">
      {/* Database ID (only for new connections) */}
      {isNewConnection && (
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1.5">
            Database ID <span className="text-red-500">*</span>
          </label>
          <input
            type="text"
            name="database_id"
            value={formData.database_id}
            onChange={handleInputChange}
            placeholder="e.g., productionDB, testDB, myAppDB"
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            required
          />
          <p className="text-xs text-gray-500 mt-1">
            Unique identifier used in the query interface. Use a descriptive name.
          </p>
        </div>
      )}

      {/* Connection Name */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1.5">
          Connection Name <span className="text-gray-400">(Optional)</span>
        </label>
        <input
          type="text"
          name="nickname"
          value={formData.nickname}
          onChange={handleInputChange}
          placeholder="e.g., ProductionDB, TestDB, MyApp"
          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
        <p className="text-xs text-gray-500 mt-1">
          Friendly name to identify this connection. If not set, the database ID will be used.
        </p>
      </div>

      {/* Database Type - Read-only display for new connections */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1.5">
          Database Type
        </label>
        <div className="px-3 py-2 bg-gray-50 border border-gray-200 rounded-lg">
          <span className="text-gray-900 font-medium">
            {formData.db_type === 'postgresql' ? 'PostgreSQL' : 'MySQL'}
          </span>
        </div>
        {isNewConnection && (
          <p className="text-xs text-gray-500 mt-1">
            Selected during provider setup. Create a new connection to choose a different type.
          </p>
        )}
      </div>

      {/* Host and Port */}
      <div className="grid grid-cols-3 gap-4">
        <div className="col-span-2">
          <label className="block text-sm font-medium text-gray-700 mb-1.5">
            Host <span className="text-red-500">*</span>
          </label>
          <input
            type="text"
            name="host"
            value={formData.host}
            onChange={handleInputChange}
            placeholder="localhost"
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            required
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1.5">
            Port <span className="text-red-500">*</span>
          </label>
          <input
            type="number"
            name="port"
            value={formData.port}
            onChange={handleInputChange}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            required
          />
        </div>
      </div>

      {/* Database Name */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1.5">
          Database <span className="text-red-500">*</span>
        </label>
        <input
          type="text"
          name="database"
          value={formData.database}
          onChange={handleInputChange}
          placeholder="Enter database name"
          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
          required
        />
      </div>

      {/* Username */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1.5">
          User <span className="text-red-500">*</span>
        </label>
        <input
          type="text"
          name="username"
          value={formData.username}
          onChange={handleInputChange}
          placeholder="Enter username"
          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
          required
        />
      </div>

      {/* Password */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1.5">
          Password <span className="text-red-500">*</span>
        </label>
        <div className="relative">
          <input
            type={showPassword ? 'text' : 'password'}
            name="password"
            value={formData.password}
            onChange={handleInputChange}
            placeholder="Enter password"
            className="w-full px-3 py-2 pr-10 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            required
          />
          <button
            type="button"
            onClick={handlePasswordToggle}
            title={showPassword ? 'Hide password' : 'Show password'}
            className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-700"
          >
            {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
          </button>
        </div>
      </div>

      {/* SSL Mode */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1.5">
          SSL Mode
        </label>
        <select
          name="ssl_mode"
          value={formData.ssl_mode}
          onChange={handleInputChange}
          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="disable">Disable</option>
          <option value="prefer">Prefer</option>
          <option value="require">Require</option>
        </select>
      </div>

      {/* Connection URL Display */}
      {generateConnectionUrl() && (
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1.5">
            Connection URL
          </label>
          <div className="px-3 py-2 bg-gray-50 border border-gray-200 rounded-lg">
            <code className="text-xs text-gray-700 break-all">
              {generateConnectionUrl()}
            </code>
          </div>
        </div>
      )}

      {/* Test Connection Button */}
      <button
        onClick={testConnection}
        disabled={testingConnection || !formData.database || !formData.username}
        title={
          !formData.database || !formData.username
            ? 'Fill in database name and username to test connection'
            : 'Verify database connection settings'
        }
        className="w-full py-2.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed font-medium transition-colors"
      >
        {testingConnection ? (
          <span className="flex items-center justify-center gap-2">
            <Loader2 size={18} className="animate-spin" />
            Testing Connection...
          </span>
        ) : (
          'Test Connection'
        )}
      </button>

      {/* Test Result */}
      {testResult && (
        <div className={`p-3 rounded-lg border ${
          testResult.success
            ? 'bg-green-50 border-green-200 text-green-800'
            : 'bg-red-50 border-red-200 text-red-800'
        }`}>
          <div className="flex items-start gap-2">
            {testResult.success ? (
              <CheckCircle size={18} className="mt-0.5 flex-shrink-0" />
            ) : (
              <XCircle size={18} className="mt-0.5 flex-shrink-0" />
            )}
            <div className="flex-1">
              <p className="font-medium text-sm">
                {testResult.success ? 'Connection successful!' : 'Connection failed'}
              </p>
              {!testResult.success && testResult.error && (
                <p className="text-xs mt-1">{testResult.error}</p>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
