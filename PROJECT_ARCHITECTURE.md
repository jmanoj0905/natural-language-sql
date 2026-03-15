# Natural Language SQL — Project Architecture

## What It Is

A full-stack app that lets you type plain English questions and get SQL queries generated, validated, and executed against your databases. Uses a local Ollama AI (no API keys, no cost) to do the translation. Supports PostgreSQL and MySQL.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React, Vite, Tailwind CSS, Axios |
| Backend | FastAPI (Python), Uvicorn |
| AI | Ollama (local LLM — llama3.2 by default) |
| Database | PostgreSQL (asyncpg), MySQL (aiomysql) |
| ORM / Queries | SQLAlchemy (async) |
| Config | Pydantic Settings (loaded from .env) |
| Logging | structlog (JSON in prod, console in dev) |
| Rate Limiting | slowapi (60 req/min per IP, fixed-window) |
| Password Storage | Fernet symmetric encryption |
| Caching | TTLCache (in-memory, 1hr TTL) + persistent AI-prompt cache |

---

## High-Level Flow

```
User types a question in the browser
       |
       v
  QueryInterface.jsx          ← collects the text, options, and which DB to target
       |
       |  POST /api/v1/query/natural   { question, options, database_id }
       v
  query.py  →  natural_language_query()   ← the main orchestrator, calls everything below
       |
       +-- SchemaInspector.get_schema_summary()   ← fetches + caches schema with sample rows
       +-- prompts.build_sql_generation_prompt()   ← assembles the full prompt string
       +-- OllamaClient.generate_content()         ← sends prompt to Ollama, gets raw text back
       +-- prompts.extract_sql_from_response()     ← pulls SQL out of the ```sql block
       +-- SQLGenerator._detect_missing_fields()   ← checks if AI said MISSING_REQUIRED_FIELDS
       +-- IntelligentQueryPlanner.analyze_request()← decides single vs multi-step
       +-- QueryValidator.validate()               ← sanitize, intent check, LIMIT
       +-- QueryExecutor.execute()                 ← runs it, returns rows + timing
       |
       v
  Return QueryResponse   →   ResultsDisplay.jsx   ← renders SQL, explanation, table, badges
