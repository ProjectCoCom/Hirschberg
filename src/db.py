"""
Summary: Database connection and session management.

What it does: Initializes the SQLite database engine, sets WAL mode, enforces foreign keys, and manages thread-local connection sessions.

How it fits in: Used by 'src/clients/database.py' and across the API controllers to interact with the database.
"""



import json
from pathlib import Path

from clients.database import Database
from config import load_settings

settings = load_settings()

_config_path = Path("config.json")
_db_config = {"mode": "local", "local_path": "./data/jat.db", "sync_interval": 30}
if _config_path.exists():
    try:
        raw = json.loads(_config_path.read_text())
        _db_config = raw.get("database", _db_config)
    except Exception:
        pass

db = Database(
    mode="local",
    local_path=_db_config.get("local_path", "./data/jat.db"),
    sync_interval=_db_config.get("sync_interval", 30),
)
