#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WATCHER_DIR="$ROOT_DIR/memory_watcher"
VENV_DIR="$WATCHER_DIR/.venv"
PYTHON_BIN="${PYTHON_BIN:-python3}"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "Python 3.11+ is required. Set PYTHON_BIN=/path/to/python if needed."
  exit 1
fi

"$PYTHON_BIN" - <<'PY'
import sys
if sys.version_info < (3, 11):
    raise SystemExit("Python 3.11+ is required.")
PY

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is required for local Qdrant. Install Docker Desktop or OrbStack, then rerun install.sh."
  exit 1
fi

echo "Creating Python environment..."
"$PYTHON_BIN" -m venv "$VENV_DIR"
"$VENV_DIR/bin/python" -m pip install --upgrade pip
"$VENV_DIR/bin/pip" install -r "$WATCHER_DIR/requirements.txt"
"$VENV_DIR/bin/pip" install -e "$ROOT_DIR/uams_sdk"

chmod +x "$ROOT_DIR/uams" "$ROOT_DIR/start_uams.sh" "$WATCHER_DIR/start.sh" "$WATCHER_DIR/scripts/start_qdrant.sh"

echo
echo "UAMS installed."
echo "Run: ./uams start"
echo "API docs: http://localhost:8000/docs"
