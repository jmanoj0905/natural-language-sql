import { useState, useEffect } from 'react'
import axios from 'axios'
import { TUNNEL_ENDPOINTS } from '../config'

export default function TunnelDatabaseSelector({ onClose, onDatabasesSelected }) {
  const [machines, setMachines] = useState([])
  const [loading, setLoading] = useState(true)
  const [selectedDbs, setSelectedDbs] = useState({})

  const fetchMachines = async () => {
    try {
      const resp = await axios.get(TUNNEL_ENDPOINTS.status)
      setMachines(resp.data.machines || [])
      
      // Default: select all databases
      const allSelected = {}
      resp.data.machines?.forEach(machine => {
        machine.databases?.forEach(db => {
          allSelected[db.database_id] = true
        })
      })
      setSelectedDbs(allSelected)
    } catch (err) {
      console.error('Failed to fetch machines:', err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchMachines()
  }, [])

  const toggleDb = (dbId) => {
    setSelectedDbs(prev => ({
      ...prev,
      [dbId]: !prev[dbId]
    }))
  }

  const handleConfirm = () => {
    const selected = Object.entries(selectedDbs)
      .filter(([_, selected]) => selected)
      .map(([dbId, _]) => dbId)
    onDatabasesSelected(selected)
    onClose()
  }

  if (loading) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center" style={{ background: 'rgba(26,28,29,0.6)' }}>
        <div className="brutalist-border bg-white p-8 rounded-2xl">
          <span className="text-foreground/50">Loading databases...</span>
        </div>
      </div>
    )
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      style={{ background: 'rgba(26,28,29,0.6)' }}
      onClick={e => { if (e.target === e.currentTarget) onClose() }}
    >
      <div className="brutalist-border bg-white soft-shadow-lg rounded-2xl w-full max-w-md mx-4 overflow-hidden">
        <div className="flex items-center justify-between px-6 py-4 border-b-2 border-border bg-[#f1f5f9]">
          <div className="flex items-center gap-3">
            <span className="material-symbols-outlined text-xl text-main">inventory_2</span>
            <h2 className="font-heading font-black text-xl uppercase tracking-tighter">Select Databases</h2>
          </div>
        </div>

        <div className="p-6 space-y-4">
          <p className="text-sm text-foreground/70">
            Select which databases from your machine to add to NLSQL:
          </p>

          {machines.map(machine => (
            <div key={machine.machine_id} className="space-y-2">
              <div className="flex items-center gap-2 text-xs font-heading font-bold uppercase text-foreground/50">
                <span className="w-2 h-2 rounded-full bg-success" />
                {machine.machine_id}
              </div>
              <div className="space-y-1 pl-4">
                {machine.databases?.map(db => (
                  <label
                    key={db.database_id}
                    className="flex items-center gap-3 p-2 rounded-base hover:bg-[#f1f5f9] cursor-pointer"
                  >
                    <input
                      type="checkbox"
                      checked={selectedDbs[db.database_id] || false}
                      onChange={() => toggleDb(db.database_id)}
                      className="w-4 h-4 rounded accent-main"
                    />
                    <span className="font-label text-sm">{db.name}</span>
                    <span className="text-xs text-foreground/40">({db.db_type})</span>
                  </label>
                ))}
              </div>
            </div>
          ))}

          <div className="flex gap-2 pt-4">
            <button
              onClick={onClose}
              className="px-4 py-2 border-2 border-border text-sm font-heading hover:bg-[#e2e8f0] rounded-base transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleConfirm}
              className="flex-1 px-4 py-2 bg-main text-white text-sm font-heading hover:bg-[#d8b4fe] rounded-base transition-colors"
            >
              Add Selected
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}