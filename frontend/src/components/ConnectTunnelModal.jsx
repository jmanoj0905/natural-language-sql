import { useState, useEffect } from 'react'
import axios from 'axios'
import { TUNNEL_ENDPOINTS } from '../config'

export default function ConnectTunnelModal({ onClose, onKeyGenerated }) {
  const [key, setKey] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const generateKey = async () => {
    setLoading(true)
    setError(null)
    try {
      const resp = await axios.post(TUNNEL_ENDPOINTS.generateKey)
      setKey(resp.data.key)
      onKeyGenerated(resp.data.key)
    } catch (err) {
      setError(err.response?.data?.detail?.message || 'Failed to generate key')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    generateKey()
  }, [])

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      style={{ background: 'rgba(26,28,29,0.6)' }}
      onClick={e => { if (e.target === e.currentTarget) onClose() }}
    >
      <div className="brutalist-border bg-white soft-shadow-lg rounded-2xl w-full max-w-lg mx-4 overflow-hidden">
        <div className="flex items-center justify-between px-6 py-4 border-b-2 border-border bg-[#f1f5f9]">
          <div className="flex items-center gap-3">
            <span className="material-symbols-outlined text-xl">hub</span>
            <h2 className="font-heading font-black text-xl uppercase tracking-tighter">Connect Local Database</h2>
          </div>
          <button onClick={onClose} className="material-symbols-outlined p-1.5 hover:bg-[#e2e8f0] rounded-full">
            close
          </button>
        </div>

        <div className="p-6 space-y-6">
          <div className="bg-info/20 border-2 border-border p-4 rounded-base">
            <h3 className="font-heading font-bold text-sm mb-2">How it works:</h3>
            <ol className="text-sm space-y-2 list-decimal list-inside">
              <li>Copy the command below</li>
              <li>Run it on your computer where the database is running</li>
              <li>Your local database will appear in the sidebar</li>
            </ol>
          </div>

          {error && (
            <div className="bg-danger/30 border-2 border-border p-3 rounded-base text-sm">
              {error}
            </div>
          )}

          {key ? (
            <div className="space-y-3">
              <label className="block text-sm font-heading font-bold uppercase">Run this command:</label>
              <div className="relative">
                <code className="block w-full bg-[#1a1c1d] text-success p-4 pr-20 rounded-base font-mono text-xs break-all">
                  nlsql-connector --key {key}
                </code>
                <button
                  onClick={() => navigator.clipboard.writeText(`nlsql-connector --key ${key}`)}
                  className="absolute right-2 top-1/2 -translate-y-1/2 material-symbols-outlined p-1.5 hover:bg-[#333] rounded text-white"
                  title="Copy command"
                >
                  content_copy
                </button>
              </div>

              <div className="flex gap-2">
                <button
                  onClick={generateKey}
                  disabled={loading}
                  className="px-4 py-2 border-2 border-border text-sm font-heading hover:bg-[#e2e8f0] rounded-base transition-colors"
                >
                  {loading ? 'Generating...' : 'Regenerate Key'}
                </button>
                <button
                  onClick={onClose}
                  className="flex-1 px-4 py-2 bg-[#1a1c1d] text-white text-sm font-heading hover:bg-[#333] rounded-base transition-colors"
                >
                  Done
                </button>
              </div>
            </div>
          ) : (
            <div className="text-center py-4">
              {loading ? (
                <span className="text-foreground/50">Generating key...</span>
              ) : (
                <button onClick={generateKey} className="px-4 py-2 bg-[#1a1c1d] text-white font-heading rounded-base">
                  Generate Key
                </button>
              )}
            </div>
          )}

          <div className="border-t-2 border-border pt-4">
            <h4 className="font-heading font-bold text-xs uppercase mb-2">Installation:</h4>
            <code className="block w-full bg-[#f8fafc] border border-border p-2 rounded-base font-mono text-xs">
              pip install nlsql-connector
            </code>
          </div>
        </div>
      </div>
    </div>
  )
}