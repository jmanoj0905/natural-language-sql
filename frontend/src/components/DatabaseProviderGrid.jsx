import { useState } from 'react'
import { Search, Database, Container, Cloud, CloudCog, Waves, Zap, Train, Palette, CircleDot, Globe, Settings, HardDrive, Server } from 'lucide-react'
import { PROVIDERS } from '../data/providers'

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

const BADGE_COLORS = {
  'Local': 'bg-gray-100 text-gray-700',
  'Container': 'bg-blue-100 text-blue-700',
  'Cloud': 'bg-green-100 text-green-700',
  'Popular': 'bg-purple-100 text-purple-700',
  'Platform': 'bg-orange-100 text-orange-700',
  'Serverless': 'bg-pink-100 text-pink-700',
  'Custom': 'bg-gray-100 text-gray-700'
}

// Database type indicators
const DB_TYPE_COLORS = {
  postgresql: 'bg-blue-600 text-white',
  mysql: 'bg-orange-600 text-white'
}

function ProviderCard({ provider, onSelect }) {
  const IconComponent = ICON_COMPONENTS[provider.icon] || Database
  const badgeColor = BADGE_COLORS[provider.badge] || BADGE_COLORS['Custom']
  const dbTypeColor = DB_TYPE_COLORS[provider.dbType] || 'bg-gray-600 text-white'

  return (
    <button
      onClick={() => onSelect(provider)}
      title={`Configure ${provider.fullName} - ${provider.description}`}
      className="w-full p-4 border-2 border-gray-200 rounded-lg hover:border-blue-500 hover:shadow-md transition-all text-left group"
    >
      <div className="flex items-start gap-3">
        <div className="p-2 bg-blue-50 rounded-lg group-hover:bg-blue-100 transition-colors">
          <IconComponent size={24} className="text-blue-600" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1 flex-wrap">
            <h4 className="font-semibold text-gray-900 text-sm">{provider.name}</h4>
            <span className={`text-xs px-1.5 py-0.5 rounded font-medium ${dbTypeColor}`}>
              {provider.dbType === 'postgresql' ? 'PG' : 'MY'}
            </span>
            {provider.badge && (
              <span className={`text-xs px-2 py-0.5 rounded ${badgeColor}`}>
                {provider.badge}
              </span>
            )}
          </div>
          <p className="text-xs text-gray-600">{provider.description}</p>
        </div>
      </div>
    </button>
  )
}

// Categorize providers
function categorizeProviders(providers) {
  const categories = {
    local: [],
    cloud: [],
    platform: [],
    custom: []
  }

  providers.forEach(provider => {
    if (provider.badge === 'Local' || provider.badge === 'Container') {
      categories.local.push(provider)
    } else if (provider.badge === 'Cloud') {
      categories.cloud.push(provider)
    } else if (provider.badge === 'Platform' || provider.badge === 'Serverless' || provider.badge === 'Popular') {
      categories.platform.push(provider)
    } else {
      categories.custom.push(provider)
    }
  })

  return categories
}

