#!/bin/bash
# Natural Language SQL Engine - Unified Management Script
# Usage: ./run.sh [COMMAND] [OPTIONS]

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Print functions
print_info() { echo -e "${BLUE}[INFO] ${1}${NC}"; }
print_success() { echo -e "${GREEN}[SUCCESS] ${1}${NC}"; }
print_error() { echo -e "${RED}[ERROR] ${1}${NC}"; }
print_warning() { echo -e "${YELLOW}[WARNING] ${1}${NC}"; }
print_header() {
    echo -e "\n${BLUE}========================================${NC}"
    echo -e "${BLUE}  ${1}${NC}"
    echo -e "${BLUE}========================================${NC}\n"
}

# Show usage
show_usage() {
    cat << EOF
${BLUE}Natural Language SQL Engine - Management Script${NC}

${YELLOW}Usage:${NC}
  ./run.sh ${GREEN}COMMAND${NC} [OPTIONS]

${YELLOW}Commands:${NC}
  ${GREEN}dev${NC}              Start development environment (frontend + backend + Ollama)
  ${GREEN}prod${NC}             Start production mode (backend only)
  ${GREEN}setup-ollama${NC}     Install Ollama and pull the SQL model
  ${GREEN}stop${NC}             Stop all running services
  ${GREEN}clean${NC}            Clean up logs and temp files
  ${GREEN}logs${NC}             Show application logs
  ${GREEN}help${NC}             Show this help message

${YELLOW}Development Options:${NC}
  ${GREEN}--verbose, -v${NC}    Show detailed logs in real-time

${YELLOW}Examples:${NC}
  ./run.sh dev              # Start development environment
  ./run.sh dev --verbose    # Start with live logs
  ./run.sh setup-ollama     # Install Ollama + pull model
  ./run.sh stop             # Stop all services
  ./run.sh clean            # Clean up everything

${YELLOW}Quick Start:${NC}
  1. ./run.sh setup-ollama  # First time only
  2. ./run.sh dev           # Start development
  3. Open http://localhost:3000

EOF
}

# Parse global options
VERBOSE=false

# Cleanup function
cleanup() {
    echo ""
    print_header "Shutting Down Services"

    [ -n "$TAIL_PID" ] && kill $TAIL_PID 2>/dev/null || true

    if [ -n "$FRONTEND_PID" ]; then
        print_info "Stopping frontend..."
        kill -TERM -$FRONTEND_PID 2>/dev/null || kill $FRONTEND_PID 2>/dev/null || true
        sleep 1
        kill -9 -$FRONTEND_PID 2>/dev/null || kill -9 $FRONTEND_PID 2>/dev/null || true
    fi

    if [ -n "$BACKEND_PID" ]; then
        print_info "Stopping backend..."
        kill -TERM -$BACKEND_PID 2>/dev/null || kill $BACKEND_PID 2>/dev/null || true
        sleep 1
        kill -9 -$BACKEND_PID 2>/dev/null || kill -9 $BACKEND_PID 2>/dev/null || true
    fi

    # Only stop Ollama if we started it ourselves (leave managed services alone)
    if [ -n "$OLLAMA_SERVE_PID" ]; then
        print_info "Stopping ollama serve..."
        kill $OLLAMA_SERVE_PID 2>/dev/null || true
    fi

    lsof -ti:8000 | xargs kill -9 2>/dev/null || true
    lsof -ti:3000 | xargs kill -9 2>/dev/null || true

    print_success "All services stopped"
    exit 0
}

trap cleanup EXIT INT TERM

# PID of a background `ollama serve` we may have started ourselves
OLLAMA_SERVE_PID=""

