#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
VENV_DIR="$REPO_ROOT/.venv"
VENV_PYTHON="$VENV_DIR/bin/python"

find_python() {
  local candidate
  for candidate in python3.13 python3.12 python3.11 python3.10 python3 python; do
    if command -v "$candidate" >/dev/null 2>&1 &&
       "$candidate" -c 'import sys; raise SystemExit(sys.version_info[:2] not in {(3, 10), (3, 11), (3, 12), (3, 13)})' >/dev/null 2>&1; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done
  return 1
}

if ! PYTHON_BIN="$(find_python)"; then
  echo "Python 3.10-3.13 was not found."
  echo "Install a supported Python version and run this script again."
  exit 1
fi

if ! command -v node >/dev/null 2>&1 || ! command -v npm >/dev/null 2>&1; then
  echo "Node.js and npm were not found."
  echo "Install Node.js 20.19+, 22.13+, or 24+, then run this script again."
  exit 1
fi

if ! node -e 'const [major, minor] = process.versions.node.split(".").map(Number); process.exit((major === 20 && minor >= 19) || (major === 22 && minor >= 13) || major >= 24 ? 0 : 1)' >/dev/null 2>&1; then
  echo "Node.js 20.19+, 22.13+, or 24+ is required. Found: $(node --version)"
  exit 1
fi

cd "$REPO_ROOT"

if [[ ! -d "$VENV_DIR" ]]; then
  echo "Creating Python virtual environment with $PYTHON_BIN..."
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

if ! "$VENV_PYTHON" -c 'import sys; raise SystemExit(sys.version_info[:2] not in {(3, 10), (3, 11), (3, 12), (3, 13)})' >/dev/null 2>&1; then
  echo "The existing .venv does not use Python 3.10-3.13."
  echo "Remove only $VENV_DIR, then run this script again."
  exit 1
fi

echo "Installing Python dependencies..."
"$VENV_PYTHON" -m pip install -e .

echo "Installing frontend dependencies and building the web interface..."
(
  cd "$REPO_ROOT/frontend"
  npm ci
  npm run build
)

mkdir -p \
  "$REPO_ROOT/data/chats/sessions" \
  "$REPO_ROOT/data/knowledge" \
  "$REPO_ROOT/data/credentials"

echo
echo "Setup complete."
echo "Start the application with: ./scripts/run.sh"
