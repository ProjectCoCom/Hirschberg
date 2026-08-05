"""
Summary: Runner for standalone agent sessions.

What it does: Sets up, runs, and monitors standalone agent tasks from creation through completion.

How it fits in: Connected to API execution endpoints.
"""



from __future__ import annotations

import structlog

from clients.database import Database
from clients.github import GitHubClient
from clients.jules import JulesClient
from core.auto_merge import AutoMerge, MergeStrategy
from core.context_store import ContextStore
from core.prompt_builder import build_session_prompt
from models.jules import SessionState

log = structlog.get_logger()

POLL_INTERVAL = 15
SESSION_TIMEOUT = 1800


async def run_session(
    jules: JulesClient,
    db: Database,
    prompt: str,
    source: str,
    branch: str = "main",
    title: str = "",
    task_id: str | None = None,
    github: GitHubClient | None = None,
    auto_merge: bool = False,
    merge_strategy: str = "squash",
    dependency_context: list[dict] | None = None,
) -> dict:
    session_title = title or prompt[:80]
    full_prompt = build_session_prompt(prompt, dependency_context)

    session = await jules.create_session(
        prompt=full_prompt,
        source=source,
        branch=branch,
        title=session_title,
    )
    log.info("session_created", session_id=session.id, title=session_title)

    if task_id:
        await db.update(
            "agent_tasks",
            {"session_id": session.id, "status": "running"},
            {"id": task_id},
        )

    result = await _poll_until_done(jules, db, session.id, task_id)

    if task_id:
        store = ContextStore(db)
        await store.save_result(task_id, result)

    if auto_merge and github and result["pr_url"]:
        result = await _try_auto_merge(github, db, result, source, merge_strategy)

    return result


async def _try_auto_merge(
    github: GitHubClient,
    db: Database,
    result: dict,
    source: str,
    merge_strategy: str,
) -> dict:
    pr_url = result["pr_url"]
    # Extract owner, repo, and PR number from the URL
    # Format: https://github.com/{owner}/{repo}/pull/{number}
    parts = pr_url.rstrip("/").split("/")
    owner, repo, pr_number = parts[-4], parts[-3], int(parts[-1])

    log.info("auto_merge_starting", owner=owner, repo=repo, pr=pr_number)

    strategy = MergeStrategy(merge_strategy)
    merger = AutoMerge(github, strategy=strategy)

    try:
        merge_result = await merger.merge_when_ready(owner, repo, pr_number)
        result["merged"] = merge_result.merged
        result["merge_sha"] = merge_result.sha
        result["merge_message"] = merge_result.message
        log.info("auto_merge_done", merged=merge_result.merged, sha=merge_result.sha)
    except Exception as exc:
        result["merged"] = False
        result["merge_error"] = str(exc)
        log.error("auto_merge_failed", error=str(exc))

    return result


from core.session_poller import SessionPoller, store_activity


async def _poll_until_done(
    jules: JulesClient,
    db: Database,
    session_id: str,
    task_id: str | None,
) -> dict:
    last_state = None

    async def on_transition(session, activities):
        nonlocal last_state
        # 1. Log & Store activities
        for activity in activities:
            _log_activity(activity)
            if task_id:
                await store_activity(db, task_id, session_id, activity)

        # 2. Check state transitions and notify
        if task_id and session.state != last_state:
            try:
                from core.config_loader import build_jules_pool, load_config
                from models.workflow import AgentTask

                rows = await db.select("agent_tasks", {"id": task_id})
                if rows:
                    task_obj = AgentTask.model_validate(rows[0])
                    config = load_config()
                    pool = build_jules_pool(config)
                    store = ContextStore(db)

                    if session.state == SessionState.COMPLETED:
                        pr_url = ""
                        for output in session.outputs:
                            if output.pull_request:
                                pr_url = output.pull_request.url
                        from core.orchestrator_relay import notify_orchestrator
                        await notify_orchestrator(pool, store, task_obj, "completed", pr_url=pr_url)
                    elif session.state == SessionState.FAILED:
                        from core.orchestrator_relay import notify_orchestrator
                        await notify_orchestrator(pool, store, task_obj, "failed", summary="Jules session failed")
                    elif session.state == SessionState.AWAITING_USER_FEEDBACK:
                        from core.orchestrator_relay import notify_orchestrator, relay_worker_feedback
                        await notify_orchestrator(pool, store, task_obj, "awaiting_user_feedback", summary="Worker session needs feedback")
                        await relay_worker_feedback(pool, store, jules, session_id, task_obj)
                    elif session.state == SessionState.AWAITING_PLAN_APPROVAL:
                        from core.orchestrator_relay import notify_orchestrator
                        await notify_orchestrator(pool, store, task_obj, "awaiting_plan_approval", summary="Session is awaiting plan approval")
                        try:
                            await db.update("agent_tasks", {"status": "awaiting_plan_approval"}, {"id": task_id})
                        except Exception:
                            pass
                    elif session.state == SessionState.PAUSED:
                        from core.orchestrator_relay import notify_orchestrator
                        await notify_orchestrator(pool, store, task_obj, "paused", summary="Worker session paused")

                    await pool.close_all()
            except Exception as e:
                log.warning("session_runner_notification_failed", error=str(e))
            last_state = session.state

    poller = SessionPoller(jules, session_id, on_transition)
    try:
        terminal_session = await poller.poll()
    except TimeoutError:
        return {"session_id": session_id, "status": "timeout", "pr_url": ""}

    if terminal_session.state == SessionState.COMPLETED:
        res = _build_result(terminal_session, "completed")
        if task_id and res.get("pr_url"):
            try:
                from core.config_loader import build_jules_pool, load_config
                from core.context_store import ContextStore
                from core.qa_reviewer import run_qa_review_for_task
                from models.workflow import AgentTask

                rows = await db.select("agent_tasks", {"id": task_id})
                if rows:
                    task_obj = AgentTask.model_validate(rows[0])
                    config = load_config()
                    pool = build_jules_pool(config)
                    store = ContextStore(db)

                    await run_qa_review_for_task(pool, store, task_obj, res["pr_url"])
                    await pool.close_all()
            except Exception as e:
                log.warning("failed_to_trigger_qa_in_session_runner", error=str(e))
        return res

    if terminal_session.state == SessionState.FAILED:
        return _build_result(terminal_session, "failed")

    if terminal_session.state == SessionState.PAUSED:
        return _build_result(terminal_session, "paused")

    return _build_result(terminal_session, "unknown")


def _build_result(session, status: str) -> dict:
    pr_url = ""
    for output in session.outputs:
        if output.pull_request:
            pr_url = output.pull_request.url
            break

    return {
        "session_id": session.id,
        "status": status,
        "state": session.state,
        "title": session.title,
        "pr_url": pr_url,
        "url": session.url,
    }


def _log_activity(activity) -> None:
    parts = [f"[{activity.originator}]"]
    if activity.description:
        parts.append(activity.description)

    if activity.progress_updated:
        parts.append(f">> {activity.progress_updated.title}")

    if activity.agent_messaged:
        msg = activity.agent_messaged.agent_message
        parts.append(msg[:200] if len(msg) > 200 else msg)

    if activity.plan_generated and activity.plan_generated.plan:
        steps = activity.plan_generated.plan.steps
        parts.append(f"Plan with {len(steps)} steps")
        for step in steps:
            parts.append(f"  - {step.title}")

    if activity.session_failed:
        parts.append(f"FAILED: {activity.session_failed.reason}")

    log.info("activity", detail=" | ".join(parts))
