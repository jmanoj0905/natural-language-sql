import {
  Database,
  Container,
  Cloud,
  CloudCog,
  Waves,
  Zap,
  Train,
  Palette,
  CircleDot,
  Globe,
  Settings,
  Server,
  CheckCircle,
  XCircle,
  Loader2
} from 'lucide-react'

const ICON_COMPONENTS = {
  database: Database,
  docker: Container,
  aws: Cloud,
  gcp: CloudCog,
  azure: Cloud,
  digitalocean: Waves,
  supabase: Zap,
  railway: Train,
  render: Palette,
  heroku: CircleDot,
  neon: Zap,
  planetscale: Globe,
  settings: Settings
}

export default function ConnectionForm({
  provider,
  formData,
  onFormDataChange,
  onSave,
  onCancel,
  onChangeProvider,
  testConnection,
  testingConnection,
  testResult
}) {
  const handleInputChange = (e) => {
    const { name, value } = e.target
    onFormDataChange(prev => ({
      ...prev,
      [name]: value
    }))
  }

  const isFieldDisabled = (fieldName) => {
    // Disable pre-filled fields for localhost and docker providers
    if (provider.config && provider.config[fieldName] !== undefined) {
      return provider.id.includes('localhost') || provider.id.includes('docker')
    }
    return false
  }

  const providerHints = provider.hints || {}
  const IconComponent = ICON_COMPONENTS[provider.icon] || Server

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
      <div className="bg-white rounded-lg max-w-2xl w-full max-h-[90vh] overflow-y-auto">
        <div className="p-6">
          {/* Provider Header */}
          <div className="flex items-center justify-between mb-6 pb-4 border-b border-gray-200">
            <div>
              <h3 className="text-2xl font-bold text-gray-900">Connect to Database</h3>
              <div className="flex items-center gap-2 mt-2">
                <IconComponent size={20} className="text-blue-600" />
                <p className="text-gray-600 font-medium">{provider.fullName}</p>
              </div>
            </div>
            <button
              onClick={onChangeProvider}
              className="text-sm text-blue-600 hover:text-blue-800 font-medium px-4 py-2 border border-blue-300 rounded-lg hover:bg-blue-50 transition-colors"
            >
              Change Provider
            </button>
          </div>

          {/* Info Box */}
          <div className="mb-6 p-4 bg-blue-50 border border-blue-200 rounded-lg">
            <p className="text-sm text-blue-800">
              <span className="font-semibold">Auto-configured for {provider.name}:</span> Some fields have been pre-filled based on your provider selection. You only need to fill in your credentials and database details.
            </p>
          </div>

          {/* Form Fields */}
          <div className="space-y-4">
            {/* Database ID */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Database ID <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                name="database_id"
                value={formData.database_id}
                onChange={handleInputChange}
                placeholder="e.g., prod-db, dev-db, my-app-db"
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                required
              />
              <p className="text-xs text-gray-500 mt-1">Unique identifier for this database connection</p>
            </div>

            {/* Nickname */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Nickname (Optional)
              </label>
              <input
                type="text"
                name="nickname"
                value={formData.nickname}
                onChange={handleInputChange}
                placeholder="e.g., Production Database, Dev Server"
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            {/* Host and Port */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Host <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  name="host"
                  value={formData.host}
                  onChange={handleInputChange}
                  placeholder={providerHints.host || 'e.g., localhost'}
                  disabled={isFieldDisabled('host')}
                  className={`w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                    isFieldDisabled('host') ? 'bg-gray-100 cursor-not-allowed' : ''
                  }`}
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Port <span className="text-red-500">*</span>
                </label>
                <input
                  type="number"
                  name="port"
                  value={formData.port}
                  onChange={handleInputChange}
                  disabled={isFieldDisabled('port')}
                  className={`w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                    isFieldDisabled('port') ? 'bg-gray-100 cursor-not-allowed' : ''
                  }`}
                  required
                />
              </div>
            </div>

            {/* Database Name */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Database Name <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                name="database"
                value={formData.database}
                onChange={handleInputChange}
                placeholder={providerHints.database || 'Enter database name'}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                required
              />
            </div>

            {/* Username */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Username <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                name="username"
                value={formData.username}
                onChange={handleInputChange}
                placeholder={providerHints.username || 'Enter username'}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                required
              />
            </div>

            {/* Password */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Password <span className="text-red-500">*</span>
              </label>
              <input
                type="password"
                name="password"
                value={formData.password}
                onChange={handleInputChange}
                placeholder={providerHints.password || 'Enter password'}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                required
              />
            </div>

            {/* SSL Mode */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                SSL Mode
              </label>
              <select
                name="ssl_mode"
                value={formData.ssl_mode}
                onChange={handleInputChange}
                disabled={isFieldDisabled('ssl_mode')}
                className={`w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                  isFieldDisabled('ssl_mode') ? 'bg-gray-100 cursor-not-allowed' : ''
                }`}
              >
                <option value="disable">Disable</option>
                <option value="prefer">Prefer</option>
                <option value="require">Require</option>
              </select>
            </div>
          </div>

          {/* Test Connection Button */}
          <button
            onClick={testConnection}
            disabled={testingConnection || !formData.database_id || !formData.database}
            className="w-full mt-6 py-3 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300 disabled:opacity-50 disabled:cursor-not-allowed font-medium transition-colors"
          >
            {testingConnection ? (
              <span className="flex items-center justify-center gap-2">
                <Loader2 size={20} className="animate-spin" />
                Testing Connection...
              </span>
            ) : (
              'Test Connection'
            )}
          </button>

          {/* Test Result */}
          {testResult && (
            <div className={`mt-4 p-4 rounded-lg border ${
              testResult.success
                ? 'bg-green-50 border-green-200 text-green-800'
                : 'bg-red-50 border-red-200 text-red-800'
            }`}>
              <div className="flex items-start gap-3">
                {testResult.success ? (
                  <CheckCircle size={20} className="mt-0.5 flex-shrink-0" />
                ) : (
                  <XCircle size={20} className="mt-0.5 flex-shrink-0" />
                )}
                <div>
                  <p className="font-medium">
                    {testResult.success ? 'Connection successful!' : 'Connection failed'}
                  </p>
                  {!testResult.success && testResult.error && (
                    <p className="text-sm mt-1">{testResult.error}</p>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* Action Buttons */}
          <div className="flex gap-3 mt-6">
            <button
              onClick={onSave}
              disabled={!formData.database_id || !formData.database}
              className="flex-1 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed font-medium transition-colors"
            >
              Save Database
            </button>
            <button
              onClick={onCancel}
              className="flex-1 py-3 border border-gray-300 rounded-lg hover:bg-gray-50 font-medium transition-colors"
            >
              Cancel
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
