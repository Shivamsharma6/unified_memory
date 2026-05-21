#!/bin/bash
cd "$(dirname "$0")/.."

echo "Starting Local-First Qdrant (Apple Silicon Optimized)..."
# Check if docker is running
if ! docker info > /dev/null 2>&1; then
  echo "Docker is not running. Please start Docker Desktop or OrbStack."
  exit 1
fi

docker-compose up -d

echo "Waiting for Qdrant to become healthy..."
sleep 2

# Native Health Check
python scripts/health_check.py
