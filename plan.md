# Natural Language SQL Engine - Deployment Requirements

## Project Overview

**Project Name:** Natural Language SQL Engine
**Type:** Full-stack web application (FastAPI backend + React frontend)
**Core Functionality:** Converts natural language questions to SQL queries using LLM, executes against user databases
**Deployment Target:** Backend on Cloudflare Workers/Pages + Cloudflare Tunnel, Frontend on Cloudflare Pages

---

## Deployment Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Cloudflare                           │
│  ┌─────────────────┐         ┌─────────────────────────┐   │
│  │ Cloudflare Pages│────────▶│ Cloudflare Workers      │   │
│  │   (Frontend)    │         │   (API Gateway)          │   │
│  └─────────────────┘         └───────────┬─────────────┘   │
│                                          │                  │
│                                          ▼                  │
│                                  ┌─────────────────────┐    │
│                                  │  Cloudflare Tunnel  │    │
│                                  │ (WebSocket/HTTP)    │    │
│                                  │  to origin server   │    │
│                                  └─────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
                                             │
                                             ▼
┌─────────────────────────────────────────────────────────────┐
│                   User's Local Machine                      │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │ cloudflared │  │  PostgreSQL  │  │      Ollama        │  │
│  │ (Tunnel)    │◀─┤  (Local DB)  │  │   (Local AI)        │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

**Connection Flow:**
- Frontend (Cloudflare Pages) → Cloudflare Workers API → Cloudflare Tunnel → Local Agent → Local DB/Ollama

---

## Current State (As-Is)

### Backend (`app/`)
- FastAPI application with async SQLAlchemy
- Supports PostgreSQL and MySQL via adapters
- Database configs stored in `~/.nlsql/databases.json` with Fernet-encrypted passwords
- Has tunnel config fields in models but **no actual tunnel implementation**

### Frontend (`frontend/`)
- React 18 + Vite + Tailwind CSS
- SettingsModal allows selecting provider (ollama/openai/google/groq) and entering API keys
- **Issue:** No field to specify custom Ollama URL
- QueryInterface sends provider/model/api_key in request but backend ignores them

### AI Integration
- `ollama_client.py` has `generate_with_config()` function supporting multiple providers
- Providers: Ollama (local), OpenAI, Google Gemini, Groq, HuggingFace
- **Bug:** Query endpoint doesn't use the per-request provider configuration

---

## Requirements

### Requirement 1: Backend - Use Per-Request Provider Configuration

**Priority:** P0 (Critical - Current Bug)

**Description:** The `/api/v1/query/natural` endpoint currently ignores the `provider`, `model`, and `api_key` fields sent in the request body. It always uses the server's default Ollama configuration.

**Location:** `app/api/v1/endpoints/query.py`, lines 92-98

**Current Code (needs modification):**
```python
sql, explanation = await sql_generator.generate_sql(
    question=request.question,
    connection=conn,
    db_id=target_db_id,
    read_only=request.options.read_only,
    registered_dbs=registered_dbs,
)
```

**Expected Behavior:**
Pass the user's selected provider, model, and API key to the SQL generator. Use the existing `generate_with_config()` function in `ollama_client.py:384`.

**Acceptance Criteria:**
1. When user selects "openai" with model "gpt-4o-mini" and provides API key, queries use OpenAI
2. When user selects "google" with model "gemini-1.5-flash" and provides API key, queries use Google Gemini
3. When user selects "groq" with API key, queries use Groq
4. When user selects "ollama" with custom URL, queries use that Ollama instance
5. Response metadata reflects which provider/model was actually used

---

### Requirement 2: Frontend - Custom Ollama URL Field

**Priority:** P1 (High)

**Description:** Users must be able to specify their own Ollama endpoint URL when selecting Ollama as the provider. Currently, the frontend assumes Ollama is accessible at the backend's configured URL.

**Current Behavior:**
- Frontend calls `/health/ollama` which uses server's `OLLAMA_BASE_URL`
- No way for users to specify their own Ollama URL (e.g., `http://192.168.1.100:11434`)

**Expected Behavior:**
- Add URL input field in SettingsModal for "Ollama URL"
- Placeholder: `http://localhost:11434`
- Store in localStorage under `ollamaUrl`
- Pass with each query request or use for health check

