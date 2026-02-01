# Deployment Guide

This guide covers deploying the Natural Language SQL Engine to production environments.

## Table of Contents

- [Quick Deployment with Docker](#quick-deployment-with-docker)
- [Environment Configuration](#environment-configuration)
- [Production Best Practices](#production-best-practices)
- [Free Tier Deployment Options](#free-tier-deployment-options)
- [Security Considerations](#security-considerations)
- [Troubleshooting](#troubleshooting)

---

## Quick Deployment with Docker

### Prerequisites

- Docker and Docker Compose installed
- 4GB+ RAM available
- Ports 3000, 8000, 11434, 5432 available

### Step 1: Clone and Configure

```bash
git clone https://github.com/jmanoj0905/natural-language-sql.git
cd natural-language-sql

# Copy environment template
cp .env.example .env

# Edit configuration (see Environment Configuration section)
nano .env
```

### Step 2: Deploy

```bash
# Start all services
./run.sh

# Verify deployment
curl http://localhost:8000/api/v1/health
```

The application will be available at:
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Documentation: http://localhost:8000/docs

### Step 3: Connect Your Database

1. Open http://localhost:3000
2. Go to the "Connectors" tab
3. Add your database connection (PostgreSQL, MySQL, SQLite)
4. Test the connection
5. Start querying in natural language!

---

## Environment Configuration

### Required Variables

```bash
# API Server Configuration
HOST=0.0.0.0                    # Bind to all interfaces
PORT=8000                       # Backend API port
ENVIRONMENT=production          # Set to production for deployment

# Ollama AI Configuration
OLLAMA_BASE_URL=http://localhost:11434   # Ollama service URL
OLLAMA_MODEL=llama3.2                    # AI model to use
OLLAMA_TEMPERATURE=0.1                   # Lower = more deterministic

# Security Limits
MAX_QUERY_RESULTS=1000          # Maximum rows returned per query
DEFAULT_QUERY_LIMIT=100         # Default LIMIT for SELECT queries
QUERY_TIMEOUT_SECONDS=30        # Query execution timeout

# Performance
ENABLE_SCHEMA_CACHE=true        # Cache database schemas
SCHEMA_CACHE_TTL_SECONDS=3600   # Cache expiry (1 hour)

# CORS (IMPORTANT: Update for production)
CORS_ORIGINS=["http://localhost:3000"]  # Frontend URL
CORS_ALLOW_CREDENTIALS=true
```

### Production Configuration

For production deployments, update:

```bash
DEBUG=false
ENVIRONMENT=production
LOG_LEVEL=INFO
CORS_ORIGINS=["https://your-frontend-domain.com"]
```

---

## Production Best Practices

### 1. Security

**HTTPS is Required**
- Database credentials are transmitted in API requests
- Always deploy behind HTTPS (use Nginx, Caddy, or cloud provider SSL)

**Credential Protection**
- Database credentials are stored in `~/.nlsql/databases.json` (plaintext)
- Secure this file with proper permissions: `chmod 600 ~/.nlsql/databases.json`
- Consider encrypting the file system or using secrets management

**CORS Configuration**
- Update `CORS_ORIGINS` to your production frontend domain
- Never use `["*"]` in production

**Rate Limiting**
- Deploy behind a reverse proxy with rate limiting (Nginx, Cloudflare)
- Prevent abuse of AI query generation endpoint

### 2. Resource Management

**Ollama Service**
```bash
# Ollama requires significant resources
# Minimum: 4GB RAM
# Recommended: 8GB RAM for llama3.2
```

**Database Connection Pooling**
```bash
DB_POOL_SIZE=5          # Connection pool size per database
DB_MAX_OVERFLOW=10      # Additional connections when pool exhausted
```

### 3. Monitoring

**Health Checks**
- Backend health: `GET /api/v1/health`
- Database health: `GET /api/v1/health/database`

**Logging**
```bash
# Logs are stored in ./logs directory
tail -f logs/nlsql.log

# Set appropriate log level
LOG_LEVEL=INFO          # Production
LOG_LEVEL=DEBUG         # Development
```

### 4. Backup

**Database Credentials**
```bash
# Backup your database connections
cp ~/.nlsql/databases.json ~/.nlsql/databases.json.backup

# Consider version controlling (encrypted) or using secrets management
```

---

## Free Tier Deployment Options

### Option 1: Railway (Backend + Frontend)

**Backend Deployment:**
1. Create new project on [Railway.app](https://railway.app)
2. Add PostgreSQL service (optional - for demo data)
3. Deploy backend:
   ```bash
   # Railway auto-detects Dockerfile
   railway up
   ```
4. Set environment variables in Railway dashboard
5. Note your backend URL: `https://your-app.railway.app`

**Frontend Deployment:**
1. Build frontend:
   ```bash
   cd frontend
   npm run build
   ```
2. Deploy `dist/` folder to Railway static site
3. Update `VITE_API_URL` to Railway backend URL

**Cost:** Free tier includes 500 hours/month

### Option 2: Render (Backend) + Vercel (Frontend)

**Backend on Render:**
1. Create account at [Render.com](https://render.com)
2. New Web Service → Connect Git repository
3. Configure:
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
4. Add environment variables
5. Deploy

**Frontend on Vercel:**
1. Create account at [Vercel.com](https://vercel.com)
2. Import Git repository
3. Configure:
   - Framework: Vite
   - Root Directory: `frontend/`
   - Build Command: `npm run build`
   - Output Directory: `dist`
4. Add environment variable:
   ```
   VITE_API_URL=https://your-app.onrender.com
   ```
5. Deploy

**Cost:** Both have generous free tiers

### Option 3: Fly.io (Full Stack)

1. Install Fly CLI: `curl -L https://fly.io/install.sh | sh`
2. Create `fly.toml`:
   ```toml
   app = "nlsql-engine"

   [build]
   dockerfile = "Dockerfile"

   [[services]]
   http_checks = []
   internal_port = 8000
   protocol = "tcp"

   [[services.ports]]
   handlers = ["http"]
   port = 80

   [[services.ports]]
   handlers = ["tls", "http"]
   port = 443
   ```
3. Deploy:
   ```bash
   fly deploy
   fly secrets set OLLAMA_MODEL=llama3.2
   ```

**Cost:** Free tier includes 3 shared-cpu VMs

### Important Note on Ollama

**Ollama requires significant resources:**
- Most free tiers don't provide enough RAM (8GB+) for Ollama
- Consider these alternatives:
  1. **Self-host Ollama** on a separate server/VPS
  2. **Use cloud AI APIs** (OpenAI, Anthropic) - requires code modification
  3. **Deploy on paid tier** with sufficient resources

---

## Security Considerations

### Critical Security Warnings

1. **HTTPS Required**
   - Database passwords are transmitted in API requests
   - Always use HTTPS in production
   - Use SSL certificates (Let's Encrypt, Cloudflare, etc.)

2. **Credential Storage**
   - Database credentials stored in `~/.nlsql/databases.json` (plaintext)
   - Protect this file: `chmod 600 ~/.nlsql/databases.json`
   - Consider encryption at rest or secrets management (Vault, AWS Secrets Manager)

3. **CORS Configuration**
   - Update `CORS_ORIGINS` environment variable for production
   - Never use `["*"]` - specify exact frontend domains
   - Example: `CORS_ORIGINS=["https://myapp.com","https://www.myapp.com"]`

4. **Query Permissions**
   - Use database accounts with least privilege
   - For read-only use cases, use read-only database users
   - Avoid using database admin accounts

5. **Write Mode Safety**
   - Write mode allows UPDATE, DELETE, INSERT queries
   - Enable only when necessary
   - Always review generated SQL before execution in write mode
   - Consider disabling write mode in production frontends

6. **SQL Injection Prevention**
   - Backend validates all SQL queries
   - Uses parameterized queries where possible
   - Never bypass query validator in production

### Recommended Security Checklist

- [ ] Deploy behind HTTPS
- [ ] Update CORS_ORIGINS for production domain
- [ ] Secure `~/.nlsql/databases.json` with proper permissions
- [ ] Use read-only database users when possible
- [ ] Enable rate limiting (reverse proxy or API gateway)
- [ ] Set up monitoring and alerting
- [ ] Regular backup of database connection configs
- [ ] Review logs for suspicious queries
- [ ] Keep dependencies updated (`pip-audit`, `npm audit`)

---

## Troubleshooting

### Common Issues

#### 1. Ollama Connection Failed

**Symptom:** "Failed to connect to Ollama" or "Connection refused at http://localhost:11434"

**Solutions:**
```bash
# Check if Ollama is running
docker ps | grep ollama

# Start Ollama
docker run -d -v ollama:/root/.ollama -p 11434:11434 --name nlsql-ollama ollama/ollama

# Pull model
docker exec -it nlsql-ollama ollama pull llama3.2

# Verify Ollama is responding
curl http://localhost:11434/api/tags
```

#### 2. Database Connection Failed

**Symptom:** "Database connection failed" or "Could not connect to database"

**Solutions:**
```bash
# Check database is running
docker ps | grep postgres

# Verify credentials in ~/.nlsql/databases.json
cat ~/.nlsql/databases.json

# Test connection manually
psql -h localhost -p 5432 -U myuser -d mydatabase

# Check backend logs
tail -f logs/nlsql.log
```

#### 3. Frontend Can't Reach Backend

**Symptom:** "Network Error" or "Failed to fetch" in browser console

**Solutions:**
```bash
# Verify backend is running
curl http://localhost:8000/api/v1/health

# Check CORS configuration in .env
# CORS_ORIGINS should include frontend URL

# For production, update frontend API URL:
# In frontend/.env or build config
VITE_API_URL=https://your-backend-domain.com
```

#### 4. Out of Memory / Ollama Crashes

**Symptom:** Ollama service exits or queries timeout

**Solutions:**
```bash
# Check Docker memory limits
docker stats nlsql-ollama

# Increase Docker Desktop memory (Settings → Resources → Memory)
# Recommended: 8GB for llama3.2

# Or switch to smaller model
docker exec -it nlsql-ollama ollama pull phi
# Update .env: OLLAMA_MODEL=phi
```

#### 5. Slow Query Generation

**Symptom:** Queries take 30+ seconds to generate

**Solutions:**
```bash
# Check Ollama performance
docker stats nlsql-ollama

# Reduce temperature for faster responses
OLLAMA_TEMPERATURE=0.1

# Use smaller/faster model
OLLAMA_MODEL=phi    # Faster but less accurate

# Disable schema caching if using many databases
ENABLE_SCHEMA_CACHE=false
```

#### 6. Permission Denied on databases.json

**Symptom:** "Permission denied: ~/.nlsql/databases.json"

**Solutions:**
```bash
# Fix permissions
chmod 600 ~/.nlsql/databases.json

# If directory doesn't exist
mkdir -p ~/.nlsql
chmod 700 ~/.nlsql
```

### Getting Help

If you encounter issues not covered here:

1. **Check logs:**
   ```bash
   ./run.sh logs
   ```

2. **Check backend logs:**
   ```bash
   tail -f logs/nlsql.log
   ```

3. **Check frontend console:**
   - Open browser DevTools (F12)
   - Check Console and Network tabs

4. **File an issue:**
   - GitHub Issues: https://github.com/jmanoj0905/natural-language-sql/issues
   - Include: error message, logs, environment (OS, Docker version, etc.)

---

## Performance Optimization

### 1. Schema Caching

Enable schema caching to reduce database queries:
```bash
ENABLE_SCHEMA_CACHE=true
SCHEMA_CACHE_TTL_SECONDS=3600  # 1 hour
```

### 2. Connection Pooling

Optimize database connections:
```bash
DB_POOL_SIZE=5
DB_MAX_OVERFLOW=10
```

### 3. Query Limits

Prevent large result sets:
```bash
MAX_QUERY_RESULTS=1000
DEFAULT_QUERY_LIMIT=100
```

### 4. Ollama Performance

For faster AI responses:
- Use GPU-enabled instances if available
- Reduce `OLLAMA_TEMPERATURE` (0.1 = faster, more deterministic)
- Consider smaller models (phi, mistral) for faster responses

---

## Updating the Application

```bash
# Pull latest changes
git pull origin main

# Rebuild Docker images
docker-compose build

# Restart services
./run.sh stop
./run.sh

# Update frontend dependencies
cd frontend && npm install && cd ..

# Update backend dependencies
pip install -r requirements.txt --upgrade
```

---

## Support

- **Documentation:** [README.md](README.md)
- **Issues:** https://github.com/jmanoj0905/natural-language-sql/issues
- **Author:** [Manoj J](https://jmanoj.pages.dev)