```

---

## Frontend — File by File

### App.jsx
**Responsibility:** The root of the app. Owns all the top-level state and is the single source of truth for the frontend.

- Holds state for: `databases` (list of registered DBs), `queryHistory` (last 20 queries), `currentResult` (what's displayed right now), `dbHealth` (live health status), `selectedDatabases` (which DB the user picked), `activeTab` (query / databases / connectors).
- `loadDatabases()` — calls `GET /databases` every 30 seconds. Takes nothing in. Sets `databases` and `defaultDatabaseId` state from the response.
- `checkDatabaseHealth()` — calls `GET /health/database` every 30 seconds. Takes nothing in. Sets `dbHealth` state (connected or not).
- `handleQuerySubmit(question, options)` — takes in the user's question string and the options object `{ execute, read_only, include_schema_context }`. Figures out which database to target (selected one or default). POSTs to `/query/natural`. Pushes the result into `queryHistory` (capped at 20). Sets `currentResult` so `ResultsDisplay` renders. Returns the result so child components can check it (e.g., for missing fields).
- Renders the tab navigation and swaps between `QueryInterface`, `DatabaseOverview`, `DatabaseConnectionManager`, and `QueryHistory` based on `activeTab`.
- Contains a hamburger menu that opens a "How to Use" modal with step-by-step instructions.

### QueryInterface.jsx
**Responsibility:** Collects the user's question and query settings. The only component that talks to the user before a query is sent.

- Holds state for: `question` (the typed text), `readOnlyMode` (toggle), `executeQuery` (auto-execute toggle), `loading`, `error`, `generatedResult`, `missingFields`.
- `detectDangerousSQL(sql)` — takes in a SQL string. Scans it for DELETE, UPDATE, DROP, TRUNCATE, INSERT, ALTER. Returns an array of `{ type, severity, message }` objects. Used to show warning badges after SQL is generated in write mode. Returns `null` if nothing dangerous.
- `handleReadOnlyToggle()` — takes nothing. Flips `readOnlyMode`. If switching TO write mode, it also forces `executeQuery` off (safety: never auto-run writes).
- `handleSubmit(e, forceExecute, additionalData)` — the main submit handler. Takes the form event, an optional force-execute flag, and optional extra field values from the MissingFieldsModal. Builds the full question string (appends any filled-in missing field values). Calls `onSubmit` (which is `App.handleQuerySubmit`). If the response has `requires_user_input`, it opens the MissingFieldsModal instead of showing results.
- `handleMissingFieldsSubmit(fieldValues)` — takes in `{ "table.column": "value", ... }` from the modal. Closes the modal, then re-calls `handleSubmit` with those values as `additionalData` so they get appended to the question.
- `handleExecuteGenerated()` — takes nothing. Called when the user clicks "Execute Query" after reviewing the generated SQL (when auto-execute is off). Re-submits the same question but with `execute: true`.

### ResultsDisplay.jsx
**Responsibility:** Renders whatever the backend returned. Knows nothing about how the data was generated — it just displays it.

- Takes in a single `result` prop (the full `QueryResponse` object from the backend).
- If `result.is_multi_query` is true and `query_steps` exists: renders each step as a card. Each card shows the step number, its SQL in a dark code block, an "Executed" or "Skipped" badge, and row count + timing if it ran.
- If single query: renders the SQL in a dark code block with a "Copy SQL" button, then an explanation card in blue, then the results table.
- The results table maps `execution_result.columns` as headers and `execution_result.rows` as rows. Handles `null` (shown as italic grey), booleans (green true / red false), and everything else as a string.
- At the bottom, renders a metadata bar showing the AI model name, whether it was executed, and the timestamp.

### DatabaseConnectionManager.jsx
**Responsibility:** The "Connectors" tab. Lets the user add, test, remove, and set-default database connections.

- Renders `ProviderSelector` first. When the user picks a provider, it renders `ConnectionForm` pre-filled with that provider's defaults (host, port, SSL mode, placeholder hints).
- On "Test": POSTs to `/databases/test` with the form values. Gets back version info and DB size. Shows a success/error toast.
- On "Save": POSTs to `/databases` to register. On success, reloads the database list.
- On "Remove": DELETEs `/databases/{id}`. Reloads.
- On "Set Default": POSTs to `/databases/{id}/set-default`.

### ProviderSelector.jsx
**Responsibility:** Displays the grid of 20+ cloud/local DB provider cards. Takes nothing from the backend — it's all static data from `providers.js`.

- Each card shows the provider name, a badge (e.g., "PostgreSQL"), an icon, and a short description.
- When clicked, calls `onSelect(provider)` which passes the provider's config object up to `DatabaseConnectionManager`.

### ConnectionForm.jsx
**Responsibility:** The form that collects host, port, database name, username, password, SSL mode. Pre-filled from the selected provider.

- Takes in `provider` (the selected preset config). Uses its `config` object to set default values and its `hints` object for placeholder text on each field.
- Validates port is 1–65535 on the client side before allowing submit.
- Calls `onTest` or `onSave` with the form data as a plain object.

### SchemaViewer.jsx
**Responsibility:** Shows the user what tables and columns exist in their database. Used in the "Databases" tab.

- On mount, calls `GET /schema`. Takes nothing in (uses default DB or a passed `databaseId` prop).
- Renders an expandable tree: each table is a collapsible row, and expanding it shows all columns with their types and whether they're nullable or a primary key.
- If the API call fails, falls back to a hardcoded sample schema so the UI doesn't break.

### MissingFieldsModal.jsx
**Responsibility:** Pops up when the AI couldn't generate SQL because required data was missing. Lets the user fill in the gaps.

- Takes in `missingFields` — an array of `{ table, column, description, data_type, example }` objects from the backend.
- Renders one input per missing field, labeling it with the description and showing the expected data type.
- On submit, calls `onSubmit({ "table.column": "user_typed_value", ... })` back up to `QueryInterface`.

### QueryHistory.jsx
**Responsibility:** Shows the last 20 queries the user ran in this session. Pure display — no API calls.

- Takes in `history` array. Each entry has: question, SQL, explanation, row count, execution time, timestamp, database ID.
- Renders each as a card. Clicking a card could let the user re-run it (copies the question back into the input).

### Toast.jsx + useToast.jsx
**Responsibility:** Global notification system. Any component anywhere can trigger a toast.

- `useToast.jsx` is a React Context. `ToastProvider` wraps the app. Any child calls `useToast()` to get `showSuccess`, `showError`, `showWarning`, `showInfo`.
- Each call pushes a toast into a global list (max 3 stacked). Each toast auto-dismisses after a timeout.
- `Toast.jsx` renders a single toast: color-coded by type, with a close button.

### providers.js
**Responsibility:** Static data file. Contains 20+ provider presets — one object per provider.

- Each object has: `id`, `name`, `dbType`, `fullName`, `description`, `badge`, `icon`, and `config` (default host/port/SSL) and `hints` (placeholder text per field).
- Covers: localhost, Docker, AWS RDS, GCP Cloud SQL, Azure Database, DigitalOcean Managed DB, Supabase, Railway, Render, Heroku, Neon, PlanetScale, and more.

---

## Backend — File by File

### main.py
**Responsibility:** Boots the FastAPI app. Sets up middleware, mounts routes, and runs startup checks.

- `lifespan()` — the async context manager that runs on startup and shutdown.
  - **Startup:** loads `.env`, pings `GET /api/tags` on Ollama to verify it's running and the configured model exists. If DB env vars are set (`DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`), auto-registers that database via `DatabaseConnectionManager.configure()`. Also loads any previously saved databases from disk.
  - **Shutdown:** calls `db_manager.close()` to dispose all async engine pools.
- Registers CORS middleware (origins from settings), attaches the slowapi rate limiter to `app.state`, adds a global exception handler for `NLSQLException` (catches all custom app errors and returns a standardized JSON error response), and mounts `api_router` under `/api/v1`.

### config.py
**Responsibility:** Single source of truth for all settings. Loaded once, cached forever.

- `Settings` class (Pydantic `BaseSettings`): reads every setting from environment variables or `.env`. Has field validators that run at load time:
  - `validate_ollama_url()` — takes the URL string, checks it has a valid scheme (http/https) and host. Returns the URL with trailing slash stripped.
  - `validate_temperature()` — takes a float. Rejects anything outside 0–2.
  - `validate_encryption_key()` — takes the key string. If empty, allows it (a temp key gets generated at runtime). If present, checks it's exactly 44 chars and valid base64.
  - `validate_rate_limit()` — takes an int. Rejects ≤ 0 or > 10000.
  - `validate_max_query_results()` — takes an int. Rejects ≤ 0 or > 100000.
  - `parse_cors_origins()` — takes a string or list. If string, tries JSON parse first, falls back to comma-split.
- `get_settings()` — returns the singleton `Settings` instance. Decorated with `@lru_cache` so it's only constructed once.

### dependencies.py
**Responsibility:** Factory functions for FastAPI's dependency injection system. Keeps endpoint signatures clean.

- `get_sql_generator()` — takes nothing, returns a new `SQLGenerator` instance.
- `get_query_validator()` — takes nothing, returns a new `QueryValidator` instance.
- `get_query_executor()` — takes nothing, returns a new `QueryExecutor` instance.
- These are injected into endpoint functions via FastAPI's `Depends()`.

### exceptions.py
**Responsibility:** The full exception hierarchy. Every error in the app is one of these types.

- `NLSQLException` — base class. Takes `message`, `code`, and `details` dict. All other exceptions inherit from this.
- Database group: `DatabaseConnectionError`, `DatabaseConfigurationError`, `DatabaseNotFoundError`.
- Validation group: `QueryValidationError` (base), `SQLInjectionAttempt`, `ReadOnlyViolation`, `QuerySyntaxError`.
- Execution group: `QueryExecutionError` (base), `QueryTimeoutError`, `ResultLimitExceededError`.
- AI group: `AIAPIError` (base), `AIAPIRateLimitError`, `AIParseError`.
- Schema group: `SchemaIntrospectionError`, `TableNotFoundError`.
- Each sets its own `code` string (e.g., `"SQL_INJECTION_ATTEMPT"`) so the frontend can handle specific errors programmatically.

### middleware/rate_limiter.py
**Responsibility:** Creates the global rate limiter instance that's attached to the app.

- `get_rate_limiter()` — takes nothing. Creates a `slowapi.Limiter` configured with: key function = client IP address, default limit = 60 requests/minute (from settings), storage = in-memory, strategy = fixed-window. Returns the limiter.
- The module-level `limiter` variable holds the singleton. `main.py` attaches it to `app.state`.

### utils/logger.py
**Responsibility:** Sets up structlog and provides helper functions so every module logs consistently.

- `configure_logging()` — takes nothing. Reads `LOG_FORMAT` from settings. If `"json"`: sets up a processor chain that outputs JSON with timestamps, log level, logger name, and stack traces. If anything else: sets up a human-readable console format for dev. Called once at module import time.
- `get_logger(name)` — takes a module name string (typically `__name__`). Returns a bound structlog logger for that module.
- `log_query_execution(logger, query_id, database_id, sql, execution_time_ms, row_count, success, error)` — takes all those params. Logs a standardized "query executed" or "query failed" event. Truncates SQL to 200 chars.
- `log_ai_request(logger, question, model, tokens, success, error)` — takes those params. Logs an "ai_request" or "ai_request_failed" event. Truncates the question to 100 chars.
- `log_security_event(logger, event_type, severity, message)` — takes those params. Logs a "security_event" entry. Dispatches to the correct log level based on the `severity` string.

---

## API Endpoints — Function by Function

### health.py

- `GET /health` — takes nothing. Returns `{ status, version, environment }` from settings.
- `GET /health/database` — takes nothing. Runs `SELECT 1` against the default database. Returns `{ database_configured, database_connected }`.

### database.py

- `POST /databases` — takes a `DatabaseConfigRequest` body (id, host, port, database, username, password, ssl_mode, nickname, db_type). Checks the ID isn't already registered. Calls `db_manager.register_database()`. Then immediately runs `SELECT 1` to verify the connection works. Returns success + the config (no password).
- `GET /databases` — takes nothing. Iterates over every registered DB. For each: gets its config, pings it to check if it's connected, counts its tables via `information_schema`. Returns the full list + which one is the default.
- `GET /databases/{database_id}` — takes a database ID from the URL. Returns that specific DB's info + whether it's the default.
- `DELETE /databases/{database_id}` — takes a database ID. Calls `db_manager.disconnect_database()` which disposes the engine and removes it from memory and disk.
- `POST /databases/{database_id}/set-default` — takes a database ID. Calls `db_manager.set_default_database()`. Persists to disk.
- `POST /databases/test` — takes a `DatabaseConfigRequest` body. Creates a throwaway async engine, connects, runs `SELECT version()` and `pg_size_pretty()`, then disposes the engine. Returns version and DB size. Nothing is persisted.
- `GET /databases/stats` — takes nothing. Runs three queries against the default DB: table count from `information_schema`, DB size via `pg_database_size`, active connections via `pg_stat_activity`. Returns all of it.

### schema.py

- `GET /schema` — takes an optional `database_id` query param. Calls `schema_inspector.get_schema_for_database()` to get tables + columns (cached). Then for each table, queries `pg_index` to find primary key columns and marks them. Returns the full enhanced schema.
- `GET /schema/summary` — takes an optional `database_id`. Calls `schema_inspector.get_schema_summary()` — the same text format that gets sent to the AI. Returns it as a string so you can see exactly what the AI sees.
- `GET /schema/all` — takes nothing. Loops over every registered DB and fetches its schema. Returns a dict keyed by DB ID.
- `POST /schema/cache/clear` — takes nothing. Calls `schema_inspector.clear_cache()`. Forces a fresh DB query on the next request.

### query.py

- `POST /query/natural` — the main endpoint. Takes a `NaturalLanguageQueryRequest` body `{ question, options }` and an optional `database_id` query param. This is the orchestrator — see the "Core Pipeline" section below for exactly what it does step by step.
- `POST /query/sql` — takes a `DirectSQLRequest` body `{ sql }` and optional `database_id`. Validates the SQL (read-only, strict mode), executes it, returns results. No AI involved — the user wrote the SQL themselves.
- `POST /write/preview` — takes a `NaturalLanguageQueryRequest` body. Detects if it's a batch operation (keywords like "all", "inactive", "batch") and calls either `handle_batch_delete_users()` or `handle_delete_user()`. Returns the matching rows and cascade impact without executing any DELETE.
- `POST /write/execute` — takes a `WriteConfirmationRequest` body `{ user_id, operation_type, confirmed }`. Only proceeds if `confirmed` is true. Opens a transaction, calls `execute_delete_user()` which snapshots to audit_log then DELETEs. Returns the result.

---

## Core Modules — Function by Function

### ollama_client.py
**Responsibility:** The only thing that talks to Ollama. Everything else in the AI layer calls this.

- `OllamaClient.__init__()` — takes nothing. Reads `OLLAMA_BASE_URL` and `OLLAMA_MODEL` from settings.
- `OllamaClient.generate_content(prompt)` — takes a prompt string. POSTs to `{base_url}/api/generate` with body `{ model, prompt, stream: false, options: { temperature } }`. Waits up to 60 seconds. Parses the JSON response and returns the `"response"` field (the raw text the model generated). Raises `AIAPIError` if the status code isn't 200, if the response is empty, or if it can't connect.
- `get_ollama_client()` — takes nothing. Returns the module-level singleton `OllamaClient` instance (creates it on first call).

### ollama_sql_generator.py
**Responsibility:** Orchestrates the full "question → SQL" pipeline. The highest-level AI coordinator.

- `SQLGenerator.__init__()` — takes nothing. Creates an `OllamaClient` and a `SchemaInspector`.
- `SQLGenerator._detect_missing_fields(response)` — takes the raw AI response string. Checks if it contains `"MISSING_REQUIRED_FIELDS:"`. If yes, uses a regex `- table.column: description` to extract each missing field into a list of `MissingField` objects. Returns the list, or `None` if no missing fields.
- `SQLGenerator.generate_sql(question, connection, include_schema, read_only, db_id)` — the main function. Takes the user's question, a DB connection, and flags. Does this in order:
  1. Calls `schema_inspector.get_schema_summary()` to get the schema text with sample data.
  2. Calls `build_sql_generation_prompt()` to assemble the prompt.
  3. Calls `ollama_client.generate_content(prompt)` to get the AI response.
  4. Calls `_detect_missing_fields()` — if fields are missing, returns early with an empty SQL and the missing fields list.
  5. Calls `extract_sql_from_response()` to pull SQL out.
  6. Calls `extract_explanation_from_response()` to pull the explanation out.
  7. Returns a tuple: `(sql, explanation, missing_fields_or_None)`.

### prompts.py
**Responsibility:** Builds the text prompts that get sent to Ollama. The prompt is the single most important thing that controls what SQL the AI generates.

- `build_sql_generation_prompt(question, schema_context, database_type, max_limit, read_only)` — takes all of those. If `read_only` is true, the prompt only allows SELECT with LIMIT. If false (write mode), the prompt includes: an operation-keyword map (add→INSERT, delete→DELETE, etc.), naming convention rules (usernames are lowercase + underscores, dates are YYYY-MM-DD, etc.), format-matching rules (match the format shown in sample data), instructions for INSERT/UPDATE/DELETE with examples, the MISSING_REQUIRED_FIELDS protocol, and a [GENERATED] column warning. Returns the full prompt string.
- `build_write_operation_prompt(question, schema_context, database_type, available_extensions)` — takes those params. A more conservative prompt used specifically by `WriteOperationHandler` to generate only a WHERE clause (not a full DELETE statement). Explicitly forbids extension functions like `pg_trgm`. Returns the prompt.
- `extract_sql_from_response(response)` — takes the raw AI response text. Looks for a ````sql ... ``` ` block using regex. Falls back to any generic ``` block. Returns the SQL string inside, or `None` if nothing found.
- `extract_explanation_from_response(response)` — takes the raw response. Strips out code blocks. Looks for an "Explanation:" or "**Explanation:**" header and returns the text after it. Caps at 500 characters. Falls back to the entire non-code text if no header found.