**UI Location:** `frontend/src/components/SettingsModal.jsx`, under Ollama model selector

**Acceptance Criteria:**
1. User can enter custom Ollama URL
2. URL persists across sessions (localStorage)
3. Health check uses the custom URL when configured
4. Queries route to the custom Ollama URL when provider is "ollama"

---

### Requirement 3: Cloudflare Tunnel Integration for Local Database Access

**Priority:** P1 (High)

**Description:** Users must be able to connect to databases running on their local machine. Use Cloudflare Tunnel (`cloudflared`) to establish persistent connections from user's machine to Cloudflare, allowing the backend to proxy queries through the tunnel.

#### 3.1 Architecture

```
User's Machine                          Cloudflare                  Backend
┌──────────────┐                      ┌────────────┐              ┌─────────┐
│ cloudflared  │◀───────────────────▶│ Cloudflare │─────────────▶│ FastAPI │
│ (tunnel)     │   persistent conn    │  Tunnel    │   HTTP/WS   │  API    │
└──────┬───────┘                      └────────────┘              └────┬────┘
       │                                                           │
       ▼                                                           ▼
┌──────────────┐                                          ┌────────────────┐
│ PostgreSQL   │                                          │ Tunnel Handler │
│ MySQL        │                                          │ - routes to    │
│ (localhost)  │                                          │   tunnel URL   │
└──────────────┘                                          └────────────────┘
```

#### 3.2 User Connection Flow

**Step 1: User sets up Cloudflare Tunnel**

Users install `cloudflared` and create a tunnel:
```bash
# Install cloudflared (https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/tunnel-guide/local/)

# Login and create tunnel
cloudflared tunnel login
cloudflared tunnel create my-local-db

# Run tunnel (points to the backend URL)
cloudflared tunnel run my-local-db --url http://localhost:8000
```

**Alternative: Use cloudflared to expose local services**
```bash
# Expose local PostgreSQL directly through tunnel
cloudflared tunnel run my-local-db --ingress-rule="hostname: db.user1.example.com,service: http://localhost:5432"

# Expose local Ollama
cloudflared tunnel run my-ollama --ingress-rule="hostname: ollama.user1.example.com,service: http://localhost:11434"
```

#### 3.3 Backend - Tunnel Routing

**Option A: Direct Tunnel to Service (Recommended)**

When user configures tunnel with ingress rules, they connect directly:
- Database tunnel: `https://db.machine123.yourdomain.com` → local PostgreSQL
- Ollama tunnel: `https://ollama.machine123.yourdomain.com` → local Ollama

**Backend stores:**
- `db_tunnel_url`: `https://db.machine123.yourdomain.com`
- `ollama_tunnel_url`: `https://ollama.machine123.yourdomain.com`

**Query flow:**
1. User adds database, provides tunnel URL (e.g., `https://db.machine123.yourdomain.com`)
2. Backend stores with `connection_type: "tunnel"`
3. On query, backend makes HTTP request to tunnel URL instead of direct connection
4. Cloudflare Tunnel proxies to user's local PostgreSQL

**Option B: WebSocket via Cloudflare**

If users run `cloudflared tunnel run --url http://localhost:8000`, the backend can maintain a WebSocket connection to the tunnel.

#### 3.4 Frontend - Tunnel Configuration UI

**New Database Connection Flow:**

1. User clicks "Add Database"
2. Options displayed:
   - "Cloud Database" (existing - direct connection)
   - "Local Database (via Cloudflare Tunnel)" (new)

3. If "Local Database (via Cloudflare Tunnel)":
   - Input: "Tunnel URL" (e.g., `https://db.machine123.yourdomain.com`)
   - Input: "Tunnel Name" (friendly label, e.g., "My Laptop")
   - Standard DB form (database name, username, password - host/port from tunnel URL)

4. Save with:
   - `connection_type: "tunnel"`
   - `tunnel_url`: user's tunnel URL
   - `tunnel_name`: friendly name

**Ollama via Tunnel:**

If user wants to use local Ollama from deployed frontend:
- Input: "Ollama Tunnel URL" in Settings (e.g., `https://ollama.machine123.yourdomain.com`)
- Backend uses this URL for Ollama API calls instead of default

