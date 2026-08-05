"""
Summary: Python logic module 'Test Task 2 8'.

What it does: Provides backend utility operations and core logical helper interfaces for 'Test Task 2 8'.

How it fits in: Imported and utilized by surrounding backend structures.
"""


from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from api.server import app, _find_session_by_prompt, _recover_orphaned_tasks, _count_today_sessions, _fetch_jules_repos_as_tentacles, _fetch_jules_sessions_all_accounts
from db import db
from models.jules import Session, Source, GitHubRepo


@pytest.mark.asyncio
async def test_find_session_by_prompt_client_routing():
    task_row = {
        "prompt": "Test prompting session",
        "repo_owner": "owner-a",
        "repo_name": "repo-a",
        "created_at": "2026-05-10T06:38:00Z"
    }
    j_session = Session(
        id="sess-xyz",
        name="sessions/sess-xyz",
        title="JAT-AI: Test prompting session",
        create_time=None,
    )

    mock_client = AsyncMock()
    mock_client.list_sessions.return_value = [j_session]

    with patch("clients.jules.JulesClient", return_value=mock_client):
        res = await _find_session_by_prompt(task_row, "mock-key")
        assert res == "sess-xyz"
        mock_client.list_sessions.assert_called_once_with(page_size=20)
        mock_client.close.assert_called_once()


@pytest.mark.asyncio
async def test_recover_orphaned_tasks_client_routing():
    task_id = str(uuid4())
    session_id = "sess-orphan-abc"

    # Insert task that is 'running'
    await db.insert("agent_tasks", {
        "id": task_id,
        "prompt": "Orphaned test task",
        "repo_owner": "owner-b",
        "repo_name": "repo-b",
        "branch": "main",
        "status": "running",
        "session_id": session_id,
    })

    # Insert a mock account so _get_jules_key succeeds
    await db.insert("accounts", {
        "id": "acc-recovery-id",
        "name": "recovery-acc",
        "api_key_encrypted": "encrypted-key",
        "plan": "ultra",
        "role": "worker",
        "enabled": 1,
    })

    j_session = Session(
        id=session_id,
        state="COMPLETED"
    )

    mock_client = AsyncMock()
    mock_client.get_session.return_value = j_session

    # Mock _get_jules_key to return key
    with patch("api.server._get_jules_key", return_value="some-key"), \
         patch("clients.jules.JulesClient", return_value=mock_client), \
         patch("api.server._resume_polling", new_callable=AsyncMock) as mock_resume:
        await _recover_orphaned_tasks()
        mock_client.get_session.assert_called_once_with(session_id)
        mock_client.close.assert_called_once()

    # Task status should now be completed in DB
    rows = await db.select("agent_tasks", {"id": task_id})
    assert rows[0]["status"] == "completed"


@pytest.mark.asyncio
async def test_count_today_sessions_client_routing():
    accounts = [
        {
            "id": "acc-c",
            "name": "acc-c",
            "enabled": 1,
            "api_key_encrypted": "encrypted-c",
        }
    ]
    # Current date
    from datetime import datetime, UTC
    today_prefix = datetime.now(UTC).strftime("%Y-%m-%d")

    j_session = Session(
        id="s-today",
        create_time=datetime.now(UTC)
    )

    mock_client = AsyncMock()
    mock_client.list_sessions.return_value = [j_session]

    with patch("clients.jules.JulesClient", return_value=mock_client), \
         patch("core.ai_interface.KeyVault.decrypt", return_value="decrypted-key"):
        total = await _count_today_sessions(accounts)
        assert total == 1
        mock_client.list_sessions.assert_called_once_with(page_size=100)
        mock_client.close.assert_called_once()


@pytest.mark.asyncio
async def test_fetch_jules_repos_as_tentacles_client_routing():
    j_source = Source(
        id="src-1",
        name="sources/src-1",
        github_repo=GitHubRepo(owner="owner-d", repo="repo-d")
    )

    mock_client = AsyncMock()
    mock_client.list_sources.return_value = [j_source]

    with patch("api.server._get_jules_key", return_value="some-key"), \
         patch("clients.jules.JulesClient", return_value=mock_client):
        repos = await _fetch_jules_repos_as_tentacles()
        assert "owner-d/repo-d" in repos
        assert repos["owner-d/repo-d"]["name"] == "repo-d"
        mock_client.list_sources.assert_called_once()
        mock_client.close.assert_called_once()