### query_planner.py
**Responsibility:** Detects when a user's request is too complex for a single query and breaks it into ordered steps.

- `IntelligentQueryPlanner.analyze_request(question, schema_context)` — takes the question and schema text. Runs two sets of regex patterns against the question:
  - Dependency patterns: "X has bought Y", "purchased", "assign X to Y" — these mean entities might need to be created first.
  - Multi-operation patterns: "and add", "then create", ", delete" — these mean multiple SQL statements are needed.
  - Also calls `_extract_entities()` to find references to actual table rows (e.g., "user john" maps to the `users` table).
  - Returns `{ requires_dependency_resolution, requires_multi_query, entities, complexity }`.
- `IntelligentQueryPlanner._extract_entities(question, schema_context)` — takes the question and schema. Extracts table names from the schema. For each table, tries to find a pattern like `{singular_table_name} {identifier}` in the question (e.g., "user john" → `{ type: "users", identifier: "john", table: "users" }`). Returns the list.
- `IntelligentQueryPlanner.create_dependency_resolution_plan(question, schema_context, ai_generated_sql, ai_explanation)` — takes those params. If no dependency resolution needed, wraps the single AI SQL in a one-step plan. Otherwise, for each entity: generates an existence-check SELECT, then a conditional INSERT. Appends the main AI-generated SQL as the final step. Returns a `QueryPlan` with all steps in order.
- `_generate_existence_check(table, identifier, schema_context)` — takes table name, the identifier value, and schema. Guesses the identifier column (tries username, name, email, etc.). Returns `SELECT COUNT(*) FROM {table} WHERE {id_column} = '{identifier}'`.
- `_generate_entity_insert(table, identifier, schema_context)` — same inputs. Returns `INSERT INTO {table} ({id_column}) VALUES ('{identifier}')`.
- `_guess_identifier_column(table, schema_context)` — takes table name and schema text. Extracts columns for that table. Checks them against a priority list: username, name, title, email, product_name, item_name, id. Returns the first match.
- `decompose_complex_query(question, schema_context)` — takes the question. Splits it on conjunctions like "and then", "then", "and", ";". Returns a list of individual sub-request strings.

