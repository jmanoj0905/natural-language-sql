# Local Database Connector Implementation Plan

## Overview

Enable users to securely connect their local databases (PostgreSQL, MySQL) to the cloud-based NLSQL backend without requiring login. Users run a local agent (`nlsql-connector`) that establishes a secure WebSocket tunnel to the backend.

## Architecture

```
┌──────────────────────┐                    ┌──────────────────────────────┐
│  User's Machine(s)  │                    │       Cloud Backend         │
│                      │                    │        (Render)             │
│  ┌────────────────┐  │   WebSocket        │                              │
│  │nlsql-connector│◄─┼────────────────────┼────────┐                     │
│  │  (auto-disc) │  │   Tunnel            │        │                     │
│  │  - Postgres   │  │                     │        ▼                    │
│  │  - MySQL      │  │                     │  ┌────────────────────┐    │
│  └───────┬────────┘  │                     │  │ Key Registry       │    │
│          │           │                     │  │ (key → machine_id) │    │
│          │           │                     │  └────────────────────┘    │
│          │           │                     │           │                 │
│          │           │                     │           ▼                 │
│          │           │                     │  ┌────────────────────┐    │
│          │           │                     │  │ Query Router       │    │
│          ▼           │                     │  │ (route to correct   │    │
│    Local Databases   │                     │  │  machine tunnel)   │    │
│    (Postgres/MySQL)  │                     │  └────────────────────┘    │
└──────────────────────┘                     └──────────────────────────────┘
```

## Key Concepts

### Per-Machine Keys
- Each machine gets a unique key
- Key persists across browser sessions
- Key becomes invalid on **force close** (crash, kill process), remains valid on graceful disconnect

### Multi-Machine Support
- Multiple machines can connect to same session
- Each machine has its own key
- DBs are identified by: `{machine_id}:{database_name}`
- Frontend routes queries to correct machine based on DB location

### Key Lifecycle
| Event | Key Status |
|-------|------------|
| Generated in frontend | Valid, unassigned |
| Connector registers with key | Valid, assigned to machine_id |
| User clicks "Disconnect" in frontend | Valid, can reconnect |
| Browser force close / crash | Invalid, must regenerate |
| User refreshes page | Valid, same key works |

## Implementation Phases

---

## Phase 1: Backend - WebSocket Tunnel Support

### Files to Create/Modify

#### 1. `app/core/tunnel/key_manager.py` (NEW)
```python
# Manages tunnel keys - generation, validation, lifecycle

class TunnelKeyManager:
    - generate_key() -> str  # Generate new key
    - register_key(key, machine_id, db_info)  # Assign key to machine
    - validate_key(key) -> bool  # Check if key is valid
    - invalidate_key(key)  # Force-close key (on crash detection)
    - get_machine_for_key(key) -> machine_id
    - get_all_machines() -> List[MachineInfo]
    - cleanup_stale_connections()  # Remove keys with no heartbeat > 5min
```

#### 2. `app/core/tunnel/registry.py` (NEW)
```python
# Stores connected machine state

class TunnelRegistry:
    - machines: Dict[machine_id, MachineConnection]
    - keys: Dict[key, machine_id]  # Reverse lookup
    
class MachineConnection:
    - machine_id: str
    - key: str
    - databases: List[DatabaseInfo]  # auto-discovered
    - websocket: WebSocket
    - connected_at: datetime
    - last_heartbeat: datetime
```

#### 3. `app/api/v1/endpoints/tunnel.py` (NEW)
```python
# REST endpoints for key management

@router.post("/tunnel/generate-key")
- Generate new unused key
- Return key to frontend

@router.post("/tunnel/heartbeat")
- Called periodically by frontend
- Updates last_seen timestamp for graceful close detection

@router.get("/tunnel/status")
- Returns all connected machines and their DBs
- Used by frontend to display connection status

@router.post("/tunnel/disconnect")
- Graceful disconnect - key remains valid
- Called when user clicks "Disconnect" in UI

@router.delete("/tunnel/key/{key}")
- Invalidate a key (force close)
- Called when heartbeat timeout detected

@router.websocket("/ws/tunnel")
- WebSocket for nlsql-connector
- Connector sends: register, heartbeat, query_result
- Backend sends: query_request, heartbeat_ping
```

#### 4. `app/core/tunnel/query_router.py` (NEW)
```python
# Routes queries to correct machine tunnel

class QueryRouter:
    - route_query(database_id, sql) -> result
    - Uses: machine_id = parse_database_id(database_id)
    - Sends query via WebSocket to correct machine
    - Returns result from machine
```

#### 5. Modify `app/core/database/connection_manager.py`
```python
# Add support for tunnel-based connections

class DatabaseConnectionManager:
    - Add: is_tunnel_database(db_id) -> bool
    - Add: get_tunnel_machine_id(db_id) -> machine_id
    - Modify: get_connection() - if tunnel DB, route via WebSocket instead of TCP
```

#### 6. Modify `app/models/database.py`
```python
# Add tunnel-related fields

class DatabaseConfig:
    - Add: is_tunnel: bool = False
    - Add: machine_id: Optional[str] = None

class DatabaseInfo:
    - Add: machine_id: Optional[str] = None
    - Add: connection_type: str  # "direct" or "tunnel"
```

---

## Phase 2: nlsql-connector Agent

### Package Structure

```
connector/
├── nlsql_connector/
│   ├── __init__.py
│   ├── main.py          # CLI entry point
│   ├── discoverer.py    # Auto-discover local DBs
│   ├── tunnel.py        # WebSocket client
│   ├── proxy.py         # SQL query proxy
│   └── config.py        # Settings
├── pyproject.toml
├── README.md
└── requirements.txt
```

