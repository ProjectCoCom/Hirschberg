"""
Pytest configuration and shared fixtures.

Responsibilities:
- Provides isolated temporary SQLite databases per test.
- Configures the test environment and sets up pytest-asyncio settings.

Coupling:
- Used by all pytest test suites to avoid side-effects on the production database.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from clients.local_db import LocalDB


@pytest.fixture(autouse=True)
def isolated_db(monkeypatch):
    """Provides a brand new, isolated temporary SQLite DB per test."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "jat_test.db"
        test_local_db = LocalDB(str(db_path))

        # Patch the global db's low-level client
        from db import db
        monkeypatch.setattr(db, "_local", test_local_db)

        # Force table initialization and migrations
        test_local_db._get_conn()

        yield test_local_db

        # Close connection to release the file lock
        test_local_db.close()