#=============================================================================
# COMMAND: setup-ollama
#=============================================================================
cmd_setup_ollama() {
    print_header "Ollama Setup"

    # Install if missing
    if ! command -v ollama &> /dev/null; then
        if command -v brew &> /dev/null; then
            print_info "Installing Ollama via Homebrew..."
            brew install ollama
        else
            print_error "Homebrew not found. Install Ollama manually from https://ollama.com/download"
            exit 1
        fi
    else
        print_success "Ollama already installed ($(ollama --version 2>/dev/null || echo 'unknown version'))"
    fi

    # Bring the service up (reuses ensure_ollama logic)
    ensure_ollama

    print_header "Setup Complete!"
    print_info "Ollama is running at: http://localhost:11434"
    print_info "Model: ${OLLAMA_MODEL_NAME}"
    echo ""
    ollama list
}

#=============================================================================
# ollama_start_service — attempt to start the Ollama daemon
#   Returns 0 if we believe we issued a start command, 1 if nothing to try.
#   Does NOT wait for readiness — caller does that.
#=============================================================================
ollama_start_service() {
    if ! command -v ollama &> /dev/null; then
        print_error "Ollama not installed. Run: ./run.sh setup-ollama"
        exit 1
    fi

    # macOS: prefer launchctl (works for both brew formula and .app installs)
    local launchctl_label=""
    if launchctl list 2>/dev/null | grep -q "homebrew.mxcl.ollama"; then
        launchctl_label="homebrew.mxcl.ollama"
    elif launchctl list 2>/dev/null | grep -q "com.ollama.ollama"; then
        launchctl_label="com.ollama.ollama"
    fi

    if [ -n "$launchctl_label" ]; then
        print_info "Starting Ollama via launchctl ($launchctl_label)..."
        launchctl kickstart -k "gui/$(id -u)/$launchctl_label" 2>/dev/null || \
            launchctl start "$launchctl_label" 2>/dev/null || true
        return 0
    fi

    # Fallback: brew services (Linux or non-launchctl macOS)
    if command -v brew &> /dev/null && brew services list 2>/dev/null | grep -q "^ollama"; then
        print_info "Starting Ollama via brew services..."
        brew services start ollama 2>/dev/null || true
        return 0
    fi

    # Last resort: spawn directly
    print_info "Spawning ollama serve in background..."
    ollama serve > /tmp/ollama-serve.log 2>&1 &
    OLLAMA_SERVE_PID=$!
    return 0
}

#=============================================================================
# ensure_ollama — make sure Ollama is up and the model is available
#=============================================================================
ensure_ollama() {
    # ── 1. Read the model name from .env ──────────────────────────────────
    OLLAMA_MODEL_NAME=$(grep '^OLLAMA_MODEL=' .env 2>/dev/null \
        | cut -d= -f2 | tr -d '"' | tr -d "'" | tr -d '[:space:]')
    OLLAMA_MODEL_NAME="${OLLAMA_MODEL_NAME:-mannix/defog-llama3-sqlcoder-8b}"

    # ── 2. Check if API is already up ─────────────────────────────────────
    if curl -sf http://localhost:11434/api/tags > /dev/null 2>&1; then
        print_success "Ollama is running"
    else
        print_info "Ollama is not running — attempting to start..."
        ollama_start_service

        # Wait up to 20 s for the API to become available
        local ready=false
        for i in $(seq 1 20); do
            if curl -sf http://localhost:11434/api/tags > /dev/null 2>&1; then
                ready=true
                break
            fi
            sleep 1
        done

        if [ "$ready" = false ]; then
            print_error "Ollama did not respond after 20 s. Check logs or run: ollama serve"
            [ -n "$OLLAMA_SERVE_PID" ] && cat /tmp/ollama-serve.log 2>/dev/null || true
            exit 1
        fi
        print_success "Ollama is running"
    fi

    # ── 3. Check the model is available; pull if not ──────────────────────
    print_info "Checking model: ${OLLAMA_MODEL_NAME}..."

    local model_base="${OLLAMA_MODEL_NAME%%:*}"
    if ollama list 2>/dev/null | grep -qi "^${model_base}"; then
        print_success "Model '${OLLAMA_MODEL_NAME}' is installed"
    else
        print_warning "Model '${OLLAMA_MODEL_NAME}' not found locally — pulling now (may take a few minutes)..."
        ollama pull "$OLLAMA_MODEL_NAME" || {
            print_error "Failed to pull '${OLLAMA_MODEL_NAME}'. Check your internet connection."
            exit 1
        }
        print_success "Model '${OLLAMA_MODEL_NAME}' pulled"
    fi

    # ── 4. Warm up — load the model into memory now so the first query is instant
    print_info "Loading model into memory (this takes ~20s for first load)..."
    local warm_response
    warm_response=$(curl -sf --max-time 60 \
        -X POST http://localhost:11434/api/generate \
        -H 'Content-Type: application/json' \
        -d "{\"model\": \"${OLLAMA_MODEL_NAME}\", \"prompt\": \"SELECT\", \"stream\": false}" \
        2>/dev/null)

    if [ $? -eq 0 ]; then
        print_success "Model '${OLLAMA_MODEL_NAME}' is loaded and ready"
    else
        print_warning "Warm-up timed out — model will load on first query (may be slow)"
    fi
}