**Acceptance Criteria:**
1. User can add database with tunnel connection type
2. User can specify tunnel URL for local Ollama in Settings
3. Queries to tunnel databases route through Cloudflare Tunnel
4. Queries to tunnel Ollama route through Cloudflare Tunnel
5. Clear setup instructions provided in UI

---

### Requirement 4: Cloudflare Workers / Pages Backend Deployment

**Priority:** P2 (Medium)

**Description:** Deploy backend to Cloudflare (Workers or Pages with backend).

**Option A: Cloudflare Workers + FastAPI**

- Convert FastAPI to run on Cloudflare Workers using `pyodide` or similar
- Or use FastASCII/other frameworks that compile to Workers

**Option B: Cloudflare Pages with API Routes**

- Use Cloudflare Pages Functions (formerly API routes)
- More limited runtime but simpler

**Option C: Traditional Server behind Cloudflare Tunnel**

- Deploy FastAPI to any hosting (VPS, Docker, etc.)
- Use Cloudflare as the proxy/TLS layer
- Use Cloudflare Tunnel for local access

**Recommended for v1: Option C**
- Simpler implementation - no code changes needed
- Full Python runtime with all dependencies
- Can run locally during development

**Tunnel Setup:**
```bash
# On the server running FastAPI
cloudflared tunnel --url http://localhost:8000
# Or configure ingress rules to route specific subdomains to the backend
```

**Cloudflare Dashboard Configuration:**
1. Create Cloudflare Tunnel
2. Configure public hostname (e.g., `api.nlsql.yourdomain.com`)
3. Point to origin server (or tunnel URL for local dev)
4. Enable HTTP/2 or WebSocket support if needed

**Environment Variables:**
| Variable | Value |
|----------|-------|
| `CORS_ORIGINS` | `https://*.pages.dev, https://*.cloudflareapps.com` |
| `DB_ENCRYPTION_KEY` | `<generated-fernet-key>` |
| `LOG_LEVEL` | `INFO` |

---

### Requirement 5: Cloudflare Pages Frontend Deployment

**Priority:** P2 (Medium)

**Description:** Deploy the React frontend to Cloudflare Pages.

**Build Configuration:**
| Setting | Value |
|---------|-------|
| Build command | `npm run build` |
| Build output | `dist/` |
| Node version | 18 |

**Environment Variables:**
| Variable | Value |
|----------|-------|
| `VITE_API_URL` | `https://api.nlsql.yourdomain.com` |

**Acceptance Criteria:**
1. Frontend accessible at Cloudflare Pages URL
2. Connects to backend API through Cloudflare
3. SettingsModal allows provider selection and custom Ollama URL
4. All providers work (OpenAI, Google, Groq, Ollama)

---

### Requirement 6: Security & Production Configuration

**Priority:** P3 (Lower - for future iteration)

**Configuration:**

**Environment:**
- `DEBUG=false`
- `STRICT_SQL_VALIDATION=false` (or true if untrusted users)
- `API_RATE_LIMIT_PER_MINUTE=60`
- `MAX_QUERY_RESULTS=1000`
- `QUERY_TIMEOUT_SECONDS=30`

**Cloudflare Security:**
- Enable Cloudflare WAF rules
- Configure Security Headers in Cloudflare
- Use Cloudflare Access for additional auth if needed (future)

---

## Data Flow Diagrams

### Query Flow (Cloud API Provider)

```
User: "Show me all users"
Frontend: POST /api/v1/query/natural with { provider: "openai", model: "gpt-4o-mini", api_key: "sk-..." }
Backend: generate_with_config(prompt, provider="openai", model="gpt-4o-mini", api_key="sk-...")
Backend: Calls OpenAI API directly
Backend: Returns SQL + results
Frontend: Displays results
```

### Query Flow (Local Database via Cloudflare Tunnel)

```
User queries database with tunnel_url="https://db.laptop123.yourdomain.com"
Frontend: POST /api/v1/query/natural with database_id="local-db"
Backend: Looks up database, finds connection_type="tunnel", tunnel_url="https://db.laptop123.yourdomain.com"
Backend: HTTP POST to tunnel_url with SQL
Cloudflare Tunnel: Proxies to user's local PostgreSQL
Local PostgreSQL: Executes query, returns results
Backend: Returns results to frontend
```

