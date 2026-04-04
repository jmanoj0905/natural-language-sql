import { useState, useEffect } from 'react'
import axios from 'axios'
import { TUNNEL_ENDPOINTS } from '../config'

export default function TunnelStatus({ onConnectNew }) {
  const [machines, setMachines] = useState([])
  const [loading, setLoading] = useState(true)

  const fetchStatus = async () => {
    try {
      const resp = await axios.get(TUNNEL_ENDPOINTS.status)
      setMachines(resp.data.machines || [])
    } catch (err) {
      console.error('Failed to fetch tunnel status:', err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchStatus()
    const interval = setInterval(fetchStatus, 10000)
    return () => clearInterval(interval)
  }, [])

  const handleDisconnect = async (key) => {
    try {
      await axios.post(TUNNEL_ENDPOINTS.disconnect, { key })
      fetchStatus()
    } catch (err) {
      console.error('Failed to disconnect:', err)
    }
  }

  if (loading) {
    return (
      <div className="p-4 text-center text-foreground/50 text-sm">
        Checking connections...
      </div>
    )
  }

  if (machines.length === 0) {
    return (
      <div className="p-4 space-y-3">
        <div className="text-center py-4">
          <span className="material-symbols-outlined text-3xl text-foreground/30">hub</span>
          <p className="text-sm text-foreground/50 mt-2">No local databases connected</p>
        </div>
        <button
          onClick={onConnectNew}
          className="w-full py-2 bg-[#1a1c1d] text-white font-heading text-sm rounded-base hover:bg-[#333] transition-colors"
        >
          Connect Local Database
        </button>
      </div>
    )
  }

  return (
    <div className="p-4 space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="font-heading font-bold text-xs uppercase tracking-wider">Connected Machines</h3>
        <button
          onClick={onConnectNew}
          className="material-symbols-outlined text-sm hover:bg-[#e2e8f0] p-1 rounded"
        >
          add
        </button>
      </div>

      {machines.map((machine) => (
        <div key={machine.machine_id} className="border-2 border-border rounded-base p-3 space-y-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className={`w-2 h-2 rounded-full ${machine.is_connected ? 'bg-success' : 'bg-danger'}`} />
              <span className="font-mono text-xs">{machine.machine_id}</span>
            </div>
            <button
              onClick={() => handleDisconnect(machine.key)}
              className="text-xs text-danger hover:underline"
            >
              Disconnect
            </button>
          </div>

          <div className="space-y-1">
            {machine.databases?.map((db) => (
              <div key={db.database_id} className="flex items-center gap-2 text-xs text-foreground/70 pl-4">
                <span className="material-symbols-outlined text-sm">storage</span>
                <span>{db.name}</span>
                <span className="text-foreground/40">({db.db_type})</span>
              </div>
            ))}
          </div>

          <div className="text-xs text-foreground/30">
            Connected {new Date(machine.connected_at).toLocaleString()}
          </div>
        </div>
      ))}
    </div>
  )
}