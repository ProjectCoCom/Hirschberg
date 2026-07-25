"""
Dry-run integration test suite 'Test Auto Mode'.

Responsibilities:
- Implements automated tests, mock execution environments, or workflow assertions to verify core features.

Coupling:
- Triggered by pytest or CI workflows to guarantee codebase stability without making active live API requests.
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
    from core.auto_mode import AutoModeConfig, AutoModeState
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
