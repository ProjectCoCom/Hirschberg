#!/bin/bash
# Cleanup script for Hirschberg project
# Removes temporary files, cache directories, and build artifacts

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "Starting cleanup in $PROJECT_ROOT..."

# Remove Python cache directories
echo "Removing __pycache__ directories..."
find "$PROJECT_ROOT" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

# Remove .pytest_cache
echo "Removing .pytest_cache directories..."
find "$PROJECT_ROOT" -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true

# Remove .mypy_cache
echo "Removing .mypy_cache directories..."
find "$PROJECT_ROOT" -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true

# Remove .ruff_cache
echo "Removing .ruff_cache directories..."
find "$PROJECT_ROOT" -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true

# Remove compiled Python files
echo "Removing .pyc files..."
find "$PROJECT_ROOT" -type f -name "*.pyc" -delete 2>/dev/null || true

# Remove Python optimization files
echo "Removing .pyo files..."
find "$PROJECT_ROOT" -type f -name "*.pyo" -delete 2>/dev/null || true

# Remove distribution directories
echo "Removing dist and build directories..."
rm -rf "$PROJECT_ROOT/dist" 2>/dev/null || true
rm -rf "$PROJECT_ROOT/build" 2>/dev/null || true
find "$PROJECT_ROOT" -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true

# Remove Jupyter checkpoints
echo "Removing Jupyter checkpoints..."
find "$PROJECT_ROOT" -type d -name ".ipynb_checkpoints" -exec rm -rf {} + 2>/dev/null || true

# Remove environment-specific files (but not .env itself)
echo "Removing local environment copies..."
find "$PROJECT_ROOT" -type f -name ".env.local" -delete 2>/dev/null || true

# Remove logs
echo "Removing log files..."
find "$PROJECT_ROOT" -type f -name "*.log" -delete 2>/dev/null || true

# Remove SQLite database files in data directory (if they exist)
echo "Removing temporary database files..."
find "$PROJECT_ROOT/data" -type f -name "*.db" -delete 2>/dev/null || true
find "$PROJECT_ROOT/data" -type f -name "*.sqlite" -delete 2>/dev/null || true
find "$PROJECT_ROOT/data" -type f -name "*.sqlite3" -delete 2>/dev/null || true

# Remove coverage reports
echo "Removing coverage reports..."
rm -rf "$PROJECT_ROOT/htmlcov" 2>/dev/null || true
rm -f "$PROJECT_ROOT/.coverage" 2>/dev/null || true

# Remove Node.js modules (if any)
echo "Removing node_modules..."
rm -rf "$PROJECT_ROOT/node_modules" 2>/dev/null || true

# Remove Docker-related temporary files
echo "Removing Docker temporary files..."
rm -rf "$PROJECT_ROOT/.docker-build" 2>/dev/null || true

echo "Cleanup complete!"
