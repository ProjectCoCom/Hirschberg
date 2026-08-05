"""
Summary: Crash recovery state manager.

What it does: Scans SQLite for crashed/hanging tasks on startup and moves them to failed states cleanly.

How it fits in: Runs at backend startup.
"""



from __future__ import annotations

import json
from pathlib import Path

STATE_DIR = Path("data/state")


def save_execution_state(workflow_id: str, state: dict) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    path = STATE_DIR / f"{workflow_id}.json"
    path.write_text(json.dumps(state, indent=2))


def load_execution_state(workflow_id: str) -> dict | None:
    path = STATE_DIR / f"{workflow_id}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text())


def clear_execution_state(workflow_id: str) -> None:
    path = STATE_DIR / f"{workflow_id}.json"
    if path.exists():
        path.unlink()


def list_pending_workflows() -> list[str]:
    if not STATE_DIR.exists():
        return []
    return [p.stem for p in STATE_DIR.glob("*.json")]
