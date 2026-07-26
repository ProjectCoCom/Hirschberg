"""
End-to-end happy-path integration test.

Responsibilities:
- Seeds test accounts.
- Mocks external API calls (GitHub and Jules).
- Calls `/api/execute` to verify that workflow planning and execution complete successfully.

Coupling:
- Relies on the FastAPI application, the database client layer, and `WorkflowEngine`.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from api.execute import settings
from api.server import app
from db import db
from models.jules import SessionState


@pytest.mark.asyncio
async def test_execute_plan_happy_path():
    """Verify that a multi-task workflow successfully plans, runs, and merges via `/api/execute` endpoint."""
    client = TestClient(app)

    # Ensure settings has a github_token
    settings.github_token = "mock-github-token"

    # 1. Seed a valid account in the temporary DB
    await db.insert("accounts", {
        "id": "test-worker-uuid",
        "name": "test-worker",
        "plan": "free",
        "role": "worker",
        "enabled": 1,
    })

    plan_json = json.dumps({
        "title": "Auth Feature",
        "description": "Add JWT auth and endpoints",
        "tasks": [
            {
                "id": "agent-1",
                "description": "Add JWT middleware",
                "dependencies": [],
                "exit_criteria": "JWT token is returned",
                "branch": "jat/agent-1-auth",
            }
        ],
        "execution_mode": "sequential",
    })

    # Mocks
    mock_gh = AsyncMock()
    mock_gh.get_default_branch_sha.return_value = "default-sha-123"
    mock_gh.create_branch_from_ref.return_value = True
    mock_gh.merge_branch.return_value = "merged"
    mock_gh.create_pull_request.return_value = "https://github.com/owner/repo/pull/42"
    mock_gh.close = AsyncMock()

    mock_jules = AsyncMock()
    mock_session = MagicMock()
    mock_session.id = "session-jules-123"
    mock_session.state = SessionState.COMPLETED
    mock_session.outputs = []
    mock_jules.create_session.return_value = mock_session
    mock_jules.get_session.return_value = mock_session
    mock_jules.list_activities.return_value = []
    mock_jules.close = AsyncMock()

    # Define a clean mock account with real types for attributes accessed during execution
    mock_account = MagicMock()
    mock_account.id = "test-worker-uuid"
    mock_account.name = "test-worker"
    mock_account.plan = "free"
    mock_account.daily_tasks_used = 0
    mock_account.limits = {"daily_tasks": 15, "concurrent": 3}
    mock_account.active_sessions = 0

    # We patch build_jules_pool to return our mock pool
    mock_pool = MagicMock()
    mock_pool._accounts = [mock_account]
    mock_pool.acquire.return_value = mock_account
    mock_pool.get_client.return_value = mock_jules
    mock_pool.close_all = AsyncMock()

    # Act
    with patch("api.execute.build_jules_pool", return_value=mock_pool), \
         patch("clients.github.GitHubClient", return_value=mock_gh):

        response = client.post("/api/execute", json={
            "plan_json": plan_json,
            "repo_owner": "owner",
            "repo_name": "repo",
        })

    # Assert
    assert response.status_code == 200, f"Error: {response.content.decode()}"
    res_data = response.json()
    assert res_data["status"] == "completed"
    assert len(res_data["results"]) == 1
    assert res_data["results"][0]["status"] == "completed"
