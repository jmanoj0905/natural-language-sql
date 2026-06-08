# Natural Language SQL Engine

> Ask your database questions in plain English. Get SQL and results instantly. Local Ollama by default, optional cloud model when you need one.

[![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green.svg)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18-blue.svg)](https://react.dev)
[![License](https://img.shields.io/badge/License-GPL--3.0-yellow.svg)](LICENSE.txt)

---

## What it does

Type a question like *"show me the top 10 customers by revenue last month"* — the engine retrieves only the relevant slice of your schema, asks a local SQL-tuned LLM to write the query, validates it, executes it, and streams the results back in real time. No SQL knowledge required.

**Stack:** FastAPI + async SQLAlchemy · React 18 + Vite + Tailwind · Ollama / OpenAI / Gemini / Groq routing · BM25 + sentence-transformers hybrid retrieval

> Looking for the deep-dive blueprint (architecture, pipeline internals, file-to-responsibility map)? See [`PROJECT_BLUEPRINT.html`](./PROJECT_BLUEPRINT.html).
>
> Benchmark results (Spider dev, 52.32 % execution accuracy): [`BENCHMARKS.md`](./BENCHMARKS.md).

---

## Features

- **Local AI by default** — Ollama runs on your machine. OpenAI, Gemini, and Groq are opt-in per request from Settings; keys never persist on the server.
- **Hybrid schema retrieval (RAG)** — BM25 + sentence-transformer vectors fused with Reciprocal Rank Fusion, then expanded along foreign keys and column-pruned by cosine similarity. The model only ever sees the slice of the schema your question actually needs.
- **PostgreSQL & MySQL** — Connect multiple databases simultaneously, switch between them in one click.
- **Multi-DB fan-out** — Generate one SQL statement, execute it against several same-type databases in parallel, merge rows with a `__source_db__` column.
- **SSE streaming pipeline** — Live progress for every stage: Connect → Schema → AI → Validate → Execute, with per-stage timings.
- **Editable SQL preview** — Review and edit AI-generated SQL before running it.
- **Write operations** — INSERT / UPDATE / DELETE with warning banners and a permitted *write-then-SELECT* compound shape ("delete X and show me what's left").
- **Sortable, paginated results** — Click headers to sort; 50 rows per page.
- **Export** — Download as CSV / JSON, or copy as tab-separated for spreadsheets.
- **Query history** — Session-local history with SQL, explanation, row count, and timing.
- **Encrypted credentials** — Database passwords stored Fernet-encrypted in `~/.nlsql/databases.json`.

---

## Prerequisites

- **Python 3.12+**
- **Node.js 18+**
- **Ollama CLI** — [ollama.com](https://ollama.com)

---

## Quick Start

```bash
# 1. Clone
git clone https://github.com/jmanoj0905/natural-language-sql
cd natural-language-sql

# 2. Install everything (Python venv, Node deps, Ollama model)
./install.sh

# 3. Start
./run.sh dev
```

Open **http://localhost:3000**, connect a database from the sidebar, and start asking questions.

| Service | URL |
|---------|-----|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| API Docs | http://localhost:8000/docs |
| Prometheus metrics | http://localhost:8000/metrics |
| Ollama | http://localhost:11434 |

---

## How it works

```mermaid
sequenceDiagram
    participant U as User
    participant F as Frontend (Vite :3000)
    participant B as Backend (FastAPI :8000)
    participant R as Hybrid Retriever
    participant O as Ollama / Cloud LLM
    participant D as Database

    U->>F: "top 10 customers by revenue last month"
    F->>B: POST /query/natural/stream (SSE)

    rect rgb(245, 248, 255)
        Note over B: [1] Connect
        B->>D: Acquire async connection
        D-->>B: ok

        Note over B,R: [2] Schema — hybrid RAG
        B->>R: question + schema metadata
        R->>R: BM25 rank tables
        R->>R: Vector search (tables + paths)
        R->>R: RRF fuse rankings
        R->>R: Expand seeds by foreign keys
        R->>R: Prune wide tables by cosine
        R->>D: Fetch 1 sample row per table
        D-->>R: rows
        R-->>B: compact CREATE TABLE context

        Note over B,O: [3] AI
        B->>O: prompt (schema + intent rules)
        O-->>B: raw SQL

        Note over B: [4] Validate
        B->>B: sqlparse · allow-list · LIMIT · sanitiser

        Note over B,D: [5] Execute
        B->>D: validated SQL (asyncio timeout)
        D-->>B: rows
    end

    B-->>F: SSE: progress (×5 stages) + result
    F->>U: Render table + history entry
```

Each stage emits an SSE `progress` event so the UI animates live. Failure at any stage emits an `error` event and stops the stream.

### The RAG pipeline (the part that matters)

Real databases have hundreds of tables. Dumping all of them into the prompt blows the context window, dilutes attention, and slows generation to a crawl. The retriever returns *only* the slice of schema that the current question needs:

| Stage | What it does | Why it's there |
|-------|--------------|----------------|
| **BM25** | Lexical ranking of tables, table-name weighted ×3, columns ×2. | Catches direct word matches ("show customers" → `customers`). |
| **Vector** | Cosine search across three spaces: tables, columns, and FK join-paths described in English. | Catches synonyms and concepts ("revenue" → `orders.total`). Join-path search surfaces relationships even when neither endpoint is named. |
| **RRF fuse** | Reciprocal Rank Fusion (`k=60`) over the three rankings. | Score-only fusion fails because BM25 and cosine live on incomparable scales. RRF uses rank position alone — robust to outliers. |
| **FK expand** | 1-hop walk over the foreign-key graph from the top-5 seeds. | Ensures join targets are present even if they didn't directly match the question. |
| **Column prune** | Per-table cosine scoring; keep PK + FK + top-N + above-threshold columns. | Wide tables (80+ columns) waste prompt budget. PK/FK are always kept regardless of score. |
| **Sample rows** | 1 row per surviving table. | Gives the model type / encoding / FK-convention clues a bare DDL can't. |
| **Format** | Render as `CREATE TABLE` + sample-row comments + `RELATIONSHIPS:` footer. | The native dialect of SQL-tuned models. |

**Caching:** schema-version hashes invalidate the on-disk vector index automatically on DDL change; an in-memory TTLCache (1h, keyed by question hash) skips the whole pipeline for repeated questions. Per-`db_id` asyncio locks prevent concurrent rebuilds.

**Graceful degradation:** if `sentence-transformers` isn't installed or the embedder fails to load, the retriever drops to BM25-only. If BM25 also returns nothing, a bounded first-N-tables fallback fires with an explicit comment.

Configuration lives in `.env` under `HYBRID_RETRIEVAL_ENABLED`, `MAX_SEED_TABLES`, `MAX_TABLES`, `MAX_COLS_PER_TABLE`, `COLUMN_SCORE_THRESHOLD`, `RRF_K`, `INCLUDE_SAMPLE_ROWS_COMPACT`, `SAMPLE_ROWS_COMPACT`, `EMBEDDING_INDEX_DIR`. The full design lives in `docs/superpowers/specs/2026-05-20-rag-pipeline-bundle-a-design.md`.

---

## Management Commands

```bash
./run.sh dev           # Start backend + frontend + Ollama
./run.sh stop          # Stop all services
./run.sh prod          # Backend only (no frontend dev server)
./run.sh setup-ollama  # Install Ollama + pull/warm the model
./run.sh clean         # Remove logs and cache
./run.sh logs          # Tail application logs
```

---

## Configuration

All configuration is via environment variables in `.env` (copy from `.env.example`):

| Variable | Default | Description |
|----------|---------|-------------|
| `OLLAMA_MODEL` | `mannix/defog-llama3-sqlcoder-8b` | AI model (SQL-specialist) |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama endpoint |
| `OLLAMA_TEMPERATURE` | `0.1` | 0 = deterministic, 2 = creative |
| `INFERENCE_PROVIDER` | `ollama` | Server-side default; overridable per request |
| `MAX_QUERY_RESULTS` | `1000` | Hard cap on rows returned |
| `DEFAULT_QUERY_LIMIT` | `100` | Auto-added LIMIT for SELECT queries |
| `QUERY_TIMEOUT_SECONDS` | `30` | Per-query execution timeout |
| `DB_ENCRYPTION_KEY` | *(auto)* | Fernet key for password storage — **set a stable key in production** |
| `STRICT_SQL_VALIDATION` | `false` | Opt into stricter sanitiser checks |
| `SCHEMA_CACHE_TTL_SECONDS` | `3600` | Schema cache lifetime (1 hour) |
| `HYBRID_RETRIEVAL_ENABLED` | `true` | Toggle the vector half of retrieval; `false` = BM25-only |
| `MAX_SEED_TABLES` / `MAX_TABLES` | `5` / `12` | RAG seed count and final table cap |
| `MAX_COLS_PER_TABLE` | `15` | Column-pruner budget per table |
| `COLUMN_SCORE_THRESHOLD` | `0.25` | Cosine threshold for keeping a column above budget |
| `RRF_K` | `60` | Rank constant for Reciprocal Rank Fusion |
| `EMBEDDING_INDEX_DIR` | `~/.nlsql/embeddings` | On-disk vector index location |
| `LOG_LEVEL` | `INFO` | DEBUG / INFO / WARNING / ERROR |

### Switching AI Models

The default model (`mannix/defog-llama3-sqlcoder-8b`) is fine-tuned for SQL generation. To use a different one:

```bash
ollama pull <model-name>
# Update OLLAMA_MODEL in .env
./run.sh stop && ./run.sh dev
```

| Model | Size | Notes |
|-------|------|-------|
| `mannix/defog-llama3-sqlcoder-8b` | ~5GB | Default — SQL-specialist, highest accuracy |
| `sqlcoder:7b` | ~4GB | Alternative SQL-specialist |
| `llama3.2:3b` | ~2GB | Faster, less accurate |
| `codellama:7b` | ~3.8GB | General code model |

Cloud providers (OpenAI, Google Gemini, Groq, HuggingFace) are configured per-request via the Settings modal — their API keys ride with the request and are never stored.

---

## API Reference

All endpoints are under `/api/v1`.

### Query

```bash
# Natural language → SQL → execute (SSE streaming, preferred)
curl -X POST "http://localhost:8000/api/v1/query/natural/stream?database_id=mydb" \
  -H "Content-Type: application/json" \
  -d '{"question": "show top 10 customers by revenue", "options": {"execute": true}}'

# Multi-DB fan-out (same SQL against multiple databases in parallel)
curl -X POST "http://localhost:8000/api/v1/query/natural/stream?database_ids=db1,db2,db3" \
  -H "Content-Type: application/json" \
  -d '{"question": "count active users", "options": {"execute": true}}'

# Execute raw SQL directly
curl -X POST "http://localhost:8000/api/v1/query/sql?database_id=mydb" \
  -H "Content-Type: application/json" \
  -d '{"sql": "SELECT * FROM users LIMIT 10"}'

# Get an execution plan
curl -X POST "http://localhost:8000/api/v1/query/explain?database_id=mydb" \
  -H "Content-Type: application/json" \
  -d '{"sql": "SELECT * FROM orders WHERE customer_id = 42"}'
```

### Databases

```bash
# Register a database
curl -X POST http://localhost:8000/api/v1/databases \
  -H "Content-Type: application/json" \
  -d '{"database_id":"mydb","db_type":"postgresql","host":"localhost","port":5432,"database":"mydb","username":"user","password":"pass"}'

# List all databases
curl http://localhost:8000/api/v1/databases

# Test connection without registering
curl -X POST http://localhost:8000/api/v1/databases/test \
  -H "Content-Type: application/json" \
  -d '{"db_type":"mysql","host":"localhost","port":3306,"database":"mydb","username":"root","password":"pass"}'
```

### Schema

```bash
# Get schema for a database
curl "http://localhost:8000/api/v1/schema?database_id=mydb"

# Concise schema text (same renderer used for AI prompt context)
curl "http://localhost:8000/api/v1/schema/summary?database_id=mydb"

# Clear schema cache (call after migrations)
curl -X POST http://localhost:8000/api/v1/schema/cache/clear
```

Full endpoint table lives in `PROJECT_BLUEPRINT.html` §8.

---

## Project Structure

```
natural-lang-sql/
├── app/                                  # FastAPI backend
│   ├── main.py                           # Entry point, lifespan, CORS, metrics
│   ├── config.py                         # Pydantic Settings (env vars)
│   ├── dependencies.py                   # DI singletons
│   ├── exceptions.py                     # Exception hierarchy
│   ├── api/v1/endpoints/
│   │   ├── query.py                      # /query/natural, /query/sql, /query/explain
│   │   ├── query_stream.py               # /query/natural/stream (SSE, multi-DB)
│   │   ├── query_management.py           # write preview / execute, history
│   │   ├── schema.py                     # /schema endpoints
│   │   ├── database.py                   # /databases CRUD
│   │   └── health.py                     # /health endpoints
│   └── core/
│       ├── ai/
│       │   ├── ollama_client.py          # Provider routing (Ollama/OpenAI/Gemini/Groq/HF)
│       │   ├── ollama_sql_generator.py   # NL → SQL orchestrator
│       │   ├── prompts.py                # Prompt templates + SQL/explanation extractors
│       │   ├── query_planner.py          # Intent detector + step decomposition
│       │   └── schema_embedder.py        # sentence-transformers wrapper (lazy)
│       ├── database/
│       │   ├── connection_manager.py     # Async engine pool, Fernet-encrypted creds
│       │   ├── schema_inspector.py       # information_schema introspection + TTL cache
│       │   ├── adapters/                 # PostgreSQL + MySQL adapters
│       │   └── retrieval/                # Hybrid RAG pipeline
│       │       ├── hybrid.py             # Orchestrator
│       │       ├── corpus.py             # Doc builder (tables/cols/paths)
│       │       ├── bm25.py               # Lexical ranker
│       │       ├── vector_index.py       # NumPy cosine index + .npz persistence
│       │       ├── rrf.py                # Reciprocal Rank Fusion
│       │       ├── fk_expander.py        # 1-hop FK graph walk
│       │       ├── column_pruner.py      # Per-table column pruning by cosine
│       │       ├── formatter.py          # Render CREATE TABLE + samples + relationships
│       │       └── progress.py           # Sub-stage progress events
│       ├── query/
│       │   ├── validator.py              # sqlparse, operation allow-list, auto-LIMIT
│       │   ├── executor.py               # asyncio.wait_for execution + pagination
│       │   └── error_humanizer.py        # DB errors → English
│       └── security/
│           └── sql_sanitizer.py          # Injection pattern guard (lenient / strict)
├── frontend/                             # React 18 + Vite SPA
│   └── src/
│       ├── App.jsx                       # Layout shell, top nav, sidebar, tabs
│       ├── config.js                     # API_BASE
│       ├── components/
│       │   ├── AppSidebar.jsx            # DB list, multi-select, add/edit/delete
│       │   ├── ConnectionForm.jsx        # Flat connection form with Test/Save
│       │   ├── QueryInterface.jsx        # NL input, SSE reader, editable SQL preview
│       │   ├── QueryProgress.jsx         # 5-stage live indicator
│       │   ├── MultiStepPlan.jsx         # Compound-question decomposition
│       │   ├── ResultsDisplay.jsx        # Sortable, paginated table
│       │   ├── ExportModal.jsx           # CSV / JSON / TSV export
│       │   ├── SchemaModal.jsx           # Full schema browser
│       │   ├── QueryHistory.jsx          # Session history
│       │   ├── SettingsModal.jsx         # Provider / model / API key
│       │   ├── DatabaseStatus.jsx        # Header status pill
│       │   └── ui/                       # Radix-based primitives
│       ├── data/providers.js             # Per-db_type defaults
│       └── utils/{sql,queryErrors}.js    # Write-op detection, error parsing
├── tests/                                # pytest suite (sanitiser, validator, RAG units…)
├── docs/                                 # Design specs
├── scripts/                              # Seed scripts, password-encrypt migration
├── PROJECT_BLUEPRINT.html                # Full architecture + rebuild blueprint
├── requirements.txt
├── install.sh                            # One-command setup
└── run.sh                                # dev / prod / stop / clean / logs
```

---

## Security Notes

- **Credentials** are Fernet-encrypted at rest in `~/.nlsql/databases.json`. **Generate a stable key and set `DB_ENCRYPTION_KEY` in `.env`** — otherwise a fresh key is generated on each restart, making saved passwords unrecoverable.
- **SQL execution** is limited to single SELECT / INSERT / UPDATE / DELETE statements, with one supported compound shape: write statement followed by SELECT.
- **SELECT queries** get a default `LIMIT` when missing; oversized explicit `LIMIT` values are capped at `MAX_QUERY_RESULTS`.
- **Strict validation** (`STRICT_SQL_VALIDATION=true`) blocks comments, hex literals, and other suspicious SQL patterns.
- **Write operations** are allowed by default. The UI shows warning banners; use a read-only DB user for a hard block.
- **Cloud provider API keys** are passed inline per request and **never stored or logged** server-side.
- **CORS** defaults to `http://localhost:3000`. Set `CORS_ORIGINS` for production.
- **Rate limiting** is configurable via `API_RATE_LIMIT_PER_MINUTE`.

```bash
# Generate a stable encryption key
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# Add to .env → DB_ENCRYPTION_KEY=<key>
```

---

## Development

```bash
# Backend only
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000

# Frontend only
cd frontend && npm run dev

# Run tests (includes retrieval unit tests)
.venv/bin/python -m pytest tests/ -v
```

For the architecture in depth — including the file-to-responsibility map and a "rebuild from scratch" checklist — open [`PROJECT_BLUEPRINT.html`](./PROJECT_BLUEPRINT.html) in a browser.

---

## License

GPL-3.0 — see [LICENSE.txt](LICENSE.txt).

**Author:** Manoj J · [jmanoj.pages.dev](https://jmanoj.pages.dev) · [github.com/jmanoj0905](https://github.com/jmanoj0905)