### CLI Interface

```bash
# Connect with key from frontend
nlsql-connector --key <key>

# Or with config file
nlsql-connector --config config.yaml

# Options
nlsql-connector --key <key> --verbose    # Debug output
nlsql-connector --key <key> --no-auto    # Skip auto-discovery
```

### Features

1. **Auto-Discovery**
   - Scan localhost for PostgreSQL (ports 5432, 5433, etc.)
   - Scan localhost for MySQL (ports 3306, 3307, etc.)
   - Check common env vars: `DATABASE_URL`, `PGHOST`, `MYSQL_HOST`
   - Support custom connection strings via config

2. **WebSocket Connection**
   - Connect to backend `/ws/tunnel`
   - Register with key + machine_id + discovered DBs
   - Send heartbeat every 30 seconds
   - Auto-reconnect on disconnect (exponential backoff)

3. **Query Proxy**
   - Receive SQL queries via WebSocket
   - Execute against local database
   - Return results back via WebSocket
   - Handle both SELECT and write operations

4. **Machine ID Generation**
   - Hash of: hostname + random salt
   - Format: `machine_<8_char_hash>`

### Database Identification

DBs are identified as: `{machine_id}:{database_name}`

Example:
- `machine_abc123:postgres:myapp`
- `machine_def456:mysql:sales`

Frontend displays: `myapp (machine_abc123)` or just `myapp`

---

## Phase 3: Frontend Updates

### Files to Modify

#### 1. `frontend/src/components/ConnectionForm.jsx`
```javascript
// Add "Connect via Agent" section

- New tab/section: "Local Database (Agent)"
- "Generate Key" button → calls /api/v1/tunnel/generate-key
- Display command: nlsql-connector --key <key>
- Show connection status (waiting/connected/error)
- "Disconnect" button → calls /api/v1/tunnel/disconnect
```

#### 2. `frontend/src/components/TunnelStatus.jsx` (NEW)
```javascript
// Shows all connected machines and their DBs

- List of connected machines
- For each machine: machine_id, DB list, status
- Show "Refresh" button to update DB list
- Show "Disconnect" per machine
```

#### 3. Modify `frontend/src/components/AppSidebar.jsx`
```javascript
// Add "Connect Local DB" prominent button

- Either new section in sidebar
- Or prominent CTA in empty state
```

---

## API Endpoints Summary

### REST

| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/api/v1/tunnel/generate-key` | Generate new key |
| GET | `/api/v1/tunnel/status` | Get all connected machines + DBs |
| POST | `/api/v1/tunnel/heartbeat` | Update last_seen (graceful) |
| POST | `/api/v1/tunnel/disconnect` | Graceful disconnect |
| DELETE | `/api/v1/tunnel/key/{key}` | Invalidate key (force close) |

### WebSocket

| Endpoint | Direction | Purpose |
|----------|------------|---------|
| `/ws/tunnel` | Connector → Backend | Register machine, send heartbeat |
| `/ws/tunnel` | Backend → Connector | Query requests, heartbeat ping |

### WebSocket Messages

**Connector → Backend:**
```json
{"type": "register", "machine_id": "machine_abc", "databases": [{"name": "myapp", "type": "postgresql"}]}
{"type": "heartbeat"}
{"type": "query_result", "request_id": "req_123", "result": {...}}
```

**Backend → Connector:**
```json
{"type": "query_request", "request_id": "req_123", "database": "myapp", "sql": "SELECT * FROM users"}
{"type": "heartbeat_ping"}
{"type": "disconnect"}
```

---

## Security Considerations

1. **Key entropy** - Use 32+ random chars, unguessable
2. **WebSocket over WSS** - Use TLS (handled by Render)
3. **SQL injection** - Still sanitized on backend before sending to connector
4. **Connection limits** - Max 10 machines per deployment (configurable)
5. **Query timeout** - Same as regular DB queries

---

## Configuration

### Backend .env additions
```env
# Tunnel settings
TUNNEL_MAX_MACHINES=10
TUNNEL_HEARTBEAT_TIMEOUT_SECONDS=300
TUNNEL_QUERY_TIMEOUT_SECONDS=30

# Optional: single shared token for MVP (instead of per-key)
# CONNECTOR_TOKEN=your-secret-token
```

### Connector config (optional)
```yaml
# config.yaml
key: "generated_key_from_frontend"
databases:
  - host: localhost
    port: 5432
    type: postgresql
    name: myapp
```

---

## Testing Plan

1. **Unit tests** - Key manager, query router, discoverer
2. **Integration tests** - WebSocket connection, query routing
3. **Manual tests**:
   - Generate key in frontend
   - Run connector locally
   - See DB appear in frontend
   - Run query, verify results
   - Close browser, reconnect with same key
   - Force close, verify key is invalid
   - Connect multiple machines
   - Query DB from different machine

---

## Open Questions

1. **Query concurrency** - Can multiple queries run in parallel on same machine?
2. **Binary results** - How to handle BYTEA/Blob data through WebSocket?
3. **Large results** - Pagination for huge result sets?
4. **Write operations** - Support INSERT/UPDATE/DELETE through tunnel?
5. **SSL** - Should connector support SSL for local DBs?

---

## Priority Order

1. Backend WebSocket + key generation + basic routing
2. Connector agent with PostgreSQL support
3. Frontend UI for key generation + status
4. Add MySQL support to connector
5. Multi-machine query routing
6. Write operation support
7. Graceful/force close detection