FROM python:3.12-slim

# Install Ollama
RUN curl -fsSL https://ollama.com/install.sh | sh

WORKDIR /app

# Create user
RUN useradd -m -u 1000 user
USER user

# Copy requirements and install Python deps
COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir --upgrade -r requirements.txt

# Copy app code
COPY --chown=user app ./app

# Environment setup
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV PROMETHEUS_MULTIPROC_DIR=/tmp/prometheus_metrics
ENV OLLAMA_BASE_URL=http://localhost:11434
ENV OLLAMA_MODEL=mannix/defog-llama3-sqlcoder-8b

# Install curl for health checks
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Expose ports
EXPOSE 8000 11434

# Start script
CMD sh -c 'ollama serve & OLLAMA_PID=$!; \
    for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do \
        if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then break; fi; \
        sleep 2; \
    done; \
    ollama pull mannix/defog-llama3-sqlcoder-8b || true; \
    exec uvicorn app.main:app --host 0.0.0.0 --port 8000'
