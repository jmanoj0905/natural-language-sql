import { useState, useMemo } from 'react'
import axios from 'axios'
import { getLabel, DB_TYPE_LIST, getDefaults } from '../data/providers'
import DbIcon from './DbIcon'
import ConnectionForm from './ConnectionForm'
import DeleteConfirmDialog from './DeleteConfirmDialog'
import SchemaModal from './SchemaModal'
import { useToast } from '../hooks/useToast.jsx'
import { Dialog, DialogContent } from '@/components/ui/dialog'
import { API_BASE } from '../config'

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
}) {
  const { showSuccess, showError } = useToast()
  const [searchQuery, setSearchQuery] = useState('')
  const [formMode, setFormMode] = useState(null)
  const [formData, setFormData] = useState(EMPTY_FORM)
  const [editingId, setEditingId] = useState(null)
  const [testResult, setTestResult] = useState(null)
  const [testing, setTesting] = useState(false)
  const [saving, setSaving] = useState(false)
  const [schemaTarget, setSchemaTarget] = useState(null)
  const [deleteTarget, setDeleteTarget] = useState(null)

  const filteredDbs = useMemo(() => {
    if (!searchQuery.trim()) return databases
    const q = searchQuery.toLowerCase()
    return databases.filter(db =>
      (db.nickname || '').toLowerCase().includes(q) ||
      db.database_id.toLowerCase().includes(q) ||
      (db.database || '').toLowerCase().includes(q) ||
      (db.host || '').toLowerCase().includes(q)
    )
  }, [databases, searchQuery])

  const openNewForm = () => {
    const defaults = getDefaults('postgresql') || {}
    setFormData({ ...EMPTY_FORM, ...defaults, db_type: 'postgresql' })
    setEditingId(null)
    setTestResult(null)
    setFormMode('new')
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
    setSaving(false)
    setTesting(false)
  }

  const handleTest = async () => {
    setTesting(true)
    setTestResult(null)
    try {
      const payload = { ...formData }
      if (!formData.password && formMode === 'edit') payload.password = '__KEEP__'
      const resp = await axios.post(`${API_BASE}/databases/test`, payload)
      setTestResult({ success: true, info: resp.data.database_info })
    } catch (err) {
      setTestResult({
        success: false,
        error: err.response?.data?.detail?.message || err.response?.data?.detail || err.message,
      })
    } finally {
      setTesting(false)
    }
  }

  const handleSave = async () => {
    setSaving(true)
    setTesting(true)
    setTestResult(null)
    try {
      const testPayload = { ...formData }
      if (!formData.password && formMode === 'edit') testPayload.password = '__KEEP__'
      const resp = await axios.post(`${API_BASE}/databases/test`, testPayload)
      setTestResult({ success: true, info: resp.data.database_info })
    } catch (err) {
      setTestResult({
        success: false,
        error: err.response?.data?.detail?.message || err.response?.data?.detail || err.message,
      })
      setTesting(false)
      setSaving(false)
      return
    }
    setTesting(false)
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

  return (
    <aside className="flex flex-col fixed left-0 top-16 bottom-0 z-40 bg-white border-r-2 border-border h-[calc(100vh-64px)] w-64 p-6 gap-6 overflow-y-auto">
      {/* Header */}
      <div className="flex flex-col gap-1">
        <h2 className="font-heading font-bold text-foreground text-lg">Databases</h2>
        <p className="font-label font-medium text-xs text-foreground/60 uppercase tracking-widest">Connected Engines</p>
      </div>

      {/* Connect New */}
      <button
        onClick={openNewForm}
        data-action="connect-new"
        className="w-full brutalist-border bg-main py-3 rounded-xl font-heading font-black uppercase tracking-widest soft-shadow active-press hover:bg-[#d8b4fe] transition-all text-sm"
      >
        Connect New
      </button>

      {/* Search */}
      {databases.length > 3 && (
        <div className="relative">
          <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-foreground/40 text-sm">search</span>
          <input
            type="text"
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            placeholder="Search..."
            className="w-full pl-9 pr-3 py-2 brutalist-border rounded-xl font-label text-sm focus:ring-2 focus:ring-main outline-none bg-background"
          />
        </div>
      )}

      {/* Database list */}
      <nav className="flex flex-col gap-2 flex-1">
        {filteredDbs.length === 0 && (
          <p className="text-xs text-foreground/40 font-label px-1 py-3">
            {databases.length === 0 ? 'No databases connected yet.' : 'No results.'}
          </p>
        )}
        {filteredDbs.map(db => {
          const isSelected = selectedDbIds.includes(db.database_id)
          return (
            <div key={db.database_id} className="group">
              <button
                onClick={() => onSelectionChange(db.database_id)}
                className={`flex items-center gap-3 w-full p-3 rounded-xl font-label font-medium text-sm transition-all ${
                  isSelected
                    ? 'bg-[#7d4e58] text-white brutalist-border soft-shadow active:translate-x-[1px] active:translate-y-[1px] active:shadow-none'
                    : 'text-foreground hover:bg-[#f1f5f9]'
                }`}
              >
                <DbIcon dbType={db.db_type} className={`w-4 h-4 ${isSelected ? 'text-white' : ''}`} />
                <span className="truncate flex-1 text-left">{db.nickname || db.database_id}</span>
                <div className={`w-2 h-2 rounded-full shrink-0 ${db.is_connected ? 'bg-[#86EFAC]' : 'bg-[#fca5a5]'}`} />
              </button>
              {/* Hover actions */}
              <div className="flex items-center gap-1 px-2 pt-1 opacity-0 group-hover:opacity-100 transition-opacity" onClick={e => e.stopPropagation()}>
                <button onClick={() => setSchemaTarget(db)} className="px-2 py-0.5 text-[10px] font-heading uppercase hover:bg-main/40 rounded-lg transition-colors">Schema</button>
                <button onClick={() => openEditForm(db)} className="px-2 py-0.5 text-[10px] font-heading uppercase hover:bg-main/40 rounded-lg transition-colors">Edit</button>
                <button onClick={() => setDeleteTarget(db)} className="px-2 py-0.5 text-[10px] font-heading uppercase hover:bg-danger rounded-lg transition-colors ml-auto">Del</button>
              </div>
            </div>
          )
        })}
      </nav>

      {/* Modals */}
      {(formMode === 'new' || formMode === 'edit') && (
        <FormModal formData={formData} setFormData={setFormData} formMode={formMode} testResult={testResult} testing={testing} saving={saving} onTest={handleTest} onSave={handleSave} onClose={closeForm} />
      )}
      {schemaTarget && <SchemaModal database={schemaTarget} onClose={() => setSchemaTarget(null)} />}
      {deleteTarget && <DeleteConfirmDialog database={deleteTarget} onConfirm={handleDelete} onCancel={() => setDeleteTarget(null)} />}
    </aside>
  )
}

function FormModal({ formData, setFormData, formMode, testResult, testing, saving, onTest, onSave, onClose }) {
  return (
    <Dialog open={true} onOpenChange={(open) => { if (!open) onClose() }}>
      <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto p-0">
        <ConnectionForm
          formData={formData}
          onChange={setFormData}
          onTest={onTest}
          onSave={onSave}
          testResult={testResult}
          testing={testing}
          saving={saving}
          isNew={formMode === 'new'}
        />
      </DialogContent>
    </Dialog>
  )
}
