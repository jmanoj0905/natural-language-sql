import { useState } from 'react'
import axios from 'axios'
import { getEmoji, getLabel, DB_TYPE_LIST, getDefaults } from '../data/providers'
import ConnectionForm from './ConnectionForm'
import DeleteConfirmDialog from './DeleteConfirmDialog'
import { useToast } from '../hooks/useToast.jsx'

const API_BASE = '/api/v1'

const EMPTY_FORM = {
  database_id: '',
  nickname: '',
  db_type: 'postgresql',
  host: 'localhost',
  port: 5432,
  database: '',
  username: 'postgres',
  password: '',
  ssl_mode: 'disable',
}

export default function AppSidebar({
  databases,
  selectedDbIds,
  onSelectionChange,
  onDatabasesChanged,
  collapsed,
  onToggleCollapse,
}) {
  const { showSuccess, showError } = useToast()

  // Schema expansion state: { [db_id]: { open: bool, tables: [], loading: bool } }
  const [schemaState, setSchemaState] = useState({})

  // Form state
  const [formMode, setFormMode] = useState(null) // null | 'new' | 'edit'
  const [formData, setFormData] = useState(EMPTY_FORM)
  const [editingId, setEditingId] = useState(null)
  const [testResult, setTestResult] = useState(null)
  const [testing, setTesting] = useState(false)
  const [saving, setSaving] = useState(false)

  // Delete dialog
  const [deleteTarget, setDeleteTarget] = useState(null)

  // Provider selector for new connection
  const [newDbType, setNewDbType] = useState(null) // null = show type picker

  // Group databases by type
  const groups = {}
  databases.forEach(db => {
    const t = db.db_type || 'postgresql'
    if (!groups[t]) groups[t] = []
    groups[t].push(db)
  })

  const handleToggleSchema = async (db) => {
    const id = db.database_id
    const cur = schemaState[id]

    if (cur?.open) {
      setSchemaState(prev => ({ ...prev, [id]: { ...prev[id], open: false } }))
      return
    }

    if (cur?.tables) {
      setSchemaState(prev => ({ ...prev, [id]: { ...prev[id], open: true } }))
      return
    }

    setSchemaState(prev => ({ ...prev, [id]: { open: true, tables: [], loading: true } }))
    try {
      const resp = await axios.get(`${API_BASE}/schema`, { params: { database_id: id } })
      const tables = resp.data?.tables || []
      setSchemaState(prev => ({ ...prev, [id]: { open: true, tables, loading: false } }))
    } catch {
      setSchemaState(prev => ({ ...prev, [id]: { open: true, tables: [], loading: false } }))
    }
  }

  const openNewForm = (dbType) => {
    const defaults = getDefaults(dbType) || {}
    setFormData({ ...EMPTY_FORM, ...defaults, db_type: dbType })
    setEditingId(null)
    setTestResult(null)
    setFormMode('new')
    setNewDbType(null)
  }

  const openEditForm = (db) => {
    setFormData({
      database_id: db.database_id,
      nickname: db.nickname || '',
      db_type: db.db_type || 'postgresql',
      host: db.host || '',
      port: db.port || 5432,
      database: db.database || '',
      username: db.username || '',
      password: '',
      ssl_mode: db.ssl_mode || 'disable',
    })
    setEditingId(db.database_id)
    setTestResult(null)
    setFormMode('edit')
  }

  const closeForm = () => {
    setFormMode(null)
    setEditingId(null)
    setTestResult(null)
    setNewDbType(null)
  }

  const handleTest = async () => {
    setTesting(true)
    setTestResult(null)
    try {
      const payload = { ...formData }
      if (!formData.password && formMode === 'edit') {
        payload.password = '__KEEP__'
      }
      const resp = await axios.post(`${API_BASE}/databases/test`, payload)
      setTestResult({ success: true, info: resp.data })
    } catch (err) {
      setTestResult({
        success: false,
        error: err.response?.data?.detail?.message || err.response?.data?.detail || err.message
      })
    } finally {
      setTesting(false)
    }
  }

  const handleSave = async () => {
    setSaving(true)
    try {
      if (formMode === 'new') {
        await axios.post(`${API_BASE}/databases`, formData)
        showSuccess('Connection saved')
      } else {
        const payload = { ...formData }
        if (!payload.password) delete payload.password
        await axios.put(`${API_BASE}/databases/${editingId}`, payload)
        showSuccess('Connection updated')
      }
      closeForm()
      onDatabasesChanged()
    } catch (err) {
      showError(err.response?.data?.detail?.message || err.response?.data?.detail || err.message)
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (db_id) => {
    try {
      await axios.delete(`${API_BASE}/databases/${db_id}`)
      showSuccess('Connection removed')
      setDeleteTarget(null)
      onDatabasesChanged()
    } catch (err) {
      showError(err.response?.data?.detail?.message || err.message)
    }
  }

  if (collapsed) {
    return (
      <div className="flex flex-col items-center py-4 gap-3 bg-gray-900 text-white w-14 flex-shrink-0">
        <button
          onClick={onToggleCollapse}
          className="p-2 hover:bg-gray-700 rounded-lg transition-colors"
          title="Expand sidebar"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
          </svg>
        </button>
        {databases.map(db => (
          <button
            key={db.database_id}
            onClick={() => onSelectionChange(db.database_id)}
            title={db.nickname || db.database_id}
            className={`w-9 h-9 rounded-lg flex items-center justify-center text-base transition-colors ${
              selectedDbIds.includes(db.database_id)
                ? 'bg-blue-600'
                : 'hover:bg-gray-700'
            }`}
          >
            {getEmoji(db.db_type)}
          </button>
        ))}
      </div>
    )
  }

  return (
    <div className="flex flex-col bg-gray-900 text-white w-64 flex-shrink-0 overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-4 border-b border-gray-700">
        <span className="text-sm font-semibold text-gray-200 uppercase tracking-wide">Databases</span>
        <button
          onClick={onToggleCollapse}
          className="p-1 hover:bg-gray-700 rounded transition-colors"
          title="Collapse sidebar"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
        </button>
      </div>

      {/* Database list */}
      <div className="flex-1 overflow-y-auto py-2">
        {Object.keys(groups).length === 0 && (
          <p className="text-xs text-gray-400 px-4 py-3">No databases connected.</p>
        )}

        {Object.entries(groups).map(([dbType, dbs]) => (
          <div key={dbType} className="mb-3">
            <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide px-4 py-1">
              {getEmoji(dbType)} {getLabel(dbType)}
            </p>
            {dbs.map(db => {
              const isSelected = selectedDbIds.includes(db.database_id)
              const schemaInfo = schemaState[db.database_id]
              return (
                <div key={db.database_id}>
                  <div
                    className={`group flex items-center gap-2 px-3 py-2 mx-1 rounded-lg cursor-pointer transition-colors ${
                      isSelected ? 'bg-blue-600' : 'hover:bg-gray-700'
                    }`}
                  >
                    {/* Status dot */}
                    <div
                      className={`w-2 h-2 rounded-full flex-shrink-0 ${
                        db.is_connected ? 'bg-green-400' : 'bg-red-400'
                      }`}
                    />

                    {/* Name — click to select */}
                    <span
                      className="flex-1 text-sm truncate"
                      onClick={() => onSelectionChange(db.database_id)}
                    >
                      {db.nickname || db.database_id}
                    </span>

                    {/* Table count */}
                    {db.table_count != null && (
                      <span className="text-xs text-gray-400 group-hover:text-gray-300">
                        {db.table_count}t
                      </span>
                    )}

                    {/* Schema expand */}
                    <button
                      onClick={() => handleToggleSchema(db)}
                      className="opacity-0 group-hover:opacity-100 p-0.5 hover:bg-gray-600 rounded transition-all"
                      title="View tables"
                    >
                      <svg
                        className={`w-3 h-3 transition-transform ${schemaInfo?.open ? 'rotate-90' : ''}`}
                        fill="none" stroke="currentColor" viewBox="0 0 24 24"
                      >
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                      </svg>
                    </button>

                    {/* Edit */}
                    <button
                      onClick={() => openEditForm(db)}
                      className="opacity-0 group-hover:opacity-100 p-0.5 hover:bg-gray-600 rounded transition-all"
                      title="Edit connection"
                    >
                      <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
                      </svg>
                    </button>

                    {/* Delete */}
                    <button
                      onClick={() => setDeleteTarget(db)}
                      className="opacity-0 group-hover:opacity-100 p-0.5 hover:bg-red-600 rounded transition-all"
                      title="Remove connection"
                    >
                      <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                      </svg>
                    </button>
                  </div>

                  {/* Schema tree */}
                  {schemaInfo?.open && (
                    <div className="ml-6 mr-2 mb-1">
                      {schemaInfo.loading ? (
                        <p className="text-xs text-gray-400 px-2 py-1">Loading...</p>
                      ) : schemaInfo.tables.length === 0 ? (
                        <p className="text-xs text-gray-400 px-2 py-1">No tables found</p>
                      ) : (
                        schemaInfo.tables.map(t => (
                          <div key={t.name} className="flex items-center gap-1.5 px-2 py-0.5 text-xs text-gray-400">
                            <svg className="w-3 h-3 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 10h18M3 14h18M10 3v18M14 3v18" />
                            </svg>
                            <span className="truncate">{t.name}</span>
                            {t.column_count != null && (
                              <span className="text-gray-500 ml-auto flex-shrink-0">{t.column_count}c</span>
                            )}
                          </div>
                        ))
                      )}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        ))}
      </div>

      {/* Add Connection button */}
      {formMode === null && newDbType === null && (
        <div className="p-3 border-t border-gray-700">
          <button
            onClick={() => setNewDbType('picker')}
            className="w-full flex items-center justify-center gap-2 px-3 py-2 text-sm text-gray-300 border border-gray-600 rounded-lg hover:bg-gray-700 hover:text-white transition-colors"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
            Add Connection
          </button>
        </div>
      )}

      {/* DB type picker for new connection */}
      {newDbType === 'picker' && (
        <div className="p-3 border-t border-gray-700">
          <p className="text-xs text-gray-400 mb-2">Select database type:</p>
          <div className="space-y-1">
            {DB_TYPE_LIST.map(t => (
              <button
                key={t.id}
                onClick={() => openNewForm(t.id)}
                className="w-full text-left px-3 py-2 text-sm text-gray-200 hover:bg-gray-700 rounded-lg transition-colors"
              >
                {t.emoji} {t.label}
              </button>
            ))}
          </div>
          <button
            onClick={() => setNewDbType(null)}
            className="mt-2 w-full text-xs text-gray-500 hover:text-gray-300 transition-colors"
          >
            Cancel
          </button>
        </div>
      )}

      {/* Inline connection form overlay */}
      {(formMode === 'new' || formMode === 'edit') && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-60">
          <div className="bg-white rounded-xl shadow-2xl w-full max-w-lg max-h-[90vh] overflow-y-auto relative">
            <button
              onClick={closeForm}
              className="absolute top-4 right-4 text-gray-400 hover:text-gray-600 transition-colors"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
            <ConnectionForm
              formData={formData}
              onChange={setFormData}
              onTest={handleTest}
              onSave={handleSave}
              testResult={testResult}
              testing={testing}
              saving={saving}
              isNew={formMode === 'new'}
            />
          </div>
        </div>
      )}

      {/* Delete confirm dialog */}
      {deleteTarget && (
        <DeleteConfirmDialog
          database={deleteTarget}
          onConfirm={handleDelete}
          onCancel={() => setDeleteTarget(null)}
        />
      )}
    </div>
  )
}
