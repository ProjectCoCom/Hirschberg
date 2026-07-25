"""
API router for task and session execution.

Responsibilities:
- Triggers manual task dispatches, polls running session logs, and relays task feedback.

Coupling:
- Integrates with 'src/core/session_runner.py' and 'src/core/workflow_engine.py'.
"""


from __future__ import annotations

import asyncio
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from config import load_settings
from db import db
from core.plan_executor import parse_plan
from core.config_loader import load_config, build_jules_pool
from core.context_store import ContextStore
from core.coordinator import AgentCoordinator
from core.workflow_engine import WorkflowEngine
from models.workflow import WorkflowStatus, TaskStatus, AgentTask
from clients.github import GitHubClient

router = APIRouter()
settings = load_settings()


class ExecuteRequest(BaseModel):
    plan_json: str
    repo_owner: str
    repo_name: str
    provider_type: str = ""
    model: str = ""


class TaskResult(BaseModel):
    task_id: str
    status: str
    session_id: str | None = None
    pr_url: str | None = None
    error: str | None = None


class ExecuteResponse(BaseModel):
    status: str
    results: list[TaskResult]


@router.post("/api/execute")
async def execute_plan(request: ExecuteRequest):
    token = settings.github_token
    if not token:
        raise HTTPException(400, "No GitHub token configured in .env")

    # 1. Parse plan JSON into models.workflow.Workflow object
    try:
        workflow = parse_plan(request.plan_json, request.repo_owner, request.repo_name)
    except Exception as e:
        raise HTTPException(400, f"Invalid plan: {e}")

    # 2. Build AccountPool from the database with config.json fallback
    config = load_config()
    pool = build_jules_pool(config)

    # 3. Check if we have any active/enabled accounts configured
    if not pool._accounts:
        await pool.close_all()
        raise HTTPException(400, "No enabled Jules API accounts configured")

    # 4. Insert workflow and pre-register tasks in SQLite database
    try:
        await db.insert("workflows", {
            "id": str(workflow.id),
            "name": workflow.name,
            "description": workflow.description,
            "status": str(workflow.status),
            "execution_mode": workflow.execution_mode,
        })
        for task in workflow.tasks:
            task.workflow_id = workflow.id
            await db.insert("agent_tasks", task.model_dump(mode="json"))
    except Exception as e:
        await pool.close_all()
        raise HTTPException(500, f"Database persistence failed: {e}")

    # 5. Execute using System A (WorkflowEngine)
    store = ContextStore(db)
    coordinator = AgentCoordinator(pool, store)
    engine = WorkflowEngine(coordinator, store)

    try:
        workflow = await engine.run(workflow)
    except Exception as e:
        workflow.status = WorkflowStatus.FAILED
        print(f"[WORKFLOW] Engine execution failed: {e}")
    finally:
        await db.update("workflows", {"status": str(workflow.status)}, {"id": str(workflow.id)})
        await pool.close_all()

    # 6. Retrieve latest tasks state from DB to return complete results
    results = []
    for task in workflow.tasks:
        try:
            db_task = await store.get_task_state(task.id)
            results.append(TaskResult(
                task_id=str(task.id),
                status=db_task.get("status", str(task.status)),
                session_id=db_task.get("session_id") or None,
                pr_url=db_task.get("pr_url") or None,
                error=db_task.get("error") or None,
            ))
        except Exception:
            results.append(TaskResult(
                task_id=str(task.id),
                status=str(task.status),
                session_id=task.session_id or None,
                pr_url=task.pr_url or None,
                error=task.error or None,
            ))

    # 7. Merge branches and create final PR if workflow is successful
    all_done = workflow.status == WorkflowStatus.COMPLETED
    if all_done:
        from core.merge_review import merge_branches, create_integration_branch, create_final_pr
        gh_client = GitHubClient(token)
        try:
            base_sha = await gh_client.get_default_branch_sha(request.repo_owner, request.repo_name)
            if base_sha:
                branches = [t.branch for t in workflow.tasks]
                integration = f"jat/integration-{request.repo_name}"
                await create_integration_branch(request.repo_owner, request.repo_name, base_sha, integration, token)
                await merge_branches(request.repo_owner, request.repo_name, branches, integration, token)
                await create_final_pr(request.repo_owner, request.repo_name, integration, "main", f"JAT-AI: {integration}", token)
        except Exception as e:
            print(f"[WORKFLOW] Post-execution merge/PR failed: {e}")
        finally:
            await gh_client.close()

    return ExecuteResponse(
        status="completed" if all_done else "failed",
        results=results,
    )


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


