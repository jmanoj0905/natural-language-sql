import { useState } from 'react'
import { getLabel } from '../data/providers'

export default function ConnectionForm({
  formData,
  onChange,
  onTest,
  onSave,
  testResult,
  testing,
  saving,
  isNew,
}) {
  const [showPassword, setShowPassword] = useState(false)

  const handleChange = (e) => {
    const { name, value } = e.target
    onChange({ ...formData, [name]: name === 'port' ? Number(value) || '' : value })
  }

  const canTest = formData.host && formData.database && formData.username
  const canSave = canTest && (isNew ? formData.database_id?.trim() : true)

  const title = isNew
    ? `New ${getLabel(formData.db_type)} Connection`
    : `Edit ${formData.nickname || formData.database_id}`

  return (
    <div className="flex-1 overflow-y-auto p-6">
      <h2 className="text-lg font-semibold text-gray-900 mb-6">{title}</h2>

      <div className="space-y-4 max-w-lg">
        {/* Database ID — only shown for new connections */}
        {isNew && (
          <Field label="Database ID" required>
            <input
              type="text"
              name="database_id"
              value={formData.database_id}
              onChange={handleChange}
              placeholder="e.g., my-app-db"
              className="input"
            />
            <p className="text-xs text-gray-500 mt-1">Unique identifier. Cannot be changed later.</p>
          </Field>
        )}

        {/* Nickname */}
        <Field label="Name" hint="(optional)">
          <input
            type="text"
            name="nickname"
            value={formData.nickname}
            onChange={handleChange}
            placeholder="Friendly display name"
            className="input"
          />
        </Field>

        {/* Type — read-only */}
        <Field label="Type">
          <div className="px-3 py-2 bg-gray-50 border border-gray-200 rounded-lg text-gray-900 font-medium text-sm">
            {getLabel(formData.db_type)}
          </div>
        </Field>

        {/* Host + Port */}
        <div className="grid grid-cols-3 gap-3">
          <div className="col-span-2">
            <Field label="Host" required>
              <input
                type="text"
                name="host"
                value={formData.host}
                onChange={handleChange}
                placeholder="localhost"
                className="input"
              />
            </Field>
          </div>
          <Field label="Port" required>
            <input
              type="number"
              name="port"
              value={formData.port}
              onChange={handleChange}
              className="input"
            />
          </Field>
        </div>

        {/* Database */}
        <Field label="Database" required>
          <input
            type="text"
            name="database"
            value={formData.database}
            onChange={handleChange}
            placeholder="Enter database name"
            className="input"
          />
        </Field>

        {/* Username */}
        <Field label="User" required>
          <input
            type="text"
            name="username"
            value={formData.username}
            onChange={handleChange}
            placeholder="Enter username"
            className="input"
          />
        </Field>

        {/* Password */}
        <Field label="Password" required={isNew}>
          <div className="relative">
            <input
              type={showPassword ? 'text' : 'password'}
              name="password"
              value={formData.password}
              onChange={handleChange}
              placeholder={isNew ? 'Enter password' : 'Leave blank to keep current'}
              className="input pr-10"
            />
            <button
              type="button"
              onClick={() => setShowPassword(!showPassword)}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
            >
              {showPassword ? (
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21" />
                </svg>
              ) : (
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                </svg>
              )}
            </button>
          </div>
        </Field>

        {/* SSL Mode */}
        <Field label="SSL Mode">
          <select
            name="ssl_mode"
            value={formData.ssl_mode}
            onChange={handleChange}
            className="input"
          >
            <option value="disable">Disable</option>
            <option value="prefer">Prefer</option>
            <option value="require">Require</option>
          </select>
        </Field>

        {/* Test result box */}
        {testResult && (
          <div className={`p-3 rounded-lg border text-sm ${
            testResult.success
              ? 'bg-green-50 border-green-200 text-green-800'
              : 'bg-red-50 border-red-200 text-red-800'
          }`}>
            <div className="flex items-start gap-2">
              {testResult.success ? (
                <svg className="w-5 h-5 mt-0.5 flex-shrink-0 text-green-600" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                </svg>
              ) : (
                <svg className="w-5 h-5 mt-0.5 flex-shrink-0 text-red-600" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
                </svg>
              )}
              <div>
                <p className="font-medium">
                  {testResult.success ? 'Connection successful!' : 'Connection failed'}
                </p>
                {testResult.success && testResult.info && (
                  <p className="text-xs mt-1 opacity-80">
                    {testResult.info.version?.split(' ').slice(0, 2).join(' ')} &mdash; {testResult.info.size}
                  </p>
                )}
                {!testResult.success && testResult.error && (
                  <p className="text-xs mt-1">{testResult.error}</p>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Action buttons */}
        <div className="flex gap-3 pt-2">
          <button
            type="button"
            onClick={onTest}
            disabled={!canTest || testing}
            className="px-4 py-2 text-sm font-medium border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {testing ? (
              <span className="flex items-center gap-2">
                <svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
                Testing...
              </span>
            ) : (
              'Test Connection'
            )}
          </button>
          <button
            type="button"
            onClick={onSave}
            disabled={!canSave || saving}
            className="px-6 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {saving ? (
              <span className="flex items-center gap-2">
                <svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
                Saving...
              </span>
            ) : isNew ? (
              'Save'
            ) : (
              'Update'
            )}
          </button>
        </div>
      </div>
    </div>
  )
}

// Small helper for consistent field labels
function Field({ label, required, hint, children }) {
  return (
    <div>
      <label className="block text-sm font-medium text-gray-700 mb-1.5">
        {label}
        {required && <span className="text-red-500 ml-0.5">*</span>}
        {hint && <span className="text-gray-400 ml-1 font-normal">{hint}</span>}
      </label>
      {children}
    </div>
  )
}