export default function DatabaseProviderGrid({ onProviderSelect, onCancel }) {
  const [searchTerm, setSearchTerm] = useState('')
  const [filterDbType, setFilterDbType] = useState('all') // 'all', 'postgresql', 'mysql'

  // Filter providers based on search term and database type
  let filteredProviders = PROVIDERS.filter(p =>
    p.fullName.toLowerCase().includes(searchTerm.toLowerCase()) ||
    p.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    p.description.toLowerCase().includes(searchTerm.toLowerCase()) ||
    p.dbType.toLowerCase().includes(searchTerm.toLowerCase())
  )

  // Apply database type filter
  if (filterDbType !== 'all') {
    filteredProviders = filteredProviders.filter(p => p.dbType === filterDbType)
  }

  // Categorize filtered providers
  const categories = categorizeProviders(filteredProviders)

  return (
    <div className="h-full flex flex-col bg-white">
      {/* Header */}
      <div className="px-6 py-4 border-b border-gray-200">
        <h2 className="text-lg font-semibold text-gray-900 mb-1">Select Database Provider</h2>
        <p className="text-sm text-gray-600">
          Choose a provider to auto-configure connection settings
        </p>
      </div>

      {/* Search and Filter */}
      <div className="px-6 py-4 border-b border-gray-200 space-y-3">
        <div className="relative">
          <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
            <Search size={18} className="text-gray-400" />
          </div>
          <input
            type="text"
            placeholder="Search providers (e.g., AWS, localhost, Docker)..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-10 pr-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            autoFocus
          />
        </div>

        {/* Database Type Filter */}
        <div className="flex gap-2">
          <button
            onClick={() => setFilterDbType('all')}
            title="Show all database providers (PostgreSQL and MySQL)"
            className={`px-3 py-1.5 text-sm rounded-lg font-medium transition-colors ${
              filterDbType === 'all'
                ? 'bg-gray-900 text-white'
                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
            }`}
          >
            All Databases
          </button>
          <button
            onClick={() => setFilterDbType('postgresql')}
            title="Show only PostgreSQL providers"
            className={`px-3 py-1.5 text-sm rounded-lg font-medium transition-colors ${
              filterDbType === 'postgresql'
                ? 'bg-blue-600 text-white'
                : 'bg-blue-50 text-blue-700 hover:bg-blue-100'
            }`}
          >
            PostgreSQL Only
          </button>
          <button
            onClick={() => setFilterDbType('mysql')}
            title="Show only MySQL providers"
            className={`px-3 py-1.5 text-sm rounded-lg font-medium transition-colors ${
              filterDbType === 'mysql'
                ? 'bg-orange-600 text-white'
                : 'bg-orange-50 text-orange-700 hover:bg-orange-100'
            }`}
          >
            MySQL Only
          </button>
        </div>
      </div>

      {/* Provider Grid - Scrollable */}
      <div className="flex-1 overflow-y-auto px-6 py-4">
        {filteredProviders.length === 0 ? (
          <div className="text-center py-12 text-gray-500">
            <p>No providers found</p>
            {searchTerm && <p className="text-sm mt-1">Try adjusting your search or filter</p>}
          </div>
        ) : (
          <div className="space-y-6">
            {/* Local & Development */}
            {categories.local.length > 0 && (
              <div>
                <h3 className="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2">
                  <HardDrive size={18} className="text-gray-600" />
                  Local & Development
                  <span className="text-xs font-normal text-gray-500">({categories.local.length})</span>
                </h3>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                  {categories.local.map(provider => (
                    <ProviderCard
                      key={provider.id}
                      provider={provider}
                      onSelect={onProviderSelect}
                    />
                  ))}
                </div>
              </div>
            )}

            {/* Cloud Providers */}
            {categories.cloud.length > 0 && (
              <div>
                <h3 className="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2">
                  <Cloud size={18} className="text-blue-600" />
                  Cloud Providers
                  <span className="text-xs font-normal text-gray-500">({categories.cloud.length})</span>
                </h3>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                  {categories.cloud.map(provider => (
                    <ProviderCard
                      key={provider.id}
                      provider={provider}
                      onSelect={onProviderSelect}
                    />
                  ))}
                </div>
              </div>
            )}

            {/* Platforms & Serverless */}
            {categories.platform.length > 0 && (
              <div>
                <h3 className="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2">
                  <Server size={18} className="text-purple-600" />
                  Platforms & Serverless
                  <span className="text-xs font-normal text-gray-500">({categories.platform.length})</span>
                </h3>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                  {categories.platform.map(provider => (
                    <ProviderCard
                      key={provider.id}
                      provider={provider}
                      onSelect={onProviderSelect}
                    />
                  ))}
                </div>
              </div>
            )}

            {/* Custom */}
            {categories.custom.length > 0 && (
              <div>
                <h3 className="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2">
                  <Settings size={18} className="text-gray-600" />
                  Custom Configuration
                  <span className="text-xs font-normal text-gray-500">({categories.custom.length})</span>
                </h3>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                  {categories.custom.map(provider => (
                    <ProviderCard
                      key={provider.id}
                      provider={provider}
                      onSelect={onProviderSelect}
                    />
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Footer */}
      {onCancel && (
        <div className="px-6 py-4 border-t border-gray-200 bg-gray-50">
          <button
            onClick={onCancel}
            title="Go back to connection form"
            className="px-4 py-2 text-sm text-gray-700 hover:text-gray-900 font-medium"
          >
            ← Back
          </button>
        </div>
      )}
    </div>
  )
}