#=============================================================================
# COMMAND: dev (Development Mode)
#=============================================================================
cmd_dev() {
    cd "$(dirname "$0")"

    print_header "Natural Language SQL Engine - Development Mode"

    # Check prerequisites
    print_header "Checking Prerequisites"

    if command -v uv &> /dev/null; then
        PYTHON_VERSION=$(uv run python --version 2>&1 | awk '{print $2}')
        print_success "uv found (Python $PYTHON_VERSION)"
        USE_UV=true
    elif command -v python3 &> /dev/null; then
        PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
        print_success "Python $PYTHON_VERSION found"
        USE_UV=false
    else
        print_error "Neither uv nor Python 3 is installed"
        exit 1
    fi

    command -v node &> /dev/null || { print_error "Node.js not installed"; exit 1; }
    command -v npm &> /dev/null || { print_error "npm not installed"; exit 1; }

    print_success "All prerequisites met"

    # Start Ollama
    print_header "Starting Ollama"
    ensure_ollama

    # Start Backend
    print_header "Starting Backend (FastAPI)"

    [ ! -d ".venv" ] && {
        print_info "Creating virtual environment..."
        [ "$USE_UV" = true ] && uv venv || python3 -m venv .venv
    }

    if [ ! -f ".venv/.requirements_installed" ] || [ requirements.txt -nt .venv/.requirements_installed ]; then
        print_info "Installing dependencies..."
        if [ "$USE_UV" = true ]; then
            uv pip install -r requirements.txt
        else
            .venv/bin/pip install -q --upgrade pip
            .venv/bin/pip install -q -r requirements.txt
        fi
        touch .venv/.requirements_installed
    fi

    [ ! -f ".env" ] && [ -f ".env.example" ] && cp .env.example .env

    mkdir -p logs
    lsof -ti:8000 | xargs kill -9 2>/dev/null || true

    print_info "Starting backend on http://localhost:8000..."
    if [ "$USE_UV" = true ]; then
        uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 > logs/backend.log 2>&1 &
    else
        .venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 > logs/backend.log 2>&1 &
    fi
    BACKEND_PID=$!

    sleep 5
    if curl -s http://localhost:8000/api/v1/health > /dev/null 2>&1; then
        print_success "Backend started"
    else
        print_error "Backend failed to start. Check logs/backend.log"
        exit 1
    fi

    # Start Frontend
    print_header "Starting Frontend (React + Vite)"
    cd frontend

    [ ! -d "node_modules" ] && {
        print_info "Installing dependencies..."
        npm install --silent
    }

    lsof -ti:3000 | xargs kill -9 2>/dev/null || true

    print_info "Starting frontend on http://localhost:3000..."
    npm run dev > ../logs/frontend.log 2>&1 &
    FRONTEND_PID=$!

    sleep 5
    if curl -s http://localhost:3000 > /dev/null 2>&1; then
        print_success "Frontend started"
    else
        print_error "Frontend failed to start. Check logs/frontend.log"
        cd ..
        exit 1
    fi
    cd ..

    # Summary
    print_header "All Services Running!"
    echo -e "${GREEN}================================================${NC}"
    echo -e "${GREEN}  Natural Language SQL Engine is READY!       ${NC}"
    echo -e "${GREEN}================================================${NC}"
    echo ""
    echo -e "${BLUE}Frontend:${NC}      http://localhost:3000"
    echo -e "${BLUE}Backend API:${NC}   http://localhost:8000"
    echo -e "${BLUE}API Docs:${NC}      http://localhost:8000/docs"
    echo -e "${BLUE}AI Model:${NC}      Ollama ${OLLAMA_MODEL_NAME}"
    echo ""
    echo -e "${RED}To stop:${NC} Press ${YELLOW}Ctrl+C${NC}"
    echo ""

    # Monitor
    if [ "$VERBOSE" = true ]; then
        tail -f logs/backend.log logs/frontend.log 2>/dev/null &
        TAIL_PID=$!
    fi

    while true; do
        kill -0 $BACKEND_PID 2>/dev/null || { print_error "Backend died"; exit 1; }
        kill -0 $FRONTEND_PID 2>/dev/null || { print_error "Frontend died"; exit 1; }
        sleep 10
    done
}

