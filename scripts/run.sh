#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
VENV_PATH="${VENV_PATH:-$REPO_ROOT/.venv}"
VENV_PYTHON="$VENV_PATH/bin/python"
FRONTEND_INDEX="$REPO_ROOT/frontend/dist/index.html"

HOST="${1:-127.0.0.1}"
PORT="${2:-8000}"

if [[ ! -x "$VENV_PYTHON" ]]; then
  echo "Python environment not found: $VENV_PATH"
  echo "Run ./scripts/setup.sh first or set VENV_PATH to an existing virtual environment."
  exit 1
fi

if [[ ! -f "$FRONTEND_INDEX" ]]; then
  echo "Frontend build not found: $FRONTEND_INDEX"
  echo "Run ./scripts/setup.sh first."
  exit 1
fi

cd "$REPO_ROOT"

echo "Math IM Book is starting at http://$HOST:$PORT"
echo "Press Ctrl+C to stop."
exec "$VENV_PYTHON" -m uvicorn \
  math_im_book.api.app:create_app \
  --factory \
  --host "$HOST" \
  --port "$PORT"