@pytest.mark.asyncio
async def test_fetch_jules_sessions_all_accounts_client_routing():
    accounts = [
        {
            "id": "acc-e",
            "name": "acc-e",
            "enabled": 1,
            "api_key_encrypted": "encrypted-e",
        }
    ]
    from datetime import datetime, UTC
    j_session = Session(
        id="s-paginated",
        create_time=datetime.now(UTC),
        source_context={"source": "sources/github/owner-e/repo-e"},
        state="COMPLETED",
        title="Test Tit"
    )

    mock_client = AsyncMock()
    mock_client.list_sessions_paginated.return_value = ([j_session], None)

    with patch("db.db.select", return_value=accounts), \
         patch("clients.jules.JulesClient", return_value=mock_client), \
         patch("core.ai_interface.KeyVault.decrypt", return_value="decrypted-key"):
        sessions_by_date, projects = await _fetch_jules_sessions_all_accounts()
        assert "owner-e/repo-e" in projects
        mock_client.list_sessions_paginated.assert_called_once_with(page_size=100, page_token=None)
        mock_client.close.assert_called_once()


def test_api_test_account_client_routing():
    account_id = "acc-test-api"
    row = {
        "id": account_id,
        "name": "test-acc-name",
        "api_key_encrypted": "encrypted-key",
    }

    mock_client = AsyncMock()
    # Mock list_sources
    mock_client.list_sources.return_value = [MagicMock()]

    client = TestClient(app)

    with patch("db.db.select", return_value=[row]), \
         patch("clients.jules.JulesClient", return_value=mock_client):
        response = client.get(f"/api/jules/accounts/{account_id}/test")
        assert response.status_code == 200
        assert response.json() == {"ok": True, "sources_count": 1}
        mock_client.list_sources.assert_called_once()
        mock_client.close.assert_called_once()


def test_api_list_jules_sessions_client_routing():
    row = {
        "id": "acc-sessions",
        "name": "test-acc-sessions",
        "api_key_encrypted": "encrypted-key",
        "enabled": 1,
    }

    j_session = Session(
        id="s-list",
        create_time=None,
        state="COMPLETED",
        title="Listing sessions test"
    )

    mock_client = AsyncMock()
    mock_client.list_sessions.return_value = [j_session]

    client = TestClient(app)

    with patch("db.db.select", return_value=[row]), \
         patch("clients.jules.JulesClient", return_value=mock_client):
        response = client.get("/api/jules/sessions")
        assert response.status_code == 200
        data = response.json()
        assert len(data["sessions"]) == 1
        assert data["sessions"][0]["id"] == "s-list"
        assert data["sessions"][0]["_account_name"] == "test-acc-sessions"
        mock_client.list_sessions.assert_called_once()
        mock_client.close.assert_called_once()


def test_api_get_session_detail_client_routing():
    row = {
        "id": "acc-detail",
        "name": "test-acc-detail",
        "api_key_encrypted": "encrypted-key",
    }

    j_session = Session(
        id="s-detail",
        create_time=None,
        state="COMPLETED",
        title="Detail session test"
    )

    mock_client = AsyncMock()
    mock_client.get_session.return_value = j_session

    client = TestClient(app)

    with patch("db.db.select", return_value=[row]), \
         patch("clients.jules.JulesClient", return_value=mock_client):
        response = client.get("/api/jules/sessions/s-detail")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "s-detail"
        assert data["_account_name"] == "test-acc-detail"
        mock_client.get_session.assert_called_once_with("s-detail")
        mock_client.close.assert_called_once()


def test_api_send_session_message_client_routing():
    row = {
        "id": "acc-message",
        "name": "test-acc-message",
        "api_key_encrypted": "encrypted-key",
    }

    mock_client = AsyncMock()
    mock_client.send_message.return_value = None

    client = TestClient(app)

    with patch("db.db.select", return_value=[row]), \
         patch("clients.jules.JulesClient", return_value=mock_client):
        response = client.post("/api/jules/sessions/s-message/message", json={"message": "Hello Jules!"})
        assert response.status_code == 200
        assert response.json() == {"ok": True}
        mock_client.send_message.assert_called_once_with("s-message", "Hello Jules!")
        mock_client.close.assert_called_once()
