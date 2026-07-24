from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import structlog

from clients.jules import JulesClient
from clients.github import GitHubClient
from clients.database import Database
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


async def _poll_until_done(
    jules: JulesClient,
    db: Database,
    session_id: str,
    task_id: str | None,
) -> dict:
    last_activity_time: str | None = None
    elapsed = 0

    while elapsed < SESSION_TIMEOUT:
        session = await jules.get_session(session_id)
        log.info("session_poll", session_id=session_id, state=session.state)

        try:
            activities = await jules.list_activities(session_id, since=last_activity_time)
        except Exception:
            activities = []

        for activity in activities:
            _log_activity(activity)
            if task_id:
                await _store_activity(db, task_id, session_id, activity)
            if activity.create_time:
                last_activity_time = activity.create_time.isoformat()

        if session.state == SessionState.COMPLETED:
            return _build_result(session, "completed")

        if session.state == SessionState.FAILED:
            return _build_result(session, "failed")

        if session.state == SessionState.PAUSED:
            return _build_result(session, "paused")

        await asyncio.sleep(POLL_INTERVAL)
        elapsed += POLL_INTERVAL

    return {"session_id": session_id, "status": "timeout", "pr_url": ""}


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


async def _store_activity(db: Database, task_id: str, session_id: str, activity) -> None:
    activity_type = ""
    if activity.plan_generated:
        activity_type = "plan_generated"
    elif activity.plan_approved:
        activity_type = "plan_approved"
    elif activity.user_messaged:
        activity_type = "user_messaged"
    elif activity.agent_messaged:
        activity_type = "agent_messaged"
    elif activity.progress_updated:
        activity_type = "progress_updated"
    elif activity.session_completed:
        activity_type = "session_completed"
    elif activity.session_failed:
        activity_type = "session_failed"

    try:
        await db.upsert("session_activities", {
            "task_id": task_id,
            "session_id": session_id,
            "activity_id": activity.id,
            "originator": activity.originator,
            "description": activity.description,
            "activity_type": activity_type,
            "raw_data": {},
            "created_at": activity.create_time.isoformat() if activity.create_time else datetime.now(timezone.utc).isoformat(),
        })
    except Exception as exc:
        log.warning("store_activity_failed", error=str(exc))
