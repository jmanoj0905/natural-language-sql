import { useState, useMemo } from 'react'
import axios from 'axios'
import { getLabel, DB_TYPE_LIST, getDefaults } from '../data/providers'
import DbIcon from './DbIcon'
import ConnectionForm from './ConnectionForm'
import DeleteConfirmDialog from './DeleteConfirmDialog'
import SchemaModal from './SchemaModal'
import { useToast } from '../hooks/useToast.jsx'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Dialog, DialogContent } from '@/components/ui/dialog'

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

  const groups = useMemo(() => {
    const g = {}
    filteredDbs.forEach(db => {
      const t = db.db_type || 'postgresql'
      if (!g[t]) g[t] = []
      g[t].push(db)
    })
    return g
  }, [filteredDbs])

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

  // ── Collapsed sidebar ────────────────────────────────────
  if (collapsed) {
    return (
      <div className="flex flex-col items-center py-4 gap-3 bg-sidebar text-foreground w-14 shrink-0 border-r-2 border-border">
        <Button variant="neutral" size="icon" onClick={onToggleCollapse} className="h-8 w-8" title="Expand sidebar">
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
          </svg>
        </Button>
        {databases.map(db => {
          const isSelected = selectedDbIds.includes(db.database_id)
          return (
            <button
              key={db.database_id}
              onClick={() => onSelectionChange(db.database_id)}
              title={db.nickname || db.database_id}
              className={`w-9 h-9 flex items-center justify-center transition-all duration-200 border-2 border-border rounded-base ${
                isSelected
                  ? 'bg-main shadow-shadow translate-x-0 translate-y-0'
                  : 'bg-secondary-background hover:translate-x-boxShadowX hover:translate-y-boxShadowY'
              }`}
            >
              <DbIcon dbType={db.db_type} className="w-4 h-4" />
            </button>
          )
        })}
        <button
          onClick={openNewForm}
          title="Add connection"
          className="w-9 h-9 flex items-center justify-center bg-secondary-background border-2 border-border rounded-base hover:bg-main transition-all duration-200 mt-auto mb-2"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
        </button>

        {(formMode === 'new' || formMode === 'edit') && (
          <FormModal formData={formData} setFormData={setFormData} formMode={formMode} testResult={testResult} testing={testing} saving={saving} onTest={handleTest} onSave={handleSave} onClose={closeForm} />
        )}
        {deleteTarget && <DeleteConfirmDialog database={deleteTarget} onConfirm={handleDelete} onCancel={() => setDeleteTarget(null)} />}
        {schemaTarget && <SchemaModal database={schemaTarget} onClose={() => setSchemaTarget(null)} />}
      </div>
    )
  }

  // ── Full sidebar ─────────────────────────────────────────
  return (
    <div className="flex flex-col bg-sidebar text-foreground w-64 shrink-0 overflow-hidden border-r-2 border-border">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-4 border-b-2 border-border">
        <span className="text-base font-heading uppercase tracking-wide text-white">Databases</span>
        <Button variant="neutral" size="icon" onClick={onToggleCollapse} className="h-7 w-7" title="Collapse sidebar">
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
        </Button>
      </div>

      {/* Search */}
      {databases.length > 0 && (
        <div className="px-3 pt-3 pb-1">
          <div className="relative">
            <svg className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-foreground" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
            <Input
              type="text"
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              placeholder="Search connections..."
              className="h-8 text-xs pl-8"
            />
          </div>
        </div>
      )}

      {/* DB list */}
      <div className="flex-1 overflow-y-auto px-3 py-2 space-y-2">
        {filteredDbs.length === 0 && (
          <p className="text-xs text-foreground/60 px-1 py-3 font-base">
            {databases.length === 0 ? 'No databases connected.' : 'No results.'}
          </p>
        )}

        {Object.entries(groups).map(([dbType, dbs]) => (
          <div key={dbType} className="space-y-2">
            <p className="text-xs font-heading uppercase tracking-wide text-foreground/60 px-1 pt-1 flex items-center gap-1.5">
              <DbIcon dbType={dbType} className="w-3 h-3" />
              {getLabel(dbType)}
            </p>
            {dbs.map(db => {
              const isSelected = selectedDbIds.includes(db.database_id)
              return (
                <div
                  key={db.database_id}
                  className={`group rounded-base border-2 border-border transition-all duration-200 cursor-pointer ${
                    isSelected
                      ? 'bg-main shadow-shadow'
                      : 'bg-secondary-background hover:translate-x-boxShadowX hover:translate-y-boxShadowY hover:shadow-none shadow-shadow'
                  }`}
                  onClick={() => onSelectionChange(db.database_id)}
                >
                  {/* Card top row */}
                  <div className="flex items-center gap-2.5 px-3 py-2.5">
                    <div className="w-8 h-8 flex items-center justify-center border-2 border-border rounded-base bg-background shrink-0">
                      <DbIcon dbType={db.db_type} className="w-4 h-4" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-heading truncate leading-tight">
                        {db.nickname || db.database_id}
                      </p>
                      <div className="flex items-center gap-1.5 mt-0.5">
                        <div className={`w-1.5 h-1.5 rounded-full shrink-0 ${db.is_connected ? 'bg-success' : 'bg-danger'}`} />
                        <span className="text-[10px] text-foreground/50 font-mono truncate">
                          {db.host}:{db.port}/{db.database}
                        </span>
                      </div>
                    </div>
                    {db.table_count != null && (
                      <span className="text-[10px] text-foreground/50 font-mono shrink-0 bg-background border border-border rounded-base px-1 py-0.5">
                        {db.table_count}t
                      </span>
                    )}
                  </div>

                  {/* Card action row — visible on hover */}
                  <div className="flex items-center gap-1 px-2 pb-2 opacity-0 group-hover:opacity-100 transition-opacity" onClick={e => e.stopPropagation()}>
                    <button onClick={() => setSchemaTarget(db)} className="flex items-center gap-1 px-2 py-1 text-[10px] font-heading bg-background border border-border rounded-base hover:bg-main transition-colors" title="View schema">
                      <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 10h18M3 14h18M10 3v18M14 3v18" /></svg>
                      SCHEMA
                    </button>
                    <button onClick={() => openEditForm(db)} className="flex items-center gap-1 px-2 py-1 text-[10px] font-heading bg-background border border-border rounded-base hover:bg-main transition-colors" title="Edit connection">
                      <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" /></svg>
                      EDIT
                    </button>
                    <button onClick={() => setDeleteTarget(db)} className="flex items-center gap-1 px-2 py-1 text-[10px] font-heading bg-background border border-border rounded-base hover:bg-danger hover:text-secondary-background transition-colors ml-auto" title="Remove connection">
                      <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>
                      DEL
                    </button>
                  </div>
                </div>
              )
            })}
          </div>
        ))}
      </div>

      {/* Add Connection */}
      <div className="p-3 border-t-2 border-border">
        <Button variant="neutral" className="w-full" onClick={openNewForm}>
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          ADD CONNECTION
        </Button>
      </div>

      {(formMode === 'new' || formMode === 'edit') && (
        <FormModal formData={formData} setFormData={setFormData} formMode={formMode} testResult={testResult} testing={testing} saving={saving} onTest={handleTest} onSave={handleSave} onClose={closeForm} />
      )}
      {schemaTarget && <SchemaModal database={schemaTarget} onClose={() => setSchemaTarget(null)} />}
      {deleteTarget && <DeleteConfirmDialog database={deleteTarget} onConfirm={handleDelete} onCancel={() => setDeleteTarget(null)} />}
    </div>
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
