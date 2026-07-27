#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export TRACE_LOCAL_URL=http://localhost:6016/v1

# activate the local venv if present
if [[ -f "$SCRIPT_DIR/../.venv/bin/activate" ]]; then
    # shellcheck disable=SC1091
    source "$SCRIPT_DIR/../.venv/bin/activate"
fi

export FASTAPI_ENV=development
export PYTHONPATH="$SCRIPT_DIR/..${PYTHONPATH:+:$PYTHONPATH}"

# Function to kill background processes on exit
cleanup() {
    echo "Stopping servers..."
    kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
}
trap cleanup EXIT

echo "Starting backend on port 8016..."
"$SCRIPT_DIR/../.venv/bin/uvicorn" math_im_book.api.app:create_app --reload --host 0.0.0.0 --port 8016 &
BACKEND_PID=$!

echo "Starting frontend (Vite)..."
(cd "$SCRIPT_DIR/../frontend" && npm run dev -- --port 8017) &
FRONTEND_PID=$!

echo "Both servers are running."
echo "- Backend: http://localhost:8016"
echo "- Frontend: http://localhost:8017"
wait
