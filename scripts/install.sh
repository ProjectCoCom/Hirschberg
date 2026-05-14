#!/usr/bin/env bash
set -e

if ! command -v pnpm >/dev/null 2>&1; then
	echo "[ERROR] pnpm is required for the dashboard. Install pnpm first, then rerun this installer."
	exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo ""
echo "  ========================================"
echo "   JAT-AI - Installing..."
echo "  ========================================"
echo ""

# Step 1: Python dependencies
echo "[1/3] Installing Python dependencies..."
pip install -e "$ROOT" || pip3 install -e "$ROOT" || {
	echo "[ERROR] Could not install dependencies. Make sure Python and pip are on PATH."
	exit 1
}
echo "[OK] Python dependencies installed."

# Step 2: Frontend dependencies
echo "[2/3] Checking frontend dependencies..."
if [ ! -d "$ROOT/dashboard/node_modules" ]; then
	echo "      Installing pnpm packages..."
	cd "$ROOT/dashboard" && pnpm install
	echo "[OK] Frontend dependencies installed."
else
	echo "[OK] Frontend already installed."
fi

# Step 3: Symlink jat command
echo "[3/3] Setting up jat command..."
LINK_PATH="/usr/local/bin/jat"
chmod +x "$SCRIPT_DIR/jat.sh"
if [ -w "/usr/local/bin" ]; then
	ln -sf "$SCRIPT_DIR/jat.sh" "$LINK_PATH"
else
	sudo ln -sf "$SCRIPT_DIR/jat.sh" "$LINK_PATH"
fi
echo "[OK] jat command linked."

echo ""
echo "  ========================================"
echo "   JAT-AI installed successfully!"
echo "   First run may download embedding models (~100MB)."
echo "   Type: jat"
echo "  ========================================"
echo ""