class StartOrchestratorRequest(BaseModel):
    repo_owner: str
    repo_name: str
    prompt: str = "Automated standing orchestrator session"


@router.post("/api/orchestrators/start")
async def start_orchestrator(request: StartOrchestratorRequest):
    from core.config_loader import load_config, build_jules_pool
    from core.account_pool import AccountRole
    from uuid import uuid4

    config = load_config()
    pool = build_jules_pool(config)

    source = f"sources/github/{request.repo_owner}/{request.repo_name}"
    try:
        # Prioritize ORCHESTRATOR role account
        account = pool.acquire(source, role=AccountRole.ORCHESTRATOR)
    except Exception:
        try:
            # Fall back to any available
            account = pool.acquire(source)
        except Exception as e:
            await pool.close_all()
            raise HTTPException(400, f"No available accounts configured: {e}")

    client = pool.get_client(account.id)
    try:
        session = await client.create_session(
            prompt=request.prompt,
            source=source,
            branch="main",
            title="JAT-AI Standing Orchestrator",
            require_plan_approval=True,
        )
        session_id = session.id

        # Insert a dummy agent_task for the orchestrator to satisfy foreign key constraints
        orchestrator_task_id = uuid4()
        await db.insert("agent_tasks", {
            "id": str(orchestrator_task_id),
            "prompt": request.prompt,
            "repo_owner": request.repo_owner,
            "repo_name": request.repo_name,
            "branch": "main",
            "status": "running",
            "session_id": session_id,
            "orchestrator_session_id": session_id,
        })

        await db.insert("orchestrator_sessions", {
            "id": str(orchestrator_task_id),
            "session_id": session_id,
            "repo_owner": request.repo_owner,
            "repo_name": request.repo_name,
            "status": "running",
        })

        # Launch background poller
        asyncio.create_task(_poll_orchestrator(session_id, str(account.id), request.repo_owner, request.repo_name, str(orchestrator_task_id)))

        return {
            "session_id": session_id,
            "account_id": str(account.id),
            "status": "running",
            "task_id": str(orchestrator_task_id),
        }
    except Exception as e:
        raise HTTPException(500, f"Failed to start orchestrator: {e}")
    finally:
        await pool.close_all()


async def _poll_orchestrator(session_id: str, account_id: str, owner: str, repo: str, task_id: str):
    from core.config_loader import load_config, build_jules_pool
    from models.jules import SessionState
    import asyncio

    config = load_config()
    pool = build_jules_pool(config)
    try:
        client = pool.get_client(UUID(account_id))
    except Exception:
        await pool.close_all()
        return

    last_activity_time = None
    try:
        while True:
            try:
                session = await client.get_session(session_id)
                status_map = {
                    SessionState.COMPLETED: "completed",
                    SessionState.FAILED: "failed",
                    SessionState.AWAITING_PLAN_APPROVAL: "awaiting_plan_approval",
                    SessionState.PAUSED: "paused",
                }
                new_status = status_map.get(session.state, "running")
                await db.update("orchestrator_sessions", {"status": new_status, "updated_at": _now()}, {"session_id": session_id})
                await db.update("agent_tasks", {"status": "running" if new_status == "running" else new_status}, {"id": task_id})

                try:
                    acts = await client.list_activities(session_id, since=last_activity_time)
                    for act in acts:
                        activity_type = "plan_generated" if act.plan_generated else ("agent_messaged" if act.agent_messaged else "progress_updated")
                        await db.upsert("session_activities", {
                            "task_id": task_id,
                            "session_id": session_id,
                            "activity_id": act.id,
                            "originator": act.originator,
                            "description": act.description or "",
                            "activity_type": activity_type,
                            "raw_data": act.model_dump(mode="json"),
                            "created_at": act.create_time.isoformat() if act.create_time else _now()
                        })
                        if act.create_time:
                            last_activity_time = act.create_time.isoformat()
                except Exception:
                    pass

                if session.state in (SessionState.COMPLETED, SessionState.FAILED):
                    break
            except Exception:
                pass
            await asyncio.sleep(15)
    finally:
        await pool.close_all()


