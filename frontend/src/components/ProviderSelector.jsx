import { useState } from 'react'
import { Search, X, Database } from 'lucide-react'
import ProviderCard from './ProviderCard'
import { PROVIDERS } from '../data/providers'

// Custom PostgreSQL logo SVG
const PostgreSQLIcon = () => (
  <svg viewBox="0 0 24 24" className="w-6 h-6" fill="currentColor">
    <path d="M17.128 0c-1.313 0-1.953.906-1.953 2.219v15.906c0 1.313-.906 2.219-2.219 2.219H2.219C.906 20.344 0 19.438 0 18.125V2.22C0 .906.906 0 2.219 0zm4.266 5.625c-.703 0-1.406.234-1.875.703-.469.469-.703 1.172-.703 1.875v9.844c0 1.078-.469 1.875-1.172 2.344-.703.469-1.641.703-2.578.703h-2.813c-.703 0-1.406-.234-1.875-.703-.469-.469-.703-1.172-.703-1.875V8.672c0-.703.234-1.406.703-1.875.469-.469 1.172-.703 1.875-.703h2.813c.703 0 1.406.234 1.875.703.469.469.703 1.172.703 1.875v8.203c0 .703.234 1.406.703 1.875.469.469 1.172.703 1.875.703.703 0 1.406-.234 1.875-.703.469-.469.703-1.172.703-1.875v-9.844c0-.703-.234-1.406-.703-1.875-.469-.469-1.172-.703-1.875-.703z"/>
  </svg>
)

// Custom MySQL logo SVG
const MySQLIcon = () => (
  <svg viewBox="0 0 24 24" className="w-6 h-6" fill="currentColor">
    <path d="M16.405 5.501c-.115 0-.193.014-.274.033v.013h.014c.054.104.146.18.214.273.054.107.1.214.154.32l.014-.015c.094-.066.14-.172.14-.333-.04-.047-.046-.094-.08-.14-.04-.067-.126-.1-.18-.153zM5.77 18.695h-.927a50.854 50.854 0 00-.27-4.41h-.008l-1.41 4.41H2.45l-1.4-4.41h-.01a72.892 72.892 0 00-.195 4.41H0c.055-1.966.192-3.81.41-5.53h1.15l1.335 4.064h.008l1.347-4.064h1.095c.242 2.015.384 3.86.428 5.53zm4.017-4.08c-.378 2.045-.876 3.533-1.492 4.46-.482.716-1.01 1.073-1.583 1.073-.153 0-.34-.046-.566-.138v-.494c.11.017.24.026.386.026.268 0 .483-.075.647-.222.197-.18.295-.382.295-.605 0-.155-.077-.47-.23-.944L6.23 14.615h.91l.727 2.36c.164.536.233.91.21 1.123.376-.714.671-1.62.886-2.72zm7.878 4.08h-.814c-.195-2.098-.39-4.04-.584-5.83h-.773v5.83h-.69V13.384h-.047c-.084.18-.242.3-.474.36l-.165.04-.13.025-.05.01-.045.01c-.1.016-.193.024-.286.024-.073 0-.14-.004-.202-.012-.07-.01-.135-.025-.195-.046-.06-.022-.124-.05-.19-.087-.066-.035-.122-.08-.165-.133-.044-.055-.073-.122-.087-.2-.014-.08-.02-.174-.02-.283v-.41c0-.107.006-.2.02-.28.014-.08.043-.147.087-.2.043-.054.098-.1.165-.134.066-.036.13-.064.19-.086.06-.022.125-.037.195-.046.062-.008.13-.012.202-.012.093 0 .186.008.286.024l.05.01.13.024.165.04c.232.06.39.18.474.36h.047V13.05h1.137c.194 1.79.39 3.73.584 5.83z"/>
  </svg>
)

