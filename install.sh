#!/bin/bash
# Natural Language SQL Engine - Installation Script
# Detects system configuration and installs dependencies

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# Print functions
print_info() { echo -e "${BLUE}[INFO] ${1}${NC}"; }
print_success() { echo -e "${GREEN}[✓] ${1}${NC}"; }
print_error() { echo -e "${RED}[✗] ${1}${NC}"; }
print_warning() { echo -e "${YELLOW}[!] ${1}${NC}"; }
print_header() {
    echo -e "\n${CYAN}========================================${NC}"
    echo -e "${CYAN}  ${1}${NC}"
    echo -e "${CYAN}========================================${NC}\n"
}

# Detect OS
detect_os() {
    if [[ "$OSTYPE" == "darwin"* ]]; then
        OS="macos"
        OS_NAME="macOS"
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        OS="linux"
        if [ -f /etc/os-release ]; then
            . /etc/os-release
            OS_NAME="$NAME"
        else
            OS_NAME="Linux"
        fi
    elif [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "cygwin" ]]; then
        OS="windows"
        OS_NAME="Windows (WSL/Git Bash)"
    else
        OS="unknown"
        OS_NAME="Unknown"
    fi
}

# Detect CPU architecture
detect_arch() {
    ARCH=$(uname -m)
    case $ARCH in
        x86_64)
            ARCH_NAME="x86_64 (Intel/AMD 64-bit)"
            ;;
        arm64|aarch64)
            ARCH_NAME="ARM64 (Apple Silicon / ARM)"
            ;;
        armv7l)
            ARCH_NAME="ARMv7 (32-bit)"
            ;;
        *)
            ARCH_NAME="$ARCH"
            ;;
    esac
}

# Check if command exists
command_exists() {
    command -v "$1" &> /dev/null
}

# Check Docker installation
check_docker() {
    if command_exists docker; then
        DOCKER_VERSION=$(docker --version | cut -d ' ' -f3 | tr -d ',')
        print_success "Docker installed (version $DOCKER_VERSION)"

        # Check if Docker daemon is running
        if docker info > /dev/null 2>&1; then
            print_success "Docker daemon is running"
            return 0
        else
            print_warning "Docker is installed but not running"
            echo -e "  ${YELLOW}Please start Docker Desktop and run this script again${NC}"
            return 1
        fi
    else
        print_error "Docker not found"
        return 1
    fi
}

# Check Python installation
check_python() {
    if command_exists uv; then
        PYTHON_VERSION=$(uv run python --version 2>&1 | awk '{print $2}')
        print_success "uv found (Python $PYTHON_VERSION) - recommended!"
        PYTHON_CMD="uv"
        return 0
    elif command_exists python3; then
        PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
        PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
        PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)

        if [ "$PYTHON_MAJOR" -ge 3 ] && [ "$PYTHON_MINOR" -ge 12 ]; then
            print_success "Python $PYTHON_VERSION installed"
            PYTHON_CMD="python3"
            return 0
        else
            print_warning "Python $PYTHON_VERSION found, but 3.12+ recommended"
            PYTHON_CMD="python3"
            return 0
        fi
    else
        print_error "Python 3 not found"
        return 1
    fi
}

# Check Node.js installation
check_node() {
    if command_exists node; then
        NODE_VERSION=$(node --version | cut -d 'v' -f2)
        NODE_MAJOR=$(echo $NODE_VERSION | cut -d. -f1)

        if [ "$NODE_MAJOR" -ge 18 ]; then
            print_success "Node.js $NODE_VERSION installed"
            return 0
        else
            print_warning "Node.js $NODE_VERSION found, but v18+ recommended"
            return 0
        fi
    else
        print_error "Node.js not found"
        return 1
    fi
}

# Check npm installation
check_npm() {
    if command_exists npm; then
        NPM_VERSION=$(npm --version)
        print_success "npm $NPM_VERSION installed"
        return 0
    else
        print_error "npm not found"
        return 1
    fi
}

