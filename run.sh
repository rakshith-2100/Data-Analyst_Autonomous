#!/usr/bin/env bash
# run.sh — set up and launch the CSV Data Analyst (Linux / macOS).
#
# Creates a Python virtualenv, installs backend requirements + frontend packages,
# ensures data_analyst/.env exists, then starts the FastAPI backend and the Vite
# frontend together (backend is stopped automatically when you Ctrl+C).
#
#   chmod +x run.sh && ./run.sh
#
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
venv="$root/.venv"
backend="$root/data_analyst"
frontend="$root/app"

# 1) Python virtualenv
if [ ! -d "$venv" ]; then
    echo "==> Creating virtualenv (.venv)"
    python3 -m venv "$venv"
fi
py="$venv/bin/python"

# 2) Python requirements
echo "==> Installing Python requirements"
"$py" -m pip install --upgrade pip --quiet
"$py" -m pip install -r "$backend/requirements.txt" --quiet

# 3) .env (holds OPENAI_API_KEY; gitignored)
if [ ! -f "$backend/.env" ]; then
    cp "$backend/.env.example" "$backend/.env"
    echo "==> Created data_analyst/.env from .env.example"
    echo "    EDIT IT and set OPENAI_API_KEY before chatting."
fi

# 4) Frontend packages
if [ ! -d "$frontend/node_modules" ]; then
    echo "==> Installing frontend packages (npm install)"
    ( cd "$frontend" && npm install )
fi

# 5) Launch backend (background) + frontend (foreground); stop backend on exit
echo "==> Starting backend  -> http://127.0.0.1:8000  (/docs)"
echo "==> Starting frontend -> http://localhost:5173"
( cd "$backend" && "$py" -m uvicorn src.api:app --reload ) &
backend_pid=$!
trap 'kill "$backend_pid" 2>/dev/null || true' EXIT
( cd "$frontend" && npm run dev )
