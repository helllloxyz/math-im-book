#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export TRACE_LOCAL_URL=http://localhost:6016/v1

# Prefer the shared agent environment, falling back to this project's existing
# local environment when the agent environment has not been created.
AGENT_VENV_DIR="$HOME/agent/.venv"
LOCAL_VENV_DIR="$SCRIPT_DIR/../.venv"
if [[ -x "$AGENT_VENV_DIR/bin/uvicorn" ]]; then
    VENV_DIR="$AGENT_VENV_DIR"
else
    VENV_DIR="$LOCAL_VENV_DIR"
fi

if [[ -f "$VENV_DIR/bin/activate" ]]; then
    # shellcheck disable=SC1091
    source "$VENV_DIR/bin/activate"
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
"$VENV_DIR/bin/uvicorn" math_im_book.api.app:create_app --reload --host 0.0.0.0 --port 8016 &
BACKEND_PID=$!

echo "Starting frontend (Vite)..."
(cd "$SCRIPT_DIR/../frontend" && npm run dev -- --port 8017) &
FRONTEND_PID=$!

echo "Both servers are running."
echo "- Backend: http://localhost:8016"
echo "- Frontend: http://localhost:8017"
wait
