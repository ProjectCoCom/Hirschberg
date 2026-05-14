from __future__ import annotations

import os
import subprocess
import sys
import time
import shutil
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


def _wait_for_port(port: str, timeout: int = 30):
    for _ in range(timeout):
        time.sleep(1)
        try:
            import httpx

            r = httpx.get(f"http://localhost:{port}/api/setup", timeout=2)
            if r.status_code == 200:
                return True
        except Exception:
            continue
    return False


def _start_backend(root: Path, src_dir: Path, port: str) -> subprocess.Popen:
    print(f"[BACKEND] Starting FastAPI on port {port}...")
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "api.server:app", "--port", port, "--reload", "--app-dir", str(src_dir)],
        cwd=str(root),
    )
    print("[BACKEND] Waiting for server...")
    _wait_for_port(port)
    print(f"[BACKEND] Ready on http://localhost:{port}")
    return proc


def _start_frontend(dashboard_dir: Path, port: str) -> subprocess.Popen | None:
    if not dashboard_dir.exists() or not (dashboard_dir / "package.json").exists():
        return None

    if shutil.which("pnpm") is None:
        print("[ERROR] pnpm is required to start the dashboard. Install pnpm and try again.")
        return None

    if not (dashboard_dir / "node_modules").exists():
        print("[SETUP] Installing dashboard dependencies...")
        subprocess.run(["pnpm", "install"], cwd=str(dashboard_dir))

    print(f"[FRONTEND] Starting Vite on port {port}...")
    proc = subprocess.Popen(
        ["pnpm", "exec", "vite", "--port", port],
        cwd=str(dashboard_dir),
    )
    for _ in range(15):
        time.sleep(1)
        try:
            import httpx

            r = httpx.get(f"http://localhost:{port}", timeout=2)
            if r.status_code == 200:
                break
        except Exception:
            continue
    print(f"[FRONTEND] Ready on http://localhost:{port}")
    return proc


def main():
    root = Path(__file__).resolve().parent.parent
    env_file = root / ".env"
    dashboard_dir = root / "dashboard"

    if not env_file.exists():
        print("[ERROR] .env file not found. Copy .env.example and fill in your keys.")
        sys.exit(1)

    port = os.environ.get("BACKEND_PORT", "8000")
    frontend_port = os.environ.get("FRONTEND_PORT", "3000")

    print()
    print("  ========================================")
    print("   JAT-AI - Starting...")
    print("  ========================================")
    print()

    backend = _start_backend(root, root / "src", port)
    frontend = _start_frontend(dashboard_dir, frontend_port)

    if dashboard_dir.exists() and (dashboard_dir / "package.json").exists() and frontend is None:
        print("[ERROR] Frontend failed to start.")
        backend.terminate()
        sys.exit(1)

    url = f"http://localhost:{frontend_port}" if frontend else f"http://localhost:{port}"
    print()
    print("  ========================================")
    print(f"   JAT-AI running at {url}")
    print("   Press Ctrl+C to stop")
    print("  ========================================")
    print()

    import webbrowser

    webbrowser.open(url)

    try:
        backend.wait()
    except KeyboardInterrupt:
        print("\n[SHUTDOWN] Stopping...")
        backend.terminate()
        if frontend:
            frontend.terminate()


if __name__ == "__main__":
    main()