# Provide installation instructions based on OS
provide_install_instructions() {
    local tool=$1

    echo -e "\n${YELLOW}Installation instructions for $tool:${NC}\n"

    case $tool in
        docker)
            case $OS in
                macos)
                    echo "  Download Docker Desktop for Mac:"
                    echo "  https://www.docker.com/products/docker-desktop"
                    echo ""
                    echo "  Or install via Homebrew:"
                    echo "  brew install --cask docker"
                    ;;
                linux)
                    echo "  Ubuntu/Debian:"
                    echo "  curl -fsSL https://get.docker.com -o get-docker.sh"
                    echo "  sudo sh get-docker.sh"
                    echo "  sudo usermod -aG docker \$USER"
                    echo ""
                    echo "  Fedora/RHEL:"
                    echo "  sudo dnf install docker-ce docker-ce-cli containerd.io"
                    ;;
                windows)
                    echo "  Download Docker Desktop for Windows:"
                    echo "  https://www.docker.com/products/docker-desktop"
                    ;;
            esac
            ;;
        python)
            case $OS in
                macos)
                    echo "  Install via Homebrew (recommended):"
                    echo "  brew install python@3.12"
                    echo ""
                    echo "  Or install uv (faster Python package manager):"
                    echo "  curl -LsSf https://astral.sh/uv/install.sh | sh"
                    ;;
                linux)
                    echo "  Ubuntu/Debian:"
                    echo "  sudo apt update"
                    echo "  sudo apt install python3.12 python3.12-venv python3-pip"
                    echo ""
                    echo "  Fedora/RHEL:"
                    echo "  sudo dnf install python3.12"
                    echo ""
                    echo "  Or install uv (faster Python package manager):"
                    echo "  curl -LsSf https://astral.sh/uv/install.sh | sh"
                    ;;
                windows)
                    echo "  Download Python from:"
                    echo "  https://www.python.org/downloads/"
                    ;;
            esac
            ;;
        node)
            case $OS in
                macos)
                    echo "  Install via Homebrew:"
                    echo "  brew install node"
                    echo ""
                    echo "  Or install via nvm:"
                    echo "  curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash"
                    echo "  nvm install 20"
                    ;;
                linux)
                    echo "  Ubuntu/Debian:"
                    echo "  curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -"
                    echo "  sudo apt-get install -y nodejs"
                    echo ""
                    echo "  Or install via nvm:"
                    echo "  curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash"
                    echo "  nvm install 20"
                    ;;
                windows)
                    echo "  Download Node.js from:"
                    echo "  https://nodejs.org/"
                    ;;
            esac
            ;;
    esac
    echo ""
}

# Show system information
show_system_info() {
    print_header "System Information"
    echo -e "${BLUE}Operating System:${NC} $OS_NAME"
    echo -e "${BLUE}Architecture:${NC}     $ARCH_NAME"
    echo -e "${BLUE}Shell:${NC}            $SHELL"
    echo ""
}

# Check all prerequisites
check_prerequisites() {
    print_header "Checking Prerequisites"

    local all_ok=true

    # Check Docker
    if ! check_docker; then
        provide_install_instructions "docker"
        all_ok=false
    fi

    # Check Python
    if ! check_python; then
        provide_install_instructions "python"
        all_ok=false
    fi

    # Check Node.js
    if ! check_node; then
        provide_install_instructions "node"
        all_ok=false
    fi

    # Check npm
    if ! check_npm; then
        echo -e "${YELLOW}npm should come with Node.js. Please reinstall Node.js.${NC}"
        all_ok=false
    fi

    if [ "$all_ok" = false ]; then
        echo ""
        print_error "Missing required dependencies. Please install them and run this script again."
        exit 1
    fi

    echo ""
    print_success "All prerequisites are installed!"
}

# Setup Python environment
setup_python_env() {
    print_header "Setting Up Python Environment"

    cd "$(dirname "$0")"

    if [ -d ".venv" ]; then
        print_info "Virtual environment already exists"
    else
        print_info "Creating virtual environment..."
        if [ "$PYTHON_CMD" = "uv" ]; then
            uv venv
        else
            python3 -m venv .venv
        fi
        print_success "Virtual environment created"
    fi

    print_info "Installing Python dependencies..."
    if [ "$PYTHON_CMD" = "uv" ]; then
        uv pip install -r requirements.txt
    else
        .venv/bin/pip install --quiet --upgrade pip
        .venv/bin/pip install --quiet -r requirements.txt
    fi

    # Mark requirements as installed
    touch .venv/.requirements_installed

    print_success "Python dependencies installed"
}

# Setup frontend environment
setup_frontend_env() {
    print_header "Setting Up Frontend Environment"

    cd frontend

    if [ -d "node_modules" ]; then
        print_info "Node modules already installed"
    else
        print_info "Installing frontend dependencies (this may take a minute)..."
        npm install --silent
        print_success "Frontend dependencies installed"
    fi

    cd ..
}

# Setup environment file
setup_env_file() {
    print_header "Setting Up Environment Configuration"

    if [ -f ".env" ]; then
        print_warning ".env file already exists - skipping"
    else
        if [ -f ".env.example" ]; then
            cp .env.example .env
            print_success ".env file created from .env.example"
            echo -e "  ${YELLOW}Review and update .env with your configuration${NC}"
        else
            print_error ".env.example not found"
        fi
    fi
}