#=============================================================================
# COMMAND: prod (Production Mode)
#=============================================================================
cmd_prod() {
    cd "$(dirname "$0")"
    print_header "Starting Production Mode"

    [ ! -f ".env" ] && { print_error ".env file not found"; exit 1; }

    ensure_ollama

    export $(cat .env | grep -v '^#' | xargs)

    if [ -d ".venv" ]; then
        .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
    else
        uvicorn app.main:app --host 0.0.0.0 --port 8000
    fi
}

#=============================================================================
# COMMAND: stop
#=============================================================================
cmd_stop() {
    print_header "Stopping All Services"

    print_info "Killing processes on ports 3000 and 8000..."
    lsof -ti:3000 | xargs kill -9 2>/dev/null || true
    lsof -ti:8000 | xargs kill -9 2>/dev/null || true

    print_success "All services stopped"
}

#=============================================================================
# COMMAND: clean
#=============================================================================
cmd_clean() {
    print_header "Cleaning Up"

    read -p "This will remove logs and cache. Continue? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_info "Cancelled"
        exit 0
    fi

    print_info "Stopping services..."
    cmd_stop

    print_info "Cleaning logs..."
    rm -rf logs/*.log logs/*.log.* 2>/dev/null || true

    print_info "Cleaning Python cache..."
    find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    find . -type f -name "*.pyc" -delete 2>/dev/null || true

    print_info "Cleaning Node modules cache..."
    rm -rf frontend/.vite 2>/dev/null || true

    print_success "Cleanup complete"
}

#=============================================================================
# COMMAND: logs
#=============================================================================
cmd_logs() {
    if [ ! -d "logs" ]; then
        print_error "No logs directory found"
        exit 1
    fi

    print_header "Application Logs"
    echo -e "${YELLOW}Choose log to view:${NC}"
    echo "1) Backend"
    echo "2) Frontend"
    echo "3) Both (follow)"
    read -p "Selection: " choice

    case $choice in
        1) [ -f "logs/backend.log" ] && cat logs/backend.log || print_error "No backend log" ;;
        2) [ -f "logs/frontend.log" ] && cat logs/frontend.log || print_error "No frontend log" ;;
        3) tail -f logs/backend.log logs/frontend.log 2>/dev/null ;;
        *) print_error "Invalid choice" ;;
    esac
}

#=============================================================================
# Main Command Router
#=============================================================================
COMMAND=${1:-dev}
shift 2>/dev/null || true

# Parse remaining options
for arg in "$@"; do
    case $arg in
        --verbose|-v) VERBOSE=true ;;
    esac
done

case $COMMAND in
    dev)           cmd_dev ;;
    prod)          cmd_prod ;;
    setup-ollama)  cmd_setup_ollama ;;
    stop)          cmd_stop ;;
    clean)         cmd_clean ;;
    logs)          cmd_logs ;;
    help|--help|-h) show_usage ;;
    *)
        print_error "Unknown command: $COMMAND"
        echo ""
        show_usage
        exit 1
        ;;
esac