@router.post("/api/orchestrators/{session_id}/approve")
async def approve_orchestrator_plan(session_id: str):
    from core.config_loader import load_config, build_jules_pool
    # Find account associated with the session
    try:
        tasks = await db.select("agent_tasks", {"session_id": session_id})
        if not tasks:
            raise HTTPException(404, "Orchestrator session not found in tasks")

        config = load_config()
        pool = build_jules_pool(config)

        # Try to find client
        client = None
        for acc in pool._accounts:
            client = pool.get_client(acc.id)
            break

        if not client:
            await pool.close_all()
            raise HTTPException(400, "No active Jules clients available")

        await client.approve_plan(session_id)
        await db.update("orchestrator_sessions", {"status": "running"}, {"session_id": session_id})
        await pool.close_all()
        return {"ok": True}
    except Exception as e:
        raise HTTPException(500, f"Approve plan failed: {e}")


@router.get("/api/orchestrators/{session_id}/decisions")
async def get_orchestrator_decisions(session_id: str):
    try:
        activities = await db.select("session_activities", {"session_id": session_id})
        tasks = await db.select("agent_tasks", {"orchestrator_session_id": session_id})
        return {
            "session_id": session_id,
            "activities": activities,
            "tasks": tasks
        }
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/api/projects/{owner}/{repo}/decisions")
async def get_project_decisions(owner: str, repo: str):
    try:
        sessions = await db.select("orchestrator_sessions", {"repo_owner": owner, "repo_name": repo})
        results = []
        for s in sessions:
            session_id = s["session_id"]
            activities = await db.select("session_activities", {"session_id": session_id})
            tasks = await db.select("agent_tasks", {"orchestrator_session_id": session_id})
            results.append({
                "session_id": session_id,
                "status": s["status"],
                "created_at": s["created_at"],
                "activities": activities,
                "tasks": tasks
            })
        return {"decisions": results}
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/api/session-limiter/status")
async def limiter_status():
    from core.session_limiter import get_session_limiter
    limiter = get_session_limiter()
    return limiter.status()


class MergeReviewRequest(BaseModel):
    repo_owner: str
    repo_name: str
    branches: list[str]
    integration_branch: str = "jat/integration"
    run_review: bool = True
    cleanup: bool = True


@router.post("/api/execute/merge-review")
async def merge_and_review(request: MergeReviewRequest):
    from core.merge_review import (
        merge_branches, create_integration_branch,
        run_review_session, cleanup_branches, create_final_pr,
    )
    from core.auto_mode import get_jules_key

    token = settings.github_token
    jules_key = await get_jules_key()
    if not token:
        raise HTTPException(400, "No GitHub token configured")

    gh_client = GitHubClient(token)
    try:
        base_sha = await gh_client.get_default_branch_sha(request.repo_owner, request.repo_name)
    finally:
        await gh_client.close()

    if not base_sha:
        raise HTTPException(500, "Could not get base SHA")

    await create_integration_branch(
        request.repo_owner, request.repo_name, base_sha, request.integration_branch, token
    )

    merge_results = await merge_branches(
        request.repo_owner, request.repo_name, request.branches, request.integration_branch, token
    )

    review_result = None
    if request.run_review and jules_key:
        context = "\n".join(f"- {b}: {s}" for b, s in merge_results.items())
        review_result = await run_review_session(
            request.repo_owner, request.repo_name, request.integration_branch,
            jules_key, context,
        )

    pr_url = await create_final_pr(
        request.repo_owner, request.repo_name, request.integration_branch,
        "main", f"JAT-AI: {request.integration_branch}", token,
    )

    cleanup_result = None
    if request.cleanup:
        cleanup_result = await cleanup_branches(
            request.repo_owner, request.repo_name, request.branches, token
        )

    return {
        "merge_results": merge_results,
        "review": review_result,
        "pr_url": pr_url,
        "cleanup": cleanup_result,
    }


class AutoModeRequest(BaseModel):
    repo_owner: str
    repo_name: str
    goal: str
    provider_type: str
    model: str
    max_sessions: int = 10
    execution_mode: str = "sequential"


@router.post("/api/execute/auto")
async def start_auto_mode(request: AutoModeRequest):
    from core.auto_mode import AutoModeConfig, AutoModeState, run_auto_mode

    config = AutoModeConfig(
        repo_owner=request.repo_owner,
        repo_name=request.repo_name,
        goal=request.goal,
        provider_type=request.provider_type,
        model=request.model,
        max_sessions=request.max_sessions,
        execution_mode=request.execution_mode,
    )
    state = AutoModeState()
    result = await run_auto_mode(config, state)

    return {
        "status": result.status,
        "sessions_used": result.sessions_used,
        "plan": result.plan_json,
        "errors": result.errors,
    }
