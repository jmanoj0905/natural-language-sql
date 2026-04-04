export const API_BASE = 'https://natural-language-sql-ue9l.onrender.com/api/v1'

export const TUNNEL_ENDPOINTS = {
  generateKey: `${API_BASE}/tunnel/generate-key`,
  status: `${API_BASE}/tunnel/status`,
  heartbeat: `${API_BASE}/tunnel/heartbeat`,
  disconnect: `${API_BASE}/tunnel/disconnect`,
  availableDatabases: `${API_BASE}/tunnel/available-databases`,
}
