#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

echo "Starting Local-First Qdrant (Apple Silicon Optimized)..."
# Check if docker is running
if ! docker info > /dev/null 2>&1; then
  echo "Docker is not running. Please start Docker Desktop or OrbStack."
  exit 1
fi

if docker compose version >/dev/null 2>&1; then
  COMPOSE=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE=(docker-compose)
else
  echo "Docker Compose is required. Install Docker Desktop, OrbStack, or docker-compose."
  exit 1
fi

"${COMPOSE[@]}" up -d qdrant

echo "Waiting for Qdrant to become healthy..."
for _ in {1..30}; do
  if curl -fsS "http://${QDRANT_HOST:-127.0.0.1}:${QDRANT_HTTP_PORT:-6333}/" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

# Native Health Check
"${PYTHON:-python}" scripts/health_check.py
