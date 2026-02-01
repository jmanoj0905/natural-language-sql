# Natural Language to SQL Query Engine

> Transform natural language questions into SQL queries using local AI (Ollama llama3.2)

[![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green.svg)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18+-blue.svg)](https://react.dev)
[![License](https://img.shields.io/badge/License-GPL--3.0-yellow.svg)](LICENSE)

## Project Overview

A production-ready Natural Language to SQL Query Engine that allows users to query databases conversationally without knowing SQL. Built with FastAPI, React, and Docker Ollama for completely local, private AI-powered SQL generation.

### Key Features

- **Local AI** - Uses Docker Ollama (llama3.2) - completely free, no API keys needed
- **Multi-Database Support** - PostgreSQL and MySQL with persistent connections
- **Security** - SQL injection prevention, query validation, configurable write mode
- **Smart Context** - Includes table schema AND sample data for accurate query generation
- **Async Architecture** - Connection pooling, transaction support, auto-commit
- **Modern UI** - React + Vite frontend with query history and database management
- **Docker Ready** - Complete Docker Compose setup for all services

## Architecture

```
User Question → Frontend (React) → Backend (FastAPI) → Schema Inspector → Ollama AI → SQL Generator → Query Validator → Query Executor → PostgreSQL/MySQL
```

## Quick Start

### First Time Setup

Run the installation script to automatically detect your system and install dependencies:

```bash
./install.sh
```

This script will:
1. Detect your OS (macOS/Linux/Windows) and architecture (x86_64/ARM64)
2. Check for required tools (Docker, Python 3.12+, Node.js 18+)
3. Set up Python virtual environment
4. Install all dependencies (Python + Node.js)
5. Set up Docker Ollama with llama3.2 model
6. Create .env configuration file

### Start the Application

After installation, start everything with one command:

```bash
./run.sh dev
```

This will:
1. Start Docker Ollama with llama3.2 (if not already running)
2. Start PostgreSQL database
3. Start backend (FastAPI)
4. Start frontend (React)

After 30 seconds, open http://localhost:3000

The application is now running with:
- Frontend at http://localhost:3000
- Backend API at http://localhost:8000
- API Docs at http://localhost:8000/docs
- PostgreSQL on localhost:5432
- Ollama AI on localhost:11434

### Additional Commands

**Installation (first time only):**
```bash
./install.sh          # Auto-detect system and install dependencies
```

**Running the application:**
```bash
./run.sh dev          # Start development environment
./run.sh dev --verbose # Start with live logs
./run.sh prod         # Start production mode (backend only)
./run.sh stop         # Stop all services
./run.sh clean        # Clean up containers, logs, cache
./run.sh logs         # View application logs
./run.sh help         # Show all commands
```

## What's Included

- **Backend (FastAPI)** - REST API with async PostgreSQL/MySQL support
- **Frontend (React + Vite)** - Modern UI with query builder and history
- **AI Service (Docker Ollama)** - Local llama3.2 model for SQL generation
- **Database (PostgreSQL)** - Test database with sample data
- **Docker Compose** - Complete orchestration for all services

## Configuration

### Environment Variables (.env)

```env
# AI Configuration
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2

# Database Connection
DB_POOL_SIZE=5
DB_MAX_OVERFLOW=10

# Security Settings
MAX_QUERY_RESULTS=1000
DEFAULT_QUERY_LIMIT=100
QUERY_TIMEOUT_SECONDS=30
```

### Switching AI Models

```bash
# Pull a different model
docker exec -it nlsql-ollama ollama pull codellama

# Update .env
OLLAMA_MODEL=codellama

# Restart app
./run.sh stop && ./run.sh
```

### Available Models

| Model | Size | Speed | Best For |
|-------|------|-------|----------|
| llama3.2 | 2GB | Fast | General SQL queries |
| codellama | 3.8GB | Medium | Complex queries |
| llama3.1 | 4.7GB | Slow | High accuracy |
| mistral | 4.1GB | Medium | Balanced performance |

## Usage Examples

### Via UI (http://localhost:3000)

1. **Connect to Database**
   - Go to "Databases" tab
   - Click "Add Database"
   - Enter connection details (saved across restarts)

2. **Ask Natural Language Questions**
   ```
   "show all users"
   "find users created in the last 7 days"
   "delete user alice_brown"  (requires write mode)
   "update user john_doe set email to new@email.com"
   ```

3. **View Results**
   - See generated SQL
   - View query explanation
   - Check execution results
   - Browse query history

### Via API

```bash
# Natural language query
curl -X POST http://localhost:8000/api/v1/query/natural \
  -H "Content-Type: application/json" \
  -d '{
    "question": "show all users",
    "options": {
      "execute": true,
      "read_only": false
    }
  }'

# Direct SQL execution
curl -X POST http://localhost:8000/api/v1/query/sql \
  -H "Content-Type: application/json" \
  -d '{
    "sql": "SELECT * FROM users LIMIT 10"
  }'
```

## Security Features

### Write Operations
- **Read-Only Mode** - Default safe mode, only SELECT queries
- **Write Mode** - Enable DELETE, UPDATE, INSERT operations
- **Auto-Commit** - All write operations commit automatically
- **Error Handling** - Automatic transaction rollback on query errors

### SQL Protection
- **Injection Prevention** - Blocks dangerous patterns
- **DDL Blocking** - No DROP, CREATE, ALTER operations
- **Query Validation** - Syntax and safety checks
- **Timeout Protection** - Prevents long-running queries

### Security Warnings

**Important Security Considerations:**

- **HTTPS Required in Production** - Database credentials are transmitted in API requests. Always use HTTPS when deploying to production to protect sensitive data.

- **Credential Storage** - Database connection credentials are stored in plaintext in `~/.nlsql/databases.json`. Protect this file:
  ```bash
  chmod 600 ~/.nlsql/databases.json
  ```
  Consider using encrypted file systems or secrets management in production.

- **CORS Configuration** - Update `CORS_ORIGINS` environment variable for production domains. Never use `["*"]` in production - specify exact frontend URLs.

- **Database Permissions** - Use database accounts with minimal required privileges. For read-only use cases, use read-only database users.

- **Write Mode Caution** - Write mode enables UPDATE, DELETE, and INSERT operations. Always review generated SQL before execution in write mode. Changes are permanent once executed.

See [DEPLOYMENT.md](DEPLOYMENT.md) for comprehensive security best practices.

## Sample Data Context

The AI sees actual row data from your tables, not just schema:

**Without Sample Data:**
```
Question: "delete alice brown"
Generated: DELETE FROM users WHERE username = 'alice' AND role = 'brown' (incorrect)
```

**With Sample Data (Current):**
```
Question: "delete alice brown"
AI sees: username='alice_brown' in sample data
Generated: DELETE FROM users WHERE username = 'alice_brown' (correct)
```

Sample data includes 3 rows per table by default, configurable in settings.

## Database Persistence

Connected databases are automatically saved to `~/.nlsql/databases.json` and restored on restart.

```bash
# Check saved databases
cat ~/.nlsql/databases.json

# List via API
curl http://localhost:8000/api/v1/databases
```

## Docker Services

### View Running Services
```bash
docker ps
# nlsql-ollama    - AI service (llama3.2)
# nlsql-postgres  - PostgreSQL database
```

### Manage Ollama
```bash
# View logs
docker logs nlsql-ollama

# List models
docker exec nlsql-ollama ollama list

# Pull new model
docker exec -it nlsql-ollama ollama pull llama3.1
```

### Manage PostgreSQL
```bash
# View logs
docker logs nlsql-postgres

# Connect to database
docker exec -it nlsql-postgres psql -U readonly_user -d testdb
```

## Project Structure

```
natural-lang-sql/
├── app/                          # Backend FastAPI application
│   ├── api/v1/endpoints/        # API endpoints
│   ├── core/                    # Core business logic
│   │   ├── ai/                  # Ollama AI integration
│   │   ├── database/            # Database connection & schema
│   │   ├── query/               # Query execution & validation
│   │   └── security/            # SQL sanitization
│   ├── models/                  # Pydantic models
│   └── main.py                  # Application entry point
├── frontend/                     # React + Vite frontend
│   ├── src/
│   │   ├── components/          # React components
│   │   ├── services/            # API services
│   │   └── App.tsx              # Main app component
│   └── package.json
├── docker-compose.yml           # Docker orchestration
├── run.sh                       # Unified management script
├── install.sh                       # Unified installation script
└── README.md                    # This file
```

## Deployment

See [DEPLOYMENT.md](DEPLOYMENT.md) for comprehensive deployment guides including:

- Free deployment using Vercel + Render + Supabase ($0/month)
- Oracle Cloud Always Free tier (forever free with full compute)
- Production configuration and best practices

### Quick Deploy Options

**Frontend (Vercel):**
```bash
# Connect GitHub repo to Vercel
# Auto-deploys on push to main branch
```

**Backend (Render):**
```bash
# Use render.yaml for one-click deploy
# Connect GitHub repo to Render
```

## Development

### Manual Setup (Without Docker)

```bash
# Backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload

# Frontend
cd frontend
npm install
npm run dev
```

### Health Checks

```bash
# Test backend health
curl http://localhost:8000/api/v1/health

# Test database connection
curl http://localhost:8000/api/v1/health/database

# Test Ollama
curl http://localhost:11434/api/tags
```

## Troubleshooting

### Ollama Not Responding
```bash
# Check if running
docker ps | grep ollama

# View logs
docker logs nlsql-ollama

# Restart
docker-compose restart ollama
```

### Database Connection Failed
```bash
# Check PostgreSQL
docker logs nlsql-postgres

# Test connection
docker exec nlsql-postgres pg_isready -U readonly_user -d testdb
```

### Port Already in Use
```bash
# Kill process on port 8000
lsof -ti:8000 | xargs kill -9

# Kill process on port 3000
lsof -ti:3000 | xargs kill -9
```

### Clean Start
```bash
./run.sh clean   # Remove all containers and cache
./run.sh         # Fresh start
```

## Contributing

Contributions are welcome. Please:
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

This project is licensed under the GPL-3.0 License - see the LICENSE file for details.

## Acknowledgments

- **Ollama** - Local AI model serving
- **FastAPI** - Modern Python web framework
- **React** - Frontend framework
- **Docker** - Containerization platform

## Related Documentation

- [FastAPI Documentation](https://fastapi.tiangolo.com)
- [Ollama Documentation](https://github.com/ollama/ollama)
- [React Documentation](https://react.dev)
- [Docker Compose Documentation](https://docs.docker.com/compose/)
