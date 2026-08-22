# Multi-stage Dockerfile for UAMS (Unified Agent Memory System)
FROM python:3.11-slim as builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY memory_watcher/requirements.txt /app/memory_watcher_requirements.txt
RUN pip install --no-cache-dir --user -r /app/memory_watcher_requirements.txt

FROM python:3.11-slim

WORKDIR /app

COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/memory_watcher:/app/uams_sdk:$PYTHONPATH
ENV UAMS_VAULT_PATH=/app/vault

# Copy code
COPY memory_watcher /app/memory_watcher
COPY uams_sdk /app/uams_sdk
COPY AGENTS.md /app/vault/AGENTS.md

# Install SDK in editable mode
RUN pip install --no-cache-dir -e /app/uams_sdk

RUN mkdir -p /app/vault/Daily /app/vault/Concepts /app/vault/Tasks /app/vault/Identity /app/vault/AI/Summaries /app/vault/Archive /app/vault/.uams/backups

EXPOSE 8000

WORKDIR /app/memory_watcher
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
