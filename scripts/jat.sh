#!/usr/bin/env bash
set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND_PORT=8000
FRONTEND_PORT=3000

if ! command -v pnpm >/dev/null 2>&1; then
	echo "[ERROR] pnpm is required to start the dashboard. Install pnpm first."
	exit 1
fi

echo ""
echo "  ========================================"
echo "   JAT-AI - Starting..."
echo "  ========================================"
echo ""

if [ ! -f "$ROOT/.env" ]; then
	echo "[ERROR] .env file not found. Copy .env.example and fill in your keys."
	exit 1
fi

# Install Python deps if needed
if [ ! -f "$ROOT/.cache/deps_installed" ]; then
	echo "[SETUP] Installing Python dependencies..."
	pip install -e "$ROOT" >/dev/null 2>&1
	mkdir -p "$ROOT/.cache"
	echo "done" >"$ROOT/.cache/deps_installed"
fi

# Install frontend deps if needed
if [ ! -d "$ROOT/dashboard/node_modules" ]; then
	echo "[SETUP] Installing dashboard dependencies..."
	cd "$ROOT/dashboard" && pnpm install >/dev/null 2>&1
fi

cleanup() {
	echo ""
	echo "[SHUTDOWN] Stopping JAT-AI..."
	kill $BACKEND_PID 2>/dev/null || true
	kill $FRONTEND_PID 2>/dev/null || true
	exit 0
}
trap cleanup SIGINT SIGTERM

# Start backend
echo "[BACKEND] Starting FastAPI on port $BACKEND_PORT..."
cd "$ROOT"
python -m uvicorn api.server:app --port $BACKEND_PORT --reload --app-dir src &
BACKEND_PID=$!

# Wait for backend
echo "[BACKEND] Waiting for server..."
until curl -s "http://localhost:$BACKEND_PORT/api/setup" >/dev/null 2>&1; do
	sleep 1
done
echo "[BACKEND] Ready on http://localhost:$BACKEND_PORT"

# Start frontend
echo "[FRONTEND] Starting Vite on port $FRONTEND_PORT..."
cd "$ROOT/dashboard"
pnpm exec vite --port $FRONTEND_PORT &
FRONTEND_PID=$!

# Wait for frontend
until curl -s "http://localhost:$FRONTEND_PORT" >/dev/null 2>&1; do
	sleep 1
done
echo "[FRONTEND] Ready on http://localhost:$FRONTEND_PORT"

echo ""
echo "  ========================================"
echo "   JAT-AI running at http://localhost:$FRONTEND_PORT"
echo "   Press Ctrl+C to stop"
echo "  ========================================"
echo ""

# Open browser
if command -v xdg-open >/dev/null; then
	xdg-open "http://localhost:$FRONTEND_PORT"
elif command -v open >/dev/null; then
	open "http://localhost:$FRONTEND_PORT"
fi

wait
