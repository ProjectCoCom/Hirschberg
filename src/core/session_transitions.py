"""
Summary: Python logic module 'Session Transitions'.

What it does: Provides backend utility operations and core logical helper interfaces for 'Session Transitions'.

How it fits in: Imported and utilized by surrounding backend structures.
"""


from __future__ import annotations

from typing import Any
import structlog

from core.account_pool import AccountPool
from core.context_store import ContextStore
from core.session_poller import store_activity
from models.workflow import AgentTask
from models.jules import SessionState

log = structlog.get_logger()


async def handle_session_transition(
    pool: AccountPool,
    store: ContextStore,
    client: Any,
    session: Any,
    activities: list[Any],
    task: AgentTask,
    last_state: SessionState | None,
) -> SessionState | None:
    """Processes session activities and checks state transitions to notify the orchestrator or handle feedback."""
    for activity in activities:
        try:
            await store_activity(store._db, str(task.id), session.id, activity)
        except Exception as e:
            log.warning("failed_to_store_activity", task_id=str(task.id), error=str(e))

    if session.state != last_state:
        try:
            if session.state == SessionState.COMPLETED:
                pr_url = ""
                for output in session.outputs:
                    if output.pull_request:
                        pr_url = output.pull_request.url
                from core.orchestrator_relay import notify_orchestrator
                await notify_orchestrator(pool, store, task, "completed", pr_url=pr_url)
            elif session.state == SessionState.FAILED:
                from core.orchestrator_relay import notify_orchestrator
                await notify_orchestrator(pool, store, task, "failed", summary="Jules session failed")
            elif session.state == SessionState.AWAITING_USER_FEEDBACK:
                from core.orchestrator_relay import notify_orchestrator, relay_worker_feedback
                await notify_orchestrator(pool, store, task, "awaiting_user_feedback", summary="Worker session needs feedback")
                await relay_worker_feedback(pool, store, client, session.id, task)
            elif session.state == SessionState.AWAITING_PLAN_APPROVAL:
                from core.orchestrator_relay import notify_orchestrator
                await notify_orchestrator(pool, store, task, "awaiting_plan_approval", summary="Session is awaiting plan approval")
                try:
                    task.status = "awaiting_plan_approval"
                    await store.save_task_state(task.id, task.model_dump(mode="json"))
                except Exception:
                    pass
            elif session.state == SessionState.PAUSED:
                from core.orchestrator_relay import notify_orchestrator
                await notify_orchestrator(pool, store, task, "paused", summary="Worker session paused")
        except Exception as e:
            log.warning("session_transition_notification_failed", task_id=str(task.id), error=str(e))

        return session.state

    return last_state
