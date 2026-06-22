#!/bin/sh
# quickstart.sh — one-command installer for Natural Language SQL Engine
# Usage: sh quickstart.sh   (or: curl -fsSL <raw-url>/quickstart.sh | sh)
# Idempotent: safe to run multiple times.
set -eu

REPO_RAW="https://raw.githubusercontent.com/jmanoj0905/natural-language-sql/main"

# ---------------------------------------------------------------------------
# 1. Preflight checks
# ---------------------------------------------------------------------------
if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: 'docker' not found. Install Docker Desktop from https://docs.docker.com/get-docker/ and retry." >&2
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "ERROR: 'docker compose' (v2) not found. Upgrade Docker Desktop to 4.x+ or install the compose plugin." >&2
  exit 1
fi

# ---------------------------------------------------------------------------
# 2. Download config files if absent
# ---------------------------------------------------------------------------
if [ ! -f docker-compose.yml ]; then
  echo "Downloading docker-compose.yml ..."
  curl -fsSL "${REPO_RAW}/docker-compose.yml" -o docker-compose.yml
else
  echo "docker-compose.yml already present — skipping download."
fi

if [ ! -f .env.example ]; then
  echo "Downloading .env.example ..."
  curl -fsSL "${REPO_RAW}/.env.example" -o .env.example
else
  echo ".env.example already present — skipping download."
fi

# ---------------------------------------------------------------------------
# 3. Start the stack
# ---------------------------------------------------------------------------
echo "Starting Natural Language SQL Engine ..."
docker compose up -d

# ---------------------------------------------------------------------------
# 4. Done
# ---------------------------------------------------------------------------
echo ""
echo "Stack is up. Open http://localhost:3000"
echo ""
echo "Notes:"
echo "  - The Ollama model download runs in the background; SQL generation"
echo "    will work once 'nlsql-ollama-pull' exits (check: docker compose logs -f ollama-pull)."
echo "  - To stop: docker compose down"
echo "  - Your database credentials are encrypted and persisted in the"
echo "    'nlsql_data' Docker volume — they survive restarts automatically."
