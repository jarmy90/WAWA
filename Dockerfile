# WAWA Autonomous Business Lab — Docker image (iteración 025)
FROM python:3.12-slim

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl sqlite3 && \
    rm -rf /var/lib/apt/lists/*

# Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application code
COPY app/ app/
COPY frontend/ frontend/
COPY data/ data/ 2>/dev/null || true
COPY env.example .env.example

# Create data directories
RUN mkdir -p data/logs data/backups data/external_reviews data/freebuff_sessions data/manual_research

EXPOSE 8000

# Single process: Uvicorn with scheduler+worker in lifespan
CMD ["python3", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