### Query Flow (Local Ollama via Cloudflare Tunnel)

```
User: "Show me all users", provider="ollama", ollama_tunnel_url="https://ollama.laptop123.yourdomain.com"
Frontend: POST /api/v1/query/natural with { provider: "ollama", ... }
Backend: Looks up ollama_tunnel_url in settings
Backend: HTTP POST to tunnel_url/api/generate with prompt
Cloudflare Tunnel: Proxies to user's local Ollama
Local Ollama: Generates SQL, returns response
Backend: Extracts SQL, executes query (via tunnel if local DB)
Backend: Returns SQL + results
```

---

## Testing Requirements

### Manual Testing Checklist

1. **Provider Configuration**
   - [ ] OpenAI API key works from Settings
   - [ ] Google Gemini API key works from Settings
   - [ ] Groq API key works from Settings
   - [ ] Custom Ollama URL works in Settings

2. **Cloudflare Tunnel Setup**
   - [ ] User can install cloudflared
   - [ ] User can create and run a tunnel
   - [ ] Tunnel URL is accessible from internet

3. **Tunnel Database Connection**
   - [ ] Add database with tunnel type and tunnel URL
   - [ ] Run query, verifies routes through tunnel
   - [ ] Get correct results from local database

4. **Tunnel Ollama**
   - [ ] Configure Ollama tunnel URL in Settings
   - [ ] Query uses local Ollama through tunnel
   - [ ] SQL generation works correctly

5. **Deployment**
   - [ ] Frontend deploys to Cloudflare Pages
   - [ ] Backend accessible via Cloudflare (Workers or proxied)
   - [ ] All functionality works from deployed URLs

---

## Out of Scope (v1)

- User authentication/authorization
- Multi-user isolation (shared instance)
- Query history persistence beyond session
- ER diagrams / schema visualization
- Database connection testing during add (already exists)
- Query result export (already exists)

---

## Dependencies

### Python (Backend)
- fastapi
- uvicorn
- sqlalchemy (async)
- asyncpg (PostgreSQL)
- aiomysql (MySQL)
- pydantic + pydantic-settings
- python-multipart
- slowapi (rate limiting)
- cryptography (Fernet)
- httpx
- structlog

### JavaScript (Frontend)
- react 18
- vite 5
- tailwindcss 3
- axios
- lucide-react (icons)

### User Tools
- cloudflared (Cloudflare Tunnel client)

---

## Implementation Notes

### Cloudflare Tunnel Setup Instructions (for users)

**For Local Database:**

1. Install cloudflared: https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/tunnel-guide/local/

2. Create and run a tunnel:
   ```bash
   cloudflared tunnel login
   cloudflared tunnel create my-database-tunnel
   cloudflared tunnel run my-database-tunnel --ingress-rule="hostname: db.YOURNAME.example.com,service: http://localhost:5432"
   ```

3. Create DNS record: `db.YOURNAME.example.com` → tunnel

4. In frontend, add database:
   - Connection type: "Local Database (via Cloudflare Tunnel)"
   - Tunnel URL: `https://db.YOURNAME.example.com`

**For Local Ollama:**

1. Similar tunnel setup for port 11434:
   ```bash
   cloudflared tunnel run my-ollama-tunnel --ingress-rule="hostname: ollama.YOURNAME.example.com,service: http://localhost:11434"
   ```

2. In Settings, enter Ollama Tunnel URL: `https://ollama.YOURNAME.example.com`

---

## Questions for Implementation Team

1. **Cloudflare backend approach:** Use Cloudflare Workers with Python runtime (limited), Cloudflare Pages Functions, or traditional server behind Cloudflare proxy?

2. **Tunnel URL handling:** Should users specify full tunnel URL, or just a identifier that maps to a pre-configured tunnel?

3. **Multiple tunnels:** Should a user be able to connect multiple machines (laptop, desktop, work computer)?

4. **Tunnel health:** How to indicate tunnel status in UI (connected/disconnected) - poll tunnel URL or rely on user visibility?