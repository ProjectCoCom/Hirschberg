"""
Summary: Feedback relay loop between workers and orchestrators.

What it does: Coordinates multi-turn message exchanges when a worker session requires interactive feedback.

How it fits in: Used by 'src/core/coordinator.py'.
"""



from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import structlog

from clients.jules import JulesClient
from core.account_pool import AccountPool
from core.context_store import ContextStore
from models.workflow import AgentTask

log = structlog.get_logger()

_orchestrator_locks: dict[str, asyncio.Lock] = {}


def get_orchestrator_lock(orchestrator_id: str) -> asyncio.Lock:
    if orchestrator_id not in _orchestrator_locks:
        _orchestrator_locks[orchestrator_id] = asyncio.Lock()
    return _orchestrator_locks[orchestrator_id]


async def notify_orchestrator(
    pool: AccountPool,
    store: ContextStore,
    task: AgentTask,
    status: str,
    summary: str = "",
    pr_url: str = "",
) -> None:
    """Delivers task state transition notifications to the standing orchestrator session."""
    orchestrator_id = await store.get_task_orchestrator(task.id)
    if not orchestrator_id:
        return  # Notification is additive; preserve static path behavior

    try:
        client = await pool.get_client_for_session(orchestrator_id, store)
    except Exception as e:
        log.warning("failed_to_get_client_for_orchestrator_notification", orchestrator_id=orchestrator_id, error=str(e))
        return

    # Serialize notification turns per orchestrator
    lock = get_orchestrator_lock(orchestrator_id)
    async with lock:
        prompt = (
            f"[NOTIFICATION] Tracked task state transition:\n"
            f"- Task ID: {task.id}\n"
            f"- Description: {task.prompt}\n"
            f"- Status: {status.upper()}\n"
        )
        if pr_url:
            prompt += f"- PR URL: {pr_url}\n"
        if summary:
            prompt += f"- Summary: {summary}\n"

        try:
            await client.send_message(orchestrator_id, prompt)
            log.info("notified_orchestrator", orchestrator_id=orchestrator_id, task_id=str(task.id), status=status)
        except Exception as e:
            log.warning("failed_to_notify_orchestrator", error=str(e))


async def relay_worker_feedback(
    pool: AccountPool,
    store: ContextStore,
    worker_client: JulesClient,
    worker_session_id: str,
    task: AgentTask,
) -> None:
    """Relays worker session questions to the standing orchestrator and returns the reply."""
    orchestrator_id = await store.get_task_orchestrator(task.id)
    if not orchestrator_id:
        return

    try:
        orchestrator_client = await pool.get_client_for_session(orchestrator_id, store)
    except Exception as e:
        log.warning("failed_to_get_client_for_worker_feedback", orchestrator_id=orchestrator_id, error=str(e))
        return

    # Serialize turns per orchestrator
    lock = get_orchestrator_lock(orchestrator_id)
    async with lock:
        # 1. Fetch latest activities on the worker session to find the question
        try:
            worker_acts = await worker_client.list_activities(worker_session_id, page_size=10)
            question = "No question found."
            for act in reversed(worker_acts):
                if act.agent_messaged and act.agent_messaged.agent_message:
                    question = act.agent_messaged.agent_message
                    break
                elif act.description:
                    question = act.description
                    break
        except Exception:
            question = "Session is awaiting user feedback."

        # 2. Send the question to the orchestrator session
        msg_to_orch = (
            f"[FEEDBACK_REQUEST] Task '{task.prompt}' (ID: {task.id}) is waiting for input:\n"
            f"\"{question}\"\n\n"
            f"Please reply with your instructions/answers for this task."
        )
        try:
            await orchestrator_client.send_message(orchestrator_id, msg_to_orch)
            log.info("sent_feedback_request_to_orchestrator", orchestrator_id=orchestrator_id, task_id=str(task.id))
        except Exception as e:
            log.warning("failed_to_send_feedback_request", error=str(e))
            return

        # 3. Poll the orchestrator session specifically for a new agentMessaged activity after start_time with timeout
        start_time = datetime.now(UTC)
        reply = None

        async def poll_for_reply():
            nonlocal reply
            while not reply:
                await asyncio.sleep(5)
                try:
                    orch_acts = await orchestrator_client.list_activities(orchestrator_id, page_size=10)
                    for act in orch_acts:
                        if act.create_time and act.create_time >= start_time:
                            if act.agent_messaged and act.agent_messaged.agent_message:
                                reply = act.agent_messaged.agent_message
                                return
                except Exception as e:
                    log.warning("error_polling_orchestrator_reply", error=str(e))

        from config import load_settings
        timeout = getattr(load_settings(), "feedback_timeout", 300.0)
        try:
            await asyncio.wait_for(poll_for_reply(), timeout=timeout)
        except asyncio.TimeoutError:
            log.warning("relay_worker_feedback_timed_out", orchestrator_id=orchestrator_id, task_id=str(task.id))
            # Mark the task state to reflect "awaiting feedback timed out"
            task.status = "failed"
            task.error = "Awaiting feedback timed out"
            await store.save_task_state(task.id, task.model_dump(mode="json"))
            return

        # 4. Relay the reply back to the worker session
        try:
            await worker_client.send_message(worker_session_id, reply)
            log.info("relayed_feedback_to_worker", worker_id=worker_session_id, reply=reply[:100])
        except Exception as e:
            log.warning("failed_to_relay_feedback_to_worker", error=str(e))
