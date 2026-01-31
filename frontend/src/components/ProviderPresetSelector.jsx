import { PROVIDERS } from '../data/providers'

export default function ProviderPresetSelector({ dbType, value, onChange }) {
  // Filter providers by database type
  const filteredProviders = PROVIDERS.filter(p => p.dbType === dbType)

  return (
    <div>
      <label className="block text-sm font-medium text-gray-700 mb-1">
        Provider Preset
      </label>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
      >
        <option value="">Manual Configuration</option>
        {filteredProviders.map(provider => (
          <option key={provider.id} value={provider.id}>
            {provider.fullName} {provider.badge && `(${provider.badge})`}
          </option>
        ))}
      </select>
      <p className="text-xs text-gray-500 mt-1">
        Select a preset to auto-fill connection settings
      </p>
    </div>
  )
}
