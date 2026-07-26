"""
Dry-run integration test suite 'Test Full Workflow'.

Responsibilities:
- Implements automated tests, mock execution environments, or workflow assertions to verify core features.

Coupling:
- Triggered by pytest or CI workflows to guarantee codebase stability without making active live API requests.
"""


from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from tests.mocks import MOCK_PR_URL, MOCK_SHA, MockGitHubAPI, MockJulesAPI

mock_jules = MockJulesAPI()
mock_github = MockGitHubAPI()


SAMPLE_PLAN = json.dumps({
    "tasks": [
        {
            "id": "agent-1",
            "description": "Add user authentication with JWT",
            "dependencies": [],
            "exit_criteria": "Login endpoint returns valid JWT",
            "branch": "jat/agent-1-auth",
        },
        {
            "id": "agent-2",
            "description": "Add rate limiting middleware",
            "dependencies": [],
            "exit_criteria": "429 returned after 100 requests/min",
            "branch": "jat/agent-2-ratelimit",
        },
        {
            "id": "agent-3",
            "description": "Write integration tests for auth + rate limiting",
            "dependencies": ["agent-1", "agent-2"],
            "exit_criteria": "All tests pass",
            "branch": "jat/agent-3-tests",
        },
    ],
    "execution_mode": "hybrid",
    "max_sessions": 5,
})


async def test_plan_parser():
    from core.plan_executor import parse_plan
    plan = parse_plan(SAMPLE_PLAN, "iceyxsm", "TestRepo")
    assert len(plan.tasks) == 3
    assert len(plan.tasks[2].depends_on) == 2
    assert plan.execution_mode == "hybrid"
    print("[PASS] plan_parser: parsed 3 tasks with dependencies")


async def test_branch_creation():
    result = await mock_github.create_branch("iceyxsm", "TestRepo", "jat/agent-1-auth", MOCK_SHA, "token")
    assert result is True
    assert "jat/agent-1-auth" in mock_github.branches_created
    print("[PASS] branch_creation: created branch from SHA")


async def test_session_creation():
    session_id = await mock_jules.create_session(
        prompt="Add JWT auth",
        owner="iceyxsm",
        repo="TestRepo",
        branch="jat/agent-1-auth",
        jules_key="fake-key",
    )
    assert session_id == "dry-run-session-001"
    assert len(mock_jules.sessions_created) == 1
    print("[PASS] session_creation: Jules session created")


async def test_session_polling():
    result = await mock_jules.poll_status("dry-run-session-001", "fake-key")
    assert result["state"] == "COMPLETED"
    assert result["outputs"][0]["pull_request"]["url"] == MOCK_PR_URL
    print("[PASS] session_polling: session completed with PR")


async def test_merge_flow():
    await mock_github.merge("iceyxsm", "TestRepo", "jat/integration", "jat/agent-1-auth", "token")
    await mock_github.merge("iceyxsm", "TestRepo", "jat/integration", "jat/agent-2-ratelimit", "token")
    assert len(mock_github.merges) == 2
    print("[PASS] merge_flow: 2 branches merged into integration")


async def test_final_pr():
    url = await mock_github.create_pr("iceyxsm", "TestRepo", "jat/integration", "main", "JAT-AI: integration", "token")
    assert url == MOCK_PR_URL
    assert len(mock_github.prs_created) == 1
    print("[PASS] final_pr: PR created from integration to main")


async def test_mode_system_prompts():
    from api.chat import MODE_SYSTEM_PROMPTS
    assert "ask" in MODE_SYSTEM_PROMPTS
    assert "plan" in MODE_SYSTEM_PROMPTS
    assert "build" in MODE_SYSTEM_PROMPTS
    assert "JSON" in MODE_SYSTEM_PROMPTS["plan"]
    print("[PASS] mode_prompts: all 3 modes have system prompts")


async def test_repomix_trigger():
    from api.chat import ChatMessage, _is_repomix_trigger
    msgs = [ChatMessage(role="user", content="rrpo")]
    assert _is_repomix_trigger(msgs) is True
    msgs2 = [ChatMessage(role="user", content="hello")]
    assert _is_repomix_trigger(msgs2) is False
    print("[PASS] repomix_trigger: keyword detection works")


async def main():
    print("=" * 50)
    print("JAT-AI DRY RUN TESTS")
    print("=" * 50)
    print()

    await test_plan_parser()
    await test_branch_creation()
    await test_session_creation()
    await test_session_polling()
    await test_merge_flow()
    await test_final_pr()
    await test_mode_system_prompts()
    await test_repomix_trigger()

    print()
    print("=" * 50)
    print("ALL TESTS PASSED")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
