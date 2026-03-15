import { useState, useEffect } from 'react'
import axios from 'axios'
import { getEmoji, getLabel } from '../data/providers'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Alert, AlertDescription } from '@/components/ui/alert'

const API_BASE = '/api/v1'

export default function SchemaModal({ database, onClose }) {
  const [schema, setSchema] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [expandedTables, setExpandedTables] = useState({})

  useEffect(() => {
    const fetchSchema = async () => {
      try {
        const resp = await axios.get(`${API_BASE}/schema`, {
          params: { database_id: database.database_id },
        })
        setSchema(resp.data)
        if (resp.data.tables?.length <= 5) {
          const expanded = {}
          resp.data.tables.forEach(t => { expanded[t.name] = true })
          setExpandedTables(expanded)
        }
      } catch (err) {
        setError(err.response?.data?.detail?.message || err.message)
      } finally {
        setLoading(false)
      }
    }
    fetchSchema()
  }, [database.database_id])

  const toggleTable = (name) => {
    setExpandedTables(prev => ({ ...prev, [name]: !prev[name] }))
  }

  const expandAll = () => {
    const expanded = {}
    schema?.tables?.forEach(t => { expanded[t.name] = true })
    setExpandedTables(expanded)
  }

  const collapseAll = () => setExpandedTables({})

  return (
    <Dialog open={true} onOpenChange={(open) => { if (!open) onClose() }}>
      <DialogContent className="max-w-2xl max-h-[85vh] flex flex-col p-0">
        {/* Header */}
        <DialogHeader className="px-6 pt-6 pb-4 border-b-2 border-border">
          <DialogTitle className="flex items-center gap-2">
            <span className="text-xl">{getEmoji(database.db_type)}</span>
            {database.nickname || database.database_id}
          </DialogTitle>
          <DialogDescription>
            {getLabel(database.db_type)} · {database.host}:{database.port} · <span className="font-mono">{database.database}</span>
          </DialogDescription>
        </DialogHeader>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-6 py-4">
          {loading && (
            <div className="flex items-center justify-center py-12 text-foreground/40">
              <svg className="animate-spin h-6 w-6 mr-3" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
              </svg>
              Loading schema...
            </div>
          )}

          {error && (
            <Alert className="bg-danger/20">
              <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
              </svg>
              <AlertDescription>
                <p className="font-heading mb-1">Could not load schema</p>
                <p>{error}</p>
              </AlertDescription>
            </Alert>
          )}

          {schema && !loading && (
            <>
              {/* Summary row */}
              <div className="flex items-center justify-between mb-4">
                <p className="text-sm text-foreground/60 font-base">
                  <span className="font-heading text-foreground">{schema.table_count}</span>{' '}
                  {schema.table_count === 1 ? 'table' : 'tables'}
                </p>
                {schema.tables?.length > 0 && (
                  <div className="flex gap-3 text-xs font-heading text-foreground">
                    <button onClick={expandAll} className="hover:text-info">EXPAND ALL</button>
                    <button onClick={collapseAll} className="hover:text-info">COLLAPSE ALL</button>
                  </div>
                )}
              </div>

              {/* Tables */}
              <div className="space-y-2">
                {schema.tables?.map(table => (
                  <div key={table.name} className="border-2 border-border rounded-base shadow-shadow overflow-hidden">
                    {/* Table header row */}
                    <button
                      onClick={() => toggleTable(table.name)}
                      className="w-full flex items-center justify-between px-4 py-2.5 bg-main/10 hover:bg-main/20 transition-colors text-left"
                    >
                      <div className="flex items-center gap-2">
                        <svg
                          className={`w-3.5 h-3.5 text-foreground transition-transform flex-shrink-0 ${
                            expandedTables[table.name] ? 'rotate-90' : ''
                          }`}
                          fill="none" stroke="currentColor" viewBox="0 0 24 24"
                        >
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                        </svg>
                        <span className="font-mono text-sm font-heading text-foreground">{table.name}</span>
                      </div>
                      <span className="text-xs text-foreground/50 font-heading flex-shrink-0">
                        {table.column_count ?? table.columns?.length ?? 0} columns
                      </span>
                    </button>

                    {/* Columns */}
                    {expandedTables[table.name] && table.columns?.length > 0 && (
                      <div className="divide-y divide-foreground/10">
                        {table.columns.map(col => (
                          <div key={col.name} className="flex items-center gap-3 px-4 py-2 text-sm">
                            {/* PK badge */}
                            <div className="w-4 flex-shrink-0 flex justify-center">
                              {col.primary_key && (
                                <span title="Primary key">
                                  <svg className="w-3.5 h-3.5 text-main" fill="currentColor" viewBox="0 0 20 20">
                                    <path fillRule="evenodd" d="M18 8a6 6 0 01-7.743 5.743L10 14l-1 1-1 1H6v2H2v-4l4.257-4.257A6 6 0 1118 8zm-6-4a1 1 0 100 2 2 2 0 012 2 1 1 0 102 0 4 4 0 00-4-4z" clipRule="evenodd" />
                                  </svg>
                                </span>
                              )}
                            </div>

                            {/* Column name */}
                            <span className="font-mono text-foreground flex-1 truncate">{col.name}</span>

                            {/* Type */}
                            <Badge variant="neutral" className="bg-info/20 text-xs font-mono px-1.5 py-0.5">
                              {col.type}
                            </Badge>

                            {/* Nullable indicator */}
                            <span className={`text-xs flex-shrink-0 font-heading ${
                              col.nullable ? 'text-foreground/40' : 'text-foreground'
                            }`}>
                              {col.nullable ? 'null' : 'not null'}
                            </span>
                          </div>
                        ))}
                      </div>
                    )}

                    {expandedTables[table.name] && (!table.columns || table.columns.length === 0) && (
                      <p className="px-4 py-2 text-xs text-foreground/40 font-base">No column info available.</p>
                    )}
                  </div>
                ))}
              </div>

              {schema.tables?.length === 0 && (
                <p className="text-sm text-foreground/50 text-center py-8 font-heading">No tables found in this database.</p>
              )}
            </>
          )}
        </div>

        {/* Footer */}
        <DialogFooter className="px-6 py-3 border-t-2 border-border">
          <Button variant="neutral" onClick={onClose}>CLOSE</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