export default function ProviderSelector({ onSelect, onCancel }) {
  const [searchTerm, setSearchTerm] = useState('')
  const [selectedProvider, setSelectedProvider] = useState(null)

  // Filter providers based on search term
  const filteredProviders = PROVIDERS.filter(p =>
    p.fullName.toLowerCase().includes(searchTerm.toLowerCase()) ||
    p.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    p.description.toLowerCase().includes(searchTerm.toLowerCase()) ||
    p.dbType.toLowerCase().includes(searchTerm.toLowerCase())
  )

  // Group providers by database type
  const postgresProviders = filteredProviders.filter(p => p.dbType === 'postgresql')
  const mysqlProviders = filteredProviders.filter(p => p.dbType === 'mysql')

  const handleContinue = () => {
    if (selectedProvider) {
      onSelect(selectedProvider)
    }
  }

  const handleCardClick = (provider) => {
    setSelectedProvider(provider)
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
      <div className="bg-white rounded-lg max-w-6xl w-full max-h-[90vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="px-6 py-4 border-b border-gray-200">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-2xl font-bold text-gray-900">Select Database Provider</h2>
              <p className="text-sm text-gray-600 mt-1">
                Choose your database provider to auto-configure connection settings
              </p>
            </div>
            <button
              onClick={onCancel}
              className="text-gray-400 hover:text-gray-600 transition-colors"
            >
              <X size={24} />
            </button>
          </div>
        </div>

        {/* Search Bar */}
        <div className="px-6 py-4 border-b border-gray-200">
          <div className="relative">
            <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
              <Search size={20} className="text-gray-400" />
            </div>
            <input
              type="text"
              placeholder="Search providers (e.g., AWS, localhost, Docker)..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full pl-10 pr-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
          </div>
        </div>

        {/* Provider Grid - Scrollable */}
        <div className="flex-1 overflow-y-auto px-6 py-6">
          {filteredProviders.length === 0 ? (
            <div className="text-center py-12 text-gray-500">
              <p>No providers found matching "{searchTerm}"</p>
            </div>
          ) : (
            <div className="space-y-8">
              {/* PostgreSQL Section */}
              {postgresProviders.length > 0 && (
                <div>
                  <h3 className="text-lg font-semibold text-gray-700 mb-4 flex items-center gap-2">
                    <PostgreSQLIcon />
                    PostgreSQL Providers
                    <span className="text-sm font-normal text-gray-500">({postgresProviders.length})</span>
                  </h3>
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
                    {postgresProviders.map(provider => (
                      <ProviderCard
                        key={provider.id}
                        provider={provider}
                        selected={selectedProvider?.id === provider.id}
                        onClick={() => handleCardClick(provider)}
                      />
                    ))}
                  </div>
                </div>
              )}

              {/* MySQL Section */}
              {mysqlProviders.length > 0 && (
                <div>
                  <h3 className="text-lg font-semibold text-gray-700 mb-4 flex items-center gap-2">
                    <MySQLIcon />
                    MySQL Providers
                    <span className="text-sm font-normal text-gray-500">({mysqlProviders.length})</span>
                  </h3>
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
                    {mysqlProviders.map(provider => (
                      <ProviderCard
                        key={provider.id}
                        provider={provider}
                        selected={selectedProvider?.id === provider.id}
                        onClick={() => handleCardClick(provider)}
                      />
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Action Buttons */}
        <div className="px-6 py-4 border-t border-gray-200 bg-gray-50">
          <div className="flex items-center justify-between">
            <div className="text-sm text-gray-600">
              {selectedProvider ? (
                <span>
                  Selected: <span className="font-semibold">{selectedProvider.fullName}</span>
                </span>
              ) : (
                <span>Please select a provider to continue</span>
              )}
            </div>
            <div className="flex gap-3">
              <button
                onClick={onCancel}
                className="px-6 py-2 border border-gray-300 rounded-lg hover:bg-gray-100 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleContinue}
                disabled={!selectedProvider}
                className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                Continue
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
