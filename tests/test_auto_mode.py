"""
Summary: Python logic module 'Test Auto Mode'.

What it does: Provides backend utility operations and core logical helper interfaces for 'Test Auto Mode'.

How it fits in: Imported and utilized by surrounding backend structures.
"""



from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


MOCK_PLAN_RESPONSE = '''{
    "tasks": [
        {"id": "agent-1", "description": "Setup project structure", "dependencies": [], "exit_criteria": "package.json exists", "branch": "jat/agent-1-setup"},
        {"id": "agent-2", "description": "Add API routes", "dependencies": ["agent-1"], "exit_criteria": "GET /api/health returns 200", "branch": "jat/agent-2-routes"}
    ],
    "execution_mode": "sequential",
    "max_sessions": 5
}'''


async def test_auto_mode_config():
    from core.auto_mode import AutoModeConfig, AutoModeState
    config = AutoModeConfig(
        repo_owner="iceyxsm",
        repo_name="TestRepo",
        goal="Build a REST API with health check",
        provider_type="nvidia_nim",
        model="meta/llama-3.1-8b-instruct",
        max_sessions=5,
        execution_mode="sequential",
    )
    state = AutoModeState()
    assert config.max_sessions == 5
    assert state.status == "idle"
    assert state.sessions_used == 0
    print("[PASS] auto_mode_config: config and state initialized")


async def test_plan_extraction():
    from core.auto_mode import _extract_plan_json
    raw = f"Here is the plan:\n{MOCK_PLAN_RESPONSE}\nLet me know if you want changes."
    plan_json = await _extract_plan_json(raw)
    import json
    data = json.loads(plan_json)
    assert len(data["tasks"]) == 2
    assert data["tasks"][0]["id"] == "agent-1"
    print("[PASS] plan_extraction: extracted JSON from AI response")


async def test_interruption():
    from core.auto_mode import AutoModeState
    state = AutoModeState()
    state.interrupted = True
    state.status = "executing"
    assert state.interrupted is True
    print("[PASS] interruption: state flag set correctly")


async def test_state_transitions():
    from core.auto_mode import AutoModeState
    state = AutoModeState()
    assert state.status == "idle"
    state.status = "analyzing"
    assert state.status == "analyzing"
    state.status = "planning"
    state.status = "executing"
    state.status = "completed"
    state.sessions_used = 3
    assert state.sessions_used == 3
    print("[PASS] state_transitions: idle -> analyzing -> planning -> executing -> completed")


async def test_error_accumulation():
    from core.auto_mode import AutoModeState
    state = AutoModeState()
    state.errors.append("agent-1: timeout")
    state.errors.append("agent-2: branch conflict")
    assert len(state.errors) == 2
    state.status = "partial"
    print("[PASS] error_accumulation: errors tracked, status set to partial")


import json

import pytest


@pytest.mark.asyncio
async def test_run_auto_mode_execution():
    from core.auto_mode import AutoModeConfig, AutoModeState, run_auto_mode, settings
    settings.github_token = "mock-github-token"
    from unittest.mock import AsyncMock, patch
    from uuid import uuid4

    from models.workflow import AgentTask, TaskStatus, Workflow, WorkflowStatus

    config = AutoModeConfig(
        repo_owner="owner",
        repo_name="repo",
        goal="Test goal",
        provider_type="google",
        model="gemini-1.5",
    )
    state = AutoModeState()

    # Seed an account so we don't fail pool check
    from db import db
    account_uuid = str(uuid4())
    await db.insert("accounts", {
        "id": account_uuid,
        "name": "test-account",
        "plan": "free",
        "role": "worker",
        "enabled": 1,
    })

    # Prepare mock workflow returned by engine
    mock_task = AgentTask(
        id=uuid4(),
        prompt="Setup project structure",
        repo_owner="owner",
        repo_name="repo",
        branch="jat/agent-1-setup",
        status=TaskStatus.COMPLETED,
        session_id="mock-session-id",
    )
    mock_workflow = Workflow(
        id=uuid4(),
        name="Test Workflow",
        status=WorkflowStatus.COMPLETED,
        tasks=[mock_task],
    )

    with patch("core.auto_mode._analyze_phase", new_callable=AsyncMock) as mock_analyze, \
         patch("core.auto_mode._planning_phase", new_callable=AsyncMock) as mock_plan_phase, \
         patch("core.workflow_engine.WorkflowEngine.run", new_callable=AsyncMock) as mock_engine_run:

        mock_analyze.return_value = "<repository></repository>"
        mock_plan_phase.return_value = json.dumps({
            "tasks": [
                {"id": "agent-1", "description": "Setup project structure", "dependencies": [], "exit_criteria": "package.json exists", "branch": "jat/agent-1-setup"}
            ],
            "execution_mode": "sequential",
        })
        mock_engine_run.return_value = mock_workflow

        res_state = await run_auto_mode(config, state)
        if res_state.status != "completed":
            assert False, f"Errors: {res_state.errors}"
        assert res_state.status == "completed"
        assert res_state.sessions_used == 1
        assert len(res_state.errors) == 0


async def main():
    print("=" * 50)
    print("JAT-AI AUTO MODE DRY RUN")
    print("=" * 50)
    print()

    await test_auto_mode_config()
    await test_plan_extraction()
    await test_interruption()
    await test_state_transitions()
    await test_error_accumulation()

    print()
    print("=" * 50)
    print("ALL AUTO MODE TESTS PASSED")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