### connection_manager.py
**Responsibility:** Manages all database connections. Handles encryption, persistence, pooling, and multi-DB routing.

- `DatabaseConnectionManager.__init__()` — takes nothing. Initializes empty dicts for engines and configs. Creates the Fernet cipher from the encryption key in settings (or generates a temporary one if none is configured). Then calls `_load_saved_databases()` to restore any previously saved connections.
- `_encrypt_password(password)` — takes a plaintext password string. Encrypts it with Fernet, base64-encodes the result. Returns the encoded string.
- `_decrypt_password(encrypted_password)` — takes an encrypted string. Tries to base64-decode and Fernet-decrypt it. If decryption fails (e.g., it's an old plaintext password from before encryption was added), returns the string as-is. This is the migration path.
- `register_database(db_id, config, save_to_disk)` — takes a DB ID string, a `DatabaseConfig`, and a save flag. Builds the connection URL (PostgreSQL or MySQL format). Creates an `AsyncEngine` with connection pooling (pool size, max overflow, recycle time from settings). Stores the engine and config. If it's the first DB, sets it as default. Optionally saves to disk.
- `_build_connection_string(config)` — takes a `DatabaseConfig`. If `db_type` is mysql: builds `mysql+aiomysql://...`. Otherwise: builds `postgresql+asyncpg://...` with optional `?ssl=` param. Returns the URL string.
- `get_connection(db_id)` — an async context manager. Takes an optional DB ID (defaults to the default DB). Gets the engine, calls `engine.begin()` to open a connection with auto-commit on exit and auto-rollback on exception. Yields the connection.
- `disconnect_database(db_id)` — takes a DB ID. Disposes the engine, removes it from the dicts. If it was the default, picks the next available one. Saves to disk.
- `set_default_database(db_id)` — takes a DB ID. Sets `_default_db_id`. Saves to disk.
- `is_database_connected(db_id)` — takes a DB ID. Opens a connection and runs `SELECT 1`. Returns true/false.
- `_save_databases()` — takes nothing. Encrypts each password, writes the full config dict to `~/.nlsql/databases.json`.
- `_load_saved_databases()` — takes nothing. Reads `~/.nlsql/databases.json`. Decrypts each password. Calls `register_database()` for each (with `save_to_disk=False` to avoid a write loop). Restores the saved default.
- `get_db_manager()` — module-level singleton factory. Takes nothing. Returns the one global `DatabaseConnectionManager` instance.

### schema_inspector.py
**Responsibility:** Reads the database structure. Two-tier caching keeps it fast. Also fetches sample data so the AI can see real values.

- `SchemaInspector.__init__()` — takes nothing. Sets up per-DB TTL caches and a separate AI-prompt cache dict.
- `_validate_identifier(name, identifier_type)` — takes a name string and a type label. Checks: not empty, ≤ 63 chars, matches `^[a-zA-Z_][a-zA-Z0-9_]*$`. Warns if the name is a dangerous keyword like "drop". Raises `ValueError` if invalid. Used before any table name is interpolated into a query.
- `get_schema_version(connection, db_id)` — takes a connection and DB ID. Queries `information_schema.columns` for all public tables. Concatenates table+column+type into a string. Returns the first 8 hex chars of its MD5 hash as an int. This is the "version" — if it changes, the schema changed.
- `get_schema_summary(connection, db_id, max_tables, include_sample_data, sample_rows, for_ai_prompt)` — takes all those params. The main function. If `for_ai_prompt` is true: checks the schema version against the cached version. If unchanged and cached, returns the cached prompt text immediately. Otherwise, fetches fresh. Calls `_get_all_tables_info()` for the structure, then `_get_sample_rows()` for each table. Formats everything into a text block (table name, columns with types, `[GENERATED]` markers, and sample rows as `key=value` pairs). Caches the result in both the TTL cache and (if `for_ai_prompt`) the persistent AI cache.
- `_get_all_tables_info(connection, max_tables)` — takes a connection and a table limit. Queries `information_schema.columns` for the public schema. Groups columns by table. Detects `is_generated = ALWAYS`. Returns a list of `{ name, columns }` dicts.
- `_get_sample_rows(connection, table_name, limit)` — takes a connection, a table name, and a row limit. First validates the table name via `_validate_identifier()`. Then runs `SELECT * FROM "{table_name}" LIMIT {limit}` (double-quoted for safety). Converts each row to a dict, coercing non-basic types to strings. Returns the list.
- `get_table_info(connection, table_name)` — takes a connection and a table name. Queries `information_schema.columns` for just that table. Raises `TableNotFoundError` if no rows come back. Returns `{ name, columns, column_count }`.
- `clear_cache_for_database(db_id)` / `clear_all_caches()` — clear the TTL caches.

### validator.py
**Responsibility:** The gatekeeper. Every piece of SQL passes through here before it runs. Runs checks in a specific order.

- `QueryValidator.__init__()` — takes nothing. Creates a `SQLSanitizer` and reads settings.
- `validate_operation_intent(sql, original_question)` — takes the generated SQL and the original question. Detects what the user meant (insert keywords: "add", "create", "new"; delete keywords: "delete", "remove"; update keywords: "update", "change", "modify"). Detects what the SQL actually does (starts with INSERT, DELETE, UPDATE). If there's a dangerous mismatch — user said "add" but SQL is DELETE, or user said "delete" but SQL is INSERT — raises `QueryValidationError` with a CRITICAL SAFETY ERROR message.
- `validate(sql, read_only, original_question, strict_validation)` — the main entry point. Takes the SQL string and flags. Does this in order:
  1. Empty check — raises if blank.
  2. Intent mismatch — only runs if `strict_validation` is true AND `read_only` is false. Calls `validate_operation_intent()`.
  3. Sanitizer — calls `SQLSanitizer.validate_and_raise()`. In read-only mode: strict (blocks everything suspicious). In write mode: lenient (only blocks truly dangerous stuff, logs warnings for the rest).
  4. Parse — runs `sqlparse.parse()`. Raises `QuerySyntaxError` if it fails.
  5. Multi-statement check — if `sqlparse` returns more than one statement, raises.
  6. LIMIT enforcement — only for SELECT in read-only mode. Calls `_enforce_limit()`.
  - Returns the (possibly modified) SQL string.
- `_enforce_limit(sql)` — takes a SQL string. If LIMIT already exists: checks if it exceeds `MAX_QUERY_RESULTS` (1000), caps it if so. If no LIMIT exists: appends `LIMIT {DEFAULT_QUERY_LIMIT}` (100). Returns the modified SQL.

### sql_sanitizer.py
**Responsibility:** Pattern-based security filter. Scans SQL for known attack patterns.

- `BLOCKED_PATTERNS` — a class-level list of `(regex, description)` tuples covering: DDL (DROP/CREATE/ALTER/TRUNCATE/RENAME), system commands (EXECUTE/xp_cmdshell), SQL comments (-- and /* */), multiple statements (`;` followed by a word), UNION injection, information_schema access, PostgreSQL dangerous functions (pg_read_file, pg_sleep, lo_import, etc.), MySQL dangerous functions (LOAD_FILE, INTO OUTFILE), hex encoding (0x...), unicode encoding (\u...).
- `is_safe(sql, allow_write, strict_mode)` — takes the SQL, a write-allowed flag, and a strict flag. Normalizes the SQL to uppercase. Iterates over every blocked pattern. In non-strict mode (lenient): skips the checks for comments, hex, and unicode (those are valid in many write scenarios). Returns `(is_safe_bool, list_of_violation_strings)`.
- `validate_and_raise(sql, allow_write, strict_mode)` — takes the same params. Calls `is_safe()`. If not safe, raises `SQLInjectionAttempt` with the first violation as the pattern.
- `strip_comments(sql)` — takes a SQL string. Removes `--` single-line comments and `/* */` multi-line comments. Returns the cleaned SQL.

### executor.py
**Responsibility:** Actually runs the SQL against the database. Handles timeouts and result serialization.

- `QueryExecutor.__init__()` — takes nothing. Reads timeout setting.
- `execute(connection, sql, timeout_seconds)` — takes a connection, SQL string, and optional timeout (defaults to 30s from settings). Wraps `_execute_query()` in `asyncio.wait_for()` with that timeout. Measures execution time. Returns `(results_list, execution_time_ms)`. Raises `QueryTimeoutError` if it takes too long.
- `_execute_query(connection, sql)` — takes a connection and SQL. Runs `connection.execute(text(sql))`. If it's a write operation (starts with DELETE/UPDATE/INSERT): returns `[{ operation: "write", affected_rows: N, message: "..." }]`. If it's a SELECT: fetches all rows, converts each to a dict using `_serialize_value()` on every cell.
- `_serialize_value(value)` — takes a single database value. Converts: `Decimal` → `float`, `datetime`/`date` → ISO format string, `bytes` → UTF-8 string (falls back to `str()` if not valid UTF-8), `None` stays `None`. Everything else passes through.

### write_operation_handler.py
**Responsibility:** The safe DELETE workflow. Enforces preview-before-execute and audit logging.

- `WriteOperationHandler.__init__()` — takes nothing. Creates an `OllamaClient` and `SchemaInspector`.
- `handle_delete_user(question, connection)` — takes the user's question and a DB connection. Calls `_generate_where_clause()` to get a WHERE clause from the AI. Calls `_find_matching_users()` to run a SELECT with that WHERE. If 0 matches: returns an error. If 1 match: calls `_analyze_cascade_impact()` and returns the impact for confirmation. If multiple matches: returns them for the user to pick one.
- `handle_batch_delete_users(question, connection)` — same inputs. Same WHERE-clause generation, but no LIMIT on the SELECT. Runs `_analyze_cascade_impact()` for every matching user. Returns the total cascade impact across all of them.
- `_generate_where_clause(question, connection)` — takes the question and connection. Gets the schema, calls `build_write_operation_prompt()`, sends it to Ollama. Extracts the WHERE clause from the response using regex. Returns the WHERE string (e.g., `WHERE username = 'alice_brown'`).
- `_find_matching_users(where_clause, connection)` — takes a WHERE clause string. Runs `SELECT id, username, email, full_name, created_at, is_active FROM users {where_clause} LIMIT 10`. Returns the rows as dicts.
- `_analyze_cascade_impact(user_id, connection)` — takes a user ID and connection. Counts orders for that user. Counts order_items for those orders. Gets order details. Returns `{ user_id, orders_count, order_items_count, total_records, order_details }`.
- `_log_to_audit(user_id, user_data, impact, connection, performed_by)` — takes all those params. Inserts a row into `audit_log` with the operation type, table, record ID, a JSON snapshot of the record, the cascade impact as JSON, and who did it.
- `execute_delete_user(user_id, connection, performed_by)` — takes a user ID, connection, and performer label. Fetches the user's full row (for the snapshot). Calls `_analyze_cascade_impact()`. Calls `_log_to_audit()`. Then runs `DELETE FROM users WHERE id = {user_id}`. Returns `{ success, deleted_count, cascade_impact, audit_logged }`. Must be called inside a transaction.

---

## The Main Pipeline — Step by Step

This is what happens inside `query.py → natural_language_query()` when a request comes in:

```
1. Figure out which database to use
      Takes: database_id from query param, or db_manager._default_db_id
      Checks: DB is registered, DB exists

2. Open a connection to that database
      Uses: db_manager.get_connection(target_db_id)
      This is an async context manager — auto-commits on success, rolls back on error

3. Call SQLGenerator.generate_sql()
      Passes in: question, connection, read_only flag, db_id
      Inside this:
        → SchemaInspector fetches schema + sample data (cached)
        → prompts.py assembles the prompt
        → OllamaClient sends it to Ollama
        → Response is parsed for SQL and explanation
      Returns: (sql, explanation, missing_fields)

4. Check for missing fields
      If missing_fields is not None:
        → Return early with requires_user_input: true
        → Frontend will show MissingFieldsModal
        → User fills in values → question is re-submitted with them appended

5. Run the query planner
      Calls: IntelligentQueryPlanner.analyze_request(question, schema_context)
      If complexity is "complex" (dependency resolution needed):
        → create_dependency_resolution_plan() builds a multi-step plan
        → Each step is validated and executed in order
        → Existence-check steps set a flag; if entity exists, the next INSERT step is skipped
      If complexity is "simple":
        → Falls through to single-query path

6. Validate the SQL
      Calls: QueryValidator.validate(sql, read_only, original_question)
      This runs: sanitizer → parse → single-statement check → LIMIT enforcement
      Raises an exception if anything is wrong — the endpoint catches it and returns an error

7. Execute the SQL (if options.execute is true)
      Calls: QueryExecutor.execute(connection, validated_sql)
      Returns rows + execution time
      Serializes all values to JSON-safe types

8. Build and return the response
      Assembles a QueryResponse with: SQL, explanation, execution result, warnings, metadata
      Metadata includes: database_id, nickname, model name, timestamp, flags
```

---

## API Endpoints Summary

| Method | Path | Purpose |
|---|---|---|
| POST | /api/v1/query/natural | Convert NL question to SQL, optionally execute |
| POST | /api/v1/query/sql | Execute raw SQL directly |
| POST | /api/v1/write/preview | Preview DELETE impact (cascade analysis) |
| POST | /api/v1/write/execute | Execute confirmed DELETE with audit log |
| GET | /api/v1/databases | List all registered databases |
| POST | /api/v1/databases | Register a new database |
| DELETE | /api/v1/databases/{id} | Remove a database |
| POST | /api/v1/databases/{id}/set-default | Set a database as default |
| POST | /api/v1/databases/test | Test connectivity without registering |
| GET | /api/v1/databases/stats | PostgreSQL server stats |
| GET | /api/v1/schema | Full schema (tables, columns, primary keys) |
| GET | /api/v1/schema/summary | Schema as the text the AI sees |
| GET | /api/v1/schema/all | Schemas for all registered databases |
| POST | /api/v1/schema/cache/clear | Bust the schema cache |
| GET | /api/v1/health | App status and version |
| GET | /api/v1/health/database | Database ping check |
