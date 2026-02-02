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
  ${GREEN}dev${NC}              Start development environment (frontend + backend + DB)
  ${GREEN}prod${NC}             Start production mode (backend only)
  ${GREEN}setup-ollama${NC}     Setup Docker Ollama with llama3.2
  ${GREEN}stop${NC}             Stop all running services
  ${GREEN}clean${NC}            Clean up containers, logs, and temp files
  ${GREEN}logs${NC}             Show application logs
  ${GREEN}help${NC}             Show this help message

${YELLOW}Development Options:${NC}
  ${GREEN}--verbose, -v${NC}    Show detailed logs in real-time
  ${GREEN}--skip-ollama${NC}    Skip Ollama setup

${YELLOW}Examples:${NC}
  ./run.sh dev              # Start development environment
  ./run.sh dev --verbose    # Start with live logs
  ./run.sh setup-ollama     # Setup Docker Ollama
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
SKIP_OLLAMA=false

# Cleanup function
cleanup() {
    echo ""
    print_header "Shutting Down Services"

    [ ! -z "$TAIL_PID" ] && kill $TAIL_PID 2>/dev/null || true

    if [ ! -z "$FRONTEND_PID" ]; then
        print_info "Stopping frontend..."
        kill -TERM -$FRONTEND_PID 2>/dev/null || kill $FRONTEND_PID 2>/dev/null || true
        sleep 1
        kill -9 -$FRONTEND_PID 2>/dev/null || kill -9 $FRONTEND_PID 2>/dev/null || true
    fi

    if [ ! -z "$BACKEND_PID" ]; then
        print_info "Stopping backend..."
        kill -TERM -$BACKEND_PID 2>/dev/null || kill $BACKEND_PID 2>/dev/null || true
        sleep 1
        kill -9 -$BACKEND_PID 2>/dev/null || kill -9 $BACKEND_PID 2>/dev/null || true
    fi

    lsof -ti:8000 | xargs kill -9 2>/dev/null || true
    lsof -ti:3000 | xargs kill -9 2>/dev/null || true

    print_success "All services stopped"
    exit 0
}

trap cleanup EXIT INT TERM

#=============================================================================
# COMMAND: setup-ollama
#=============================================================================
cmd_setup_ollama() {
    print_header "Docker Ollama Setup"

    if ! docker info > /dev/null 2>&1; then
        print_error "Docker is not running. Please start Docker first."
        exit 1
    fi

    print_success "Docker is running"
    print_info "Starting Ollama container..."
    docker compose up -d ollama

    print_info "Waiting for Ollama to be ready..."
    sleep 5

    if ! docker ps | grep -q nlsql-ollama; then
        print_error "Failed to start Ollama container"
        exit 1
    fi

    print_success "Ollama container is running"
    print_info "Pulling llama3.2 model (this may take a few minutes)..."
    docker exec -it nlsql-ollama ollama pull llama3.2

    print_success "llama3.2 model downloaded successfully"
    echo ""
    docker exec nlsql-ollama ollama list

    print_header "Setup Complete!"
    print_info "Ollama is now running at: http://localhost:11434"
    print_info "Model: llama3.2"
    echo ""
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
    command -v docker &> /dev/null || { print_error "Docker not installed"; exit 1; }

    print_success "All prerequisites met"

    # Start Docker Ollama
    print_header "Starting Docker Ollama"
    if docker ps | grep -q nlsql-ollama; then
        print_success "Ollama container already running"
    else
        print_info "Starting Ollama container..."
        docker compose up -d ollama
        sleep 3
        print_success "Ollama container started"
    fi

    # Start PostgreSQL
    print_header "Starting PostgreSQL Database"
    if docker ps | grep -q "nlsql-postgres"; then
        print_success "PostgreSQL already running"
    else
        print_info "Starting PostgreSQL..."
        docker compose up -d postgres
        sleep 5
        print_success "PostgreSQL started"
    fi

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
    echo -e "${BLUE}Database:${NC}      PostgreSQL on localhost:5432"
    echo -e "${BLUE}AI Model:${NC}      Docker Ollama llama3.2"
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

    print_info "Stopping Docker containers..."
    docker compose stop 2>/dev/null || true

    print_success "All services stopped"
}

#=============================================================================
# COMMAND: clean
#=============================================================================
cmd_clean() {
    print_header "Cleaning Up"

    read -p "This will remove containers, logs, and cache. Continue? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_info "Cancelled"
        exit 0
    fi

    print_info "Stopping services..."
    cmd_stop

    print_info "Removing Docker containers..."
    docker compose down 2>/dev/null || true

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
        --skip-ollama) SKIP_OLLAMA=true ;;
    esac
done

# Auto-setup Ollama if not running and command is dev
if [ "$COMMAND" = "dev" ]; then
    if ! docker ps | grep -q nlsql-ollama 2>/dev/null; then
        print_info "Ollama not running. Setting up Docker Ollama..."
        cmd_setup_ollama
        echo ""
    fi
fi

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
