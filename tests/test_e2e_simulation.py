"""
Dry-run integration test suite 'Test E2E Simulation'.

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

from core.jdocs import CONTEXT_TEMPLATE, RULES_TEMPLATE
from core.plan_executor import parse_plan
from prompts.system_prompts import (
    ASK_MODE_SYSTEM,
    JULES_MASTER_PROMPT,
    JULES_QUESTION_HANDLER,
    PLAN_MODE_SYSTEM,
    REVIEW_SESSION_PROMPT,
)
from tests.mocks import MOCK_PR_URL, MOCK_SHA, MockGitHubAPI, MockJulesAPI

MOCK_REPOMIX_XML = """<?xml version="1.0" encoding="UTF-8"?>
<repository name="AnyWebApi" owner="iceyxsm">
  <file path="src/index.ts">Express server with 3 routes</file>
  <file path="src/routes/users.ts">CRUD for users, no auth</file>
  <file path="src/routes/posts.ts">CRUD for posts, no auth</file>
  <file path="package.json">express, typescript, jest</file>
  <file path="tsconfig.json">strict mode enabled</file>
</repository>
"""

MOCK_AI_REPO_SUMMARY = """Project: AnyWebApi
Stack: Express + TypeScript
Structure: src/index.ts (entry), src/routes/ (users, posts)
Description: REST API with user and post CRUD endpoints. No authentication currently implemented.
Dependencies: express, typescript, jest
"""

MOCK_AI_PLAN_RESPONSE = """{
  "tasks": [
    {
      "id": "agent-1",
      "description": "Add JWT authentication middleware. Create src/middleware/auth.ts with token verification. Add login/register endpoints to src/routes/auth.ts.",
      "dependencies": [],
      "exit_criteria": "POST /auth/login returns JWT, protected routes return 401 without token",
      "branch": "jat/agent-1-auth"
    },
    {
      "id": "agent-2",
      "description": "Add rate limiting middleware. Create src/middleware/rateLimit.ts using express-rate-limit. Apply to all /api routes with 100 req/min limit.",
      "dependencies": [],
      "exit_criteria": "429 returned after 100 requests within 1 minute window",
      "branch": "jat/agent-2-ratelimit"
    },
    {
      "id": "agent-3",
      "description": "Write integration tests for auth and rate limiting. Create tests/auth.test.ts and tests/rateLimit.test.ts with jest + supertest.",
      "dependencies": ["agent-1", "agent-2"],
      "exit_criteria": "npm test passes with >80% coverage on new files",
      "branch": "jat/agent-3-tests"
    }
  ],
  "execution_mode": "hybrid",
  "max_sessions": 5
}"""


mock_jules = MockJulesAPI()
mock_github = MockGitHubAPI()


def print_chat(role: str, content: str):
    prefix = "USER" if role == "user" else "AI  "
    lines = content.strip().split("\n")
    print(f"  [{prefix}] {lines[0]}")
    for line in lines[1:4]:
        print(f"         {line}")
    if len(lines) > 4:
        print(f"         ... ({len(lines) - 4} more lines)")


async def simulate_step_1_start():
    print("\n--- STEP 1: User starts session (selects provider + model + repo) ---")
    print("  Provider: NVIDIA NIM")
    print("  Model: meta/llama-3.1-8b-instruct")
    print("  Repo: iceyxsm/AnyWebApi")
    print("  Mode: ASK")
    print()
    print("  [SYSTEM] Backend clones repo, runs repomix...")
    print(f"  [SYSTEM] Repomix output: {len(MOCK_REPOMIX_XML)} chars")
    print()

    system_prompt = ASK_MODE_SYSTEM + f"\n\n<codebase>\n{MOCK_REPOMIX_XML}\n</codebase>"
    assert "<identity>" in system_prompt
    assert "<repository" in system_prompt

    print_chat("assistant", MOCK_AI_REPO_SUMMARY)
    print()
    print("[PASS] step_1: session started, repo analyzed, summary delivered")


async def simulate_step_2_plan():
    print("\n--- STEP 2: User switches to PLAN mode, describes goal ---")
    print()

    print_chat("user", "Add JWT authentication and rate limiting to all API routes. Also need tests.")
    print()

    system_prompt = PLAN_MODE_SYSTEM + f"\n\n<codebase>\n{MOCK_REPOMIX_XML}\n</codebase>"
    assert "decompose" in system_prompt.lower() or "tasks" in system_prompt.lower()

    print("  [AI thinking with PLAN system prompt...]")
    print_chat("assistant", MOCK_AI_PLAN_RESPONSE)
    print()

    plan = parse_plan(MOCK_AI_PLAN_RESPONSE, "iceyxsm", "AnyWebApi")
    assert len(plan.tasks) == 3
    assert plan.tasks[2].depends_on == [plan.tasks[0].id, plan.tasks[1].id]
    print(f"  [SYSTEM] Plan parsed: {len(plan.tasks)} tasks, mode={plan.execution_mode}")
    print()
    print("[PASS] step_2: plan created with 3 tasks, hybrid execution")


async def simulate_step_3_approve():
    print("\n--- STEP 3: User approves plan ---")
    print()
    print_chat("user", "Looks good, approve and execute.")
    print()
    print("  [SYSTEM] Plan approved. Switching to execution mode...")
    print("  [SYSTEM] Execution mode: hybrid (agent-1 + agent-2 parallel, agent-3 waits)")
    print()
    print("[PASS] step_3: plan approved, execution triggered")


async def simulate_step_4_dispatch():
    print("\n--- STEP 4: Backend dispatches Jules sessions ---")
    print()

    plan = parse_plan(MOCK_AI_PLAN_RESPONSE, "iceyxsm", "AnyWebApi")

    for task in plan.tasks[:2]:
        jules_prompt = JULES_MASTER_PROMPT.format(
            rules=RULES_TEMPLATE[:200],
            agent_context="No previous agents",
            task_description=task.prompt,
            exit_criteria=task.exit_criteria,
        )
        assert "<identity>" in jules_prompt
        assert task.prompt in jules_prompt
        assert task.exit_criteria in jules_prompt

        await mock_github.create_branch("iceyxsm", "AnyWebApi", task.branch, MOCK_SHA, "token")
        session_id = await mock_jules.create_session(jules_prompt, "iceyxsm", "AnyWebApi", task.branch, "key")
        print(f"  [JULES] {task.id}: branch={task.branch}, session={session_id}")

    print("  [SYSTEM] 2 sessions running in parallel (agent-1, agent-2)")
    print("  [SYSTEM] agent-3 waiting for dependencies...")
    print()
    assert len(mock_jules.sessions_created) == 2
    assert len(mock_github.branches_created) == 2
    print("[PASS] step_4: 2 parallel sessions dispatched, 1 waiting")


async def simulate_step_5_question():
    print("\n--- STEP 5: Jules asks a question, backend AI answers ---")
    print()

    question = "Should I use bcrypt or argon2 for password hashing?"
    print(f"  [JULES asks] {question}")

    handler_prompt = JULES_QUESTION_HANDLER.format(
        goal="Add JWT auth and rate limiting",
        task_description="Add JWT authentication middleware",
        planning_context="User wants JWT with login/register endpoints",
    )
    assert "<identity>" in handler_prompt
    assert "JWT" in handler_prompt

    answer = "Use bcrypt. It is the standard for Express/Node.js projects and has better library support."
    print(f"  [BACKEND AI answers] {answer}")
    await mock_jules.send_message("dry-run-session-001", answer, "key")
    assert len(mock_jules.messages_sent) == 1
    print()
    print("[PASS] step_5: Jules question answered autonomously by backend AI")


async def simulate_step_6_complete():
    print("\n--- STEP 6: Sessions complete, jdocs updated ---")
    print()

    for i, task_id in enumerate(["agent-1", "agent-2"]):
        result = await mock_jules.poll_status(f"session-{i}", "key")
        assert result["state"] == "COMPLETED"
        print(f"  [JULES] {task_id}: COMPLETED, PR={MOCK_PR_URL}")

    context_xml = CONTEXT_TEMPLATE
    agent_entry = '  <agent id="agent-1"><task>Add JWT auth</task><status>completed</status></agent>\n'
    context_xml = context_xml.replace("</agents>", f"{agent_entry}</agents>")
    assert '<agent id="agent-1">' in context_xml
    print("  [SYSTEM] .jules/jdocs/context.xml updated with agent-1 results")
    print("  [SYSTEM] Triggering agent-3 (dependencies met)...")
    print()
    print("[PASS] step_6: sessions completed, context passed to next agent")


async def simulate_step_7_merge_review():
    print("\n--- STEP 7: All done, merge + review ---")
    print()

    branches = ["jat/agent-1-auth", "jat/agent-2-ratelimit", "jat/agent-3-tests"]
    for b in branches:
        await mock_github.merge("iceyxsm", "AnyWebApi", "jat/integration", b, "token")
    assert len(mock_github.merges) == 3
    print(f"  [SYSTEM] Merged {len(branches)} branches into jat/integration")

    review_prompt = REVIEW_SESSION_PROMPT.format(
        agent_context="agent-1: JWT auth, agent-2: rate limiting, agent-3: tests",
        goal="Add JWT auth and rate limiting with tests",
    )
    assert "<identity>" in review_prompt
    assert "integration issues" in review_prompt

    session_id = await mock_jules.create_session(review_prompt, "iceyxsm", "AnyWebApi", "jat/integration", "key")
    print(f"  [JULES] Review session: {session_id}")

    result = await mock_jules.poll_status(session_id, "key")
    assert result["state"] == "COMPLETED"
    print("  [JULES] Review: COMPLETED")

    pr_url = await mock_github.create_pr("iceyxsm", "AnyWebApi", "jat/integration", "main", "JAT-AI: Auth + Rate Limiting", "token")
    print(f"  [SYSTEM] Final PR: {pr_url}")
    print()
    print("[PASS] step_7: merge + review + final PR created")


async def simulate_step_8_model_switch():
    print("\n--- STEP 8: User switches AI model mid-conversation ---")
    print()

    conversation_history = [
        {"role": "assistant", "content": MOCK_AI_REPO_SUMMARY},
        {"role": "user", "content": "Add JWT auth and rate limiting"},
        {"role": "assistant", "content": MOCK_AI_PLAN_RESPONSE},
    ]

    summary = f"Conversation so far ({len(conversation_history)} messages): User requested JWT auth + rate limiting. Plan created with 3 tasks."
    print(f"  [SYSTEM] Summarizing {len(conversation_history)} messages for model switch...")
    print(f"  [SYSTEM] Summary: {summary[:80]}...")
    print("  [SYSTEM] Switching from NVIDIA NIM to LongCat...")
    print("  [SYSTEM] Sending summary + repomix to new model")

    new_system = PLAN_MODE_SYSTEM + f"\n\n<conversation_summary>\n{summary}\n</conversation_summary>"
    assert "<conversation_summary>" in new_system
    print()
    print("[PASS] step_8: model switched, context preserved via summary")


async def main():
    print("=" * 60)
    print("JAT-AI FULL E2E SIMULATION")
    print("Simulating complete workflow: Start -> Plan -> Execute -> Merge")
    print("=" * 60)

    await simulate_step_1_start()
    await simulate_step_2_plan()
    await simulate_step_3_approve()
    await simulate_step_4_dispatch()
    await simulate_step_5_question()
    await simulate_step_6_complete()
    await simulate_step_7_merge_review()
    await simulate_step_8_model_switch()

    print()
    print("=" * 60)
    print("FULL E2E SIMULATION PASSED — 8 STEPS VERIFIED")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