# Setup Docker services
setup_docker_services() {
    print_header "Setting Up Docker Services"

    # Check if docker-compose.yml exists
    if [ ! -f "docker-compose.yml" ]; then
        print_warning "docker-compose.yml not found"
        print_info "You'll need to manually set up Ollama and databases"
        return
    fi

    print_info "Starting Ollama container..."
    docker-compose up -d ollama 2>/dev/null || {
        print_warning "Could not start Ollama via docker-compose"
        print_info "You can start it manually later with: docker-compose up -d ollama"
        return
    }

    print_info "Waiting for Ollama to be ready..."
    sleep 5

    if docker ps | grep -q nlsql-ollama; then
        print_success "Ollama container is running"

        print_info "Pulling llama3.2 model (this may take several minutes)..."
        echo -e "  ${YELLOW}This will download ~2GB of data${NC}"

        if docker exec -it nlsql-ollama ollama pull llama3.2; then
            print_success "llama3.2 model downloaded successfully"
            echo ""
            docker exec nlsql-ollama ollama list
        else
            print_warning "Failed to pull llama3.2 model"
            print_info "You can pull it later with: docker exec -it nlsql-ollama ollama pull llama3.2"
        fi
    else
        print_error "Failed to start Ollama container"
        print_info "You can start it manually later with: docker-compose up -d ollama"
    fi
}

# Create necessary directories
setup_directories() {
    print_header "Creating Directories"

    mkdir -p logs
    mkdir -p ~/.nlsql

    # Secure the database config directory
    chmod 700 ~/.nlsql 2>/dev/null || true

    print_success "Directories created"
}

# Show completion message
show_completion() {
    print_header "Installation Complete!"

    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}  Setup Successful! 🎉${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    echo -e "${BLUE}System:${NC}        $OS_NAME ($ARCH_NAME)"
    echo -e "${BLUE}Python:${NC}        $PYTHON_VERSION"
    echo -e "${BLUE}Node.js:${NC}       $(node --version | cut -d 'v' -f2)"
    echo -e "${BLUE}Docker:${NC}        $(docker --version | cut -d ' ' -f3 | tr -d ',')"
    echo ""
    echo -e "${CYAN}Next Steps:${NC}"
    echo ""
    echo -e "  1. Review configuration file:"
    echo -e "     ${YELLOW}nano .env${NC}"
    echo ""
    echo -e "  2. Start the development environment:"
    echo -e "     ${YELLOW}./run.sh dev${NC}"
    echo ""
    echo -e "  3. Open your browser:"
    echo -e "     ${YELLOW}http://localhost:3000${NC}"
    echo ""
    echo -e "${CYAN}Useful Commands:${NC}"
    echo ""
    echo -e "  ${GREEN}./run.sh dev${NC}          - Start development mode"
    echo -e "  ${GREEN}./run.sh dev --verbose${NC} - Start with live logs"
    echo -e "  ${GREEN}./run.sh stop${NC}         - Stop all services"
    echo -e "  ${GREEN}./run.sh clean${NC}        - Clean up containers and logs"
    echo -e "  ${GREEN}./run.sh help${NC}         - Show all commands"
    echo ""
    echo -e "${YELLOW}Documentation:${NC}"
    echo -e "  - README.md       - Project overview and usage"
    echo -e "  - DEPLOYMENT.md   - Production deployment guide"
    echo ""
}

# Main installation flow
main() {
    clear
    echo -e "${CYAN}"
    cat << "EOF"
╔═══════════════════════════════════════════════╗
║   Natural Language SQL Engine - Installer    ║
║                                               ║
║   Automated system detection and setup       ║
╚═══════════════════════════════════════════════╝
EOF
    echo -e "${NC}"

    # Detect system
    detect_os
    detect_arch
    show_system_info

    # Check prerequisites
    check_prerequisites

    # Ask for confirmation
    echo -e "${YELLOW}This script will:${NC}"
    echo "  • Create Python virtual environment"
    echo "  • Install Python dependencies"
    echo "  • Install Node.js dependencies"
    echo "  • Set up Docker Ollama with llama3.2 model"
    echo "  • Create .env configuration file"
    echo "  • Create necessary directories"
    echo ""
    read -p "Continue with installation? (Y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Nn]$ ]]; then
        print_info "Installation cancelled"
        exit 0
    fi

    # Run setup steps
    setup_directories
    setup_python_env
    setup_frontend_env
    setup_env_file
    setup_docker_services

    # Show completion
    show_completion
}

# Run main function
main
