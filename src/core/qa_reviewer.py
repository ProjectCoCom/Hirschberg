"""
Automated QA reviewer gatekeeper.

Responsibilities:
- Spins up a QA review session to validate changes on completed branches and parses verdict blocks.

Coupling:
- Mandatory step prior to pull request merge.
"""


from __future__ import annotations

import asyncio
from pathlib import Path
from uuid import uuid4

import structlog

from core.account_pool import AccountPool, AccountRole
from core.context_store import ContextStore
from models.jules import SessionState
from models.workflow import AgentTask

log = structlog.get_logger()


def load_qa_prompt(exit_criteria: str, task_description: str) -> str:
    path = Path("prompts/qa_reviewer.md")
    if not path.exists():
        # Fallback if the file was not written somehow
        return f"Identity: QA reviewer.\nExit Criteria: {exit_criteria}\nOriginal Task: {task_description}"
    content = path.read_text(encoding="utf-8")
    return content.replace("{exit_criteria}", exit_criteria).replace("{task_description}", task_description)


def extract_qa_verdict(text: str) -> dict | None:
    if '"verdict"' not in text:
        return None
    from core.json_extract import extract_json_object
    data = extract_json_object(text)
    if isinstance(data, dict) and "verdict" in data:
        return data
    return None


async def run_qa_review_for_task(
    pool: AccountPool,
    store: ContextStore,
    worker_task: AgentTask,
    pr_url: str,
) -> dict | None:
    """Dispatches a QA session on an available qa-role account.

    The QA session is pointed at the PR's head branch and parses the final output
    for a structured JSON QA verdict block. It sets the QA task's status to
    COMPLETED (never FAILED) regardless of verdict.
    """
    branch_name = worker_task.branch
    source = f"sources/github/{worker_task.repo_owner}/{worker_task.repo_name}"

    log.info("qa_review_dispatching", task_id=str(worker_task.id), branch=branch_name)

    # 1. Acquire a QA role account
    try:
        qa_account = pool.acquire(source, role=AccountRole.QA)
    except Exception as e:
        log.warning("qa_account_acquisition_failed", error=str(e))
        return None

    # 2. Create a child QA task in the database so it's visible on the canvas/dashboard
    qa_task_id = uuid4()
    await store.insert_task({
        "id": str(qa_task_id),
        "workflow_id": str(worker_task.workflow_id) if worker_task.workflow_id else None,
        "parent_task_id": str(worker_task.id),
        "prompt": f"QA Review of PR: {worker_task.prompt}",
        "repo_owner": worker_task.repo_owner,
        "repo_name": worker_task.repo_name,
        "branch": branch_name,
        "status": "running",
        "orchestrator_session_id": worker_task.orchestrator_session_id,
        "context": {"is_qa_task": True},
    })

    client = pool.get_client(qa_account.id)
    try:
        # 3. Build QA prompt and spawn the session
        exit_criteria = worker_task.exit_criteria or "Task completed as described"
        task_description = worker_task.prompt
        qa_prompt = load_qa_prompt(exit_criteria, task_description)

        session = await client.create_session(
            prompt=qa_prompt,
            source=source,
            branch=branch_name,
            title=f"QA Review: {worker_task.prompt[:60]}",
            automation_mode="",  # Unset automationMode
        )
        session_id = session.id
        await store.update_task(qa_task_id, {"session_id": session_id})

        # 4. Poll the QA session to capture the final verdict JSON block
        deadline = asyncio.get_event_loop().time() + 1800
        parsed_verdict = None
        while asyncio.get_event_loop().time() < deadline:
            session = await client.get_session(session_id)
            if session.state == SessionState.AWAITING_PLAN_APPROVAL:
                await client.approve_plan(session_id)

            # Check all activities for the verdict block
            try:
                acts = await client.list_activities(session_id)
                for act in acts:
                    if act.agent_messaged and act.agent_messaged.agent_message:
                        verdict = extract_qa_verdict(act.agent_messaged.agent_message)
                        if verdict:
                            parsed_verdict = verdict
            except Exception as e:
                log.error("unhandled_exception", error=str(e))
                pass

            if session.state in (SessionState.COMPLETED, SessionState.FAILED):
                break

            await asyncio.sleep(15)

        # 5. Default to reject if no verdict could be parsed
        if not parsed_verdict:
            parsed_verdict = {
                "verdict": "reject",
                "blocking_issues": [
                    {
                        "file": "N/A",
                        "issue": (
                            "QA session completed without returning a valid "
                            "JSON verdict block"
                        ),
                        "severity": "blocking",
                    }
                ],
                "summary": "QA session failed to return a proper JSON verdict.",
            }

        # 6. Save the verdict in context and mark the QA task as COMPLETED regardless of verdict
        await store.update_task(qa_task_id, {
            "status": "completed",
            "context": {"is_qa_task": True, "qa_verdict": parsed_verdict},
        })

        log.info("qa_review_completed", task_id=str(worker_task.id), verdict=parsed_verdict.get("verdict"))
        return parsed_verdict

    except Exception as e:
        log.warning("qa_review_execution_failed", error=str(e))
        # Save error to task context
        await store.update_task(qa_task_id, {
            "status": "completed",
            "context": {
                "is_qa_task": True,
                "qa_verdict": {
                    "verdict": "reject",
                    "blocking_issues": [{"file": "N/A", "issue": f"QA Execution Error: {e}", "severity": "blocking"}],
                    "summary": "QA execution raised an exception."
                }
            },
        })
        return None
    finally:
        pool.release(qa_account.id)
