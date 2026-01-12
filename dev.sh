#!/bin/bash

# Kill all child processes when this script exits
trap 'kill $(jobs -p)' EXIT

echo "🚀 Starting Local Development Environment..."

# 1. Start Backend (Port 8000)
echo "🐍 Starting Backend (FastAPI)..."
# Check if virtualenv exists, if not install
if [ ! -d ".venv" ] && [ ! -d "$(poetry env info -p)" ]; then
    echo "Installing backend dependencies..."
    poetry install
fi

# Run backend in background
poetry run uvicorn financia.web_api.main:app --reload --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

# Wait for backend to be vaguely ready
sleep 2

# 2. Start Frontend (Port 5173)
echo "⚛️  Starting Frontend (Vite)..."
cd financia/ui

# Check if node_modules exists
if [ ! -d "node_modules" ]; then
    echo "Installing frontend dependencies..."
    npm install
fi

# Set API URL to localhost:8000 explicitly
export VITE_API_URL="http://localhost:8000"
export VITE_APP_PIN="1234"

# Run frontend
npm run dev -- --host

# Wait for both
wait
