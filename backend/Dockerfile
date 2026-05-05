# GlassNote Backend — Docker
# Build:  docker build -t glassnote-api .
# Run:    docker run -p 8000:8000 --env-file .env glassnote-api

FROM python:3.12-slim AS base

WORKDIR /app

# System deps (for asyncpg + bcrypt)
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

# Install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Non-root user
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8080

# Production command — reads $PORT injected by Cloud Run (default 8080)
# Shell form is required so the $PORT variable is expanded at runtime
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080} --workers 4
