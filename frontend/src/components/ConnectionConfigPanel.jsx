import { useState } from 'react'
import GeneralTab from './tabs/GeneralTab'
import SSHSSLTab from './tabs/SSHSSLTab'
import AdvancedTab from './tabs/AdvancedTab'
import OptionsTab from './tabs/OptionsTab'

const TABS = [
  { id: 'general', label: 'General' },
  { id: 'ssh-ssl', label: 'SSH/SSL' },
  { id: 'advanced', label: 'Advanced' },
  { id: 'options', label: 'Options' }
]

export default function ConnectionConfigPanel({
  selectedDatabase,
  formData,
  onFormDataChange,
  onSave,
  testConnection,
  testingConnection,
  testResult,
  isNewConnection
}) {
  const [activeTab, setActiveTab] = useState('general')

  if (!selectedDatabase && !isNewConnection) {
    return (
      <div className="h-full flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <p className="text-gray-500 mb-2">No connection selected</p>
          <p className="text-sm text-gray-400">
            Select a connection from the sidebar or create a new one
          </p>
        </div>
      </div>
    )
  }

  const handleSave = () => {
    // Validate required fields
    if (!formData.database_id) {
      alert('Database ID is required')
      return
    }
    if (!formData.database) {
      alert('Database name is required')
      return
    }
    if (!formData.username) {
      alert('Username is required')
      return
    }

    onSave()
  }

  const displayName = isNewConnection
    ? 'New Connection'
    : (selectedDatabase?.nickname || selectedDatabase?.database_id || 'Unknown')

  const dbTypeLabel = formData.db_type === 'postgresql' ? 'PostgreSQL' : 'MySQL'

  return (
    <div className="h-full flex flex-col bg-white">
      {/* Header */}
      <div className="px-6 py-4 border-b border-gray-200">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-gray-900">{displayName}</h2>
            <p className="text-sm text-gray-500 mt-0.5">{dbTypeLabel}</p>
          </div>
          <button
            onClick={handleSave}
            title={isNewConnection ? 'Save new database connection' : 'Update database connection settings'}
            className="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 transition-colors font-medium"
          >
            {isNewConnection ? 'Save' : 'Update'}
          </button>
        </div>
      </div>

      {/* Tab Navigation */}
      <div className="px-6 border-b border-gray-200">
        <div className="flex gap-6">
          {TABS.map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              title={
                tab.id === 'general' ? 'Basic connection settings' :
                tab.id === 'ssh-ssl' ? 'SSH tunneling and SSL certificates' :
                tab.id === 'advanced' ? 'Connection properties and pool settings' :
                'Transaction control and session options'
              }
              className={`py-3 text-sm font-medium border-b-2 transition-colors ${
                activeTab === tab.id
                  ? 'border-blue-600 text-blue-600'
                  : 'border-transparent text-gray-600 hover:text-gray-900'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* Tab Content */}
      <div className="flex-1 overflow-y-auto p-6">
        {activeTab === 'general' && (
          <GeneralTab
            formData={formData}
            onFormDataChange={onFormDataChange}
            testConnection={testConnection}
            testingConnection={testingConnection}
            testResult={testResult}
            isNewConnection={isNewConnection}
          />
        )}
        {activeTab === 'ssh-ssl' && <SSHSSLTab />}
        {activeTab === 'advanced' && <AdvancedTab />}
        {activeTab === 'options' && <OptionsTab />}
      </div>
    </div>
  )
}
