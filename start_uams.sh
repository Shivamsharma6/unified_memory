#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PATH="/opt/homebrew/bin:/opt/homebrew/sbin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"

# Wait for Docker daemon (up to 5 minutes to account for cold boot VM startup)
MAX_WAIT=300
waited=0
until docker info >/dev/null 2>&1 || [ "$waited" -ge "$MAX_WAIT" ]; do
  echo "Waiting for Docker daemon to become available... ($waited/$MAX_WAIT s)"
  sleep 5
  waited=$((waited + 5))
done

if ! docker info >/dev/null 2>&1; then
  echo "Error: Docker daemon not available after ${MAX_WAIT} seconds." >&2
  exit 1
fi

exec "$ROOT_DIR/uams" start
