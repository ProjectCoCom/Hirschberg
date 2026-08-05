"""
Summary: Shared adaptive polling engine.

What it does: Centralizes polling for both tasks and standalone sessions using adaptive backoff and jitter.

How it fits in: Direct replacement of scattered thread-loops.
"""



from __future__ import annotations

import asyncio
import random
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import structlog

from clients.database import Database
from clients.jules import JulesClient
from models.jules import Activity, Session, SessionState

log = structlog.get_logger()


async def store_activity(db: Database, task_id: str, session_id: str, activity: Activity) -> None:
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
            "raw_data": activity.model_dump(mode="json"),
            "created_at": activity.create_time.isoformat() if activity.create_time else datetime.now(UTC).isoformat(),
        })
    except Exception as exc:
        log.warning("store_activity_failed", error=str(exc))


class SessionPoller:
    """
    A unified, highly-efficient session polling engine with adaptive backoff and jitter.
    Fires the registered on_transition callback when state transitions or new activities arrive.
    """
    def __init__(
        self,
        jules: JulesClient,
        session_id: str,
        on_transition: Callable[[Session, list[Activity]], Any],
        initial_interval: float = 2.0,
        multiplier: float = 1.5,
        max_interval: float = 30.0,
        timeout: float = 1800.0,
    ) -> None:
        self.jules = jules
        self.session_id = session_id
        self.on_transition = on_transition
        self.initial_interval = initial_interval
        self.multiplier = multiplier
        self.max_interval = max_interval
        self.timeout = timeout

    async def poll(self) -> Session:
        elapsed = 0.0
        interval = self.initial_interval
        last_activity_time: str | None = None
        last_state: SessionState | None = None

        while elapsed < self.timeout:
            session = await self.jules.get_session(self.session_id)
            log.info("session_poll", session_id=self.session_id, state=session.state)

            try:
                activities = await self.jules.list_activities(self.session_id, since=last_activity_time)
            except Exception:
                activities = []

            for act in activities:
                if act.create_time:
                    last_activity_time = act.create_time.isoformat()

            if session.state != last_state or activities:
                if asyncio.iscoroutinefunction(self.on_transition):
                    await self.on_transition(session, activities)
                else:
                    self.on_transition(session, activities)
                last_state = session.state

            if session.state in (SessionState.COMPLETED, SessionState.FAILED, SessionState.PAUSED):
                return session

            sleep_time = min(interval, self.max_interval)
            # Add small random jitter (+/- 10%)
            sleep_time = sleep_time * random.uniform(0.9, 1.1)

            await asyncio.sleep(sleep_time)
            elapsed += sleep_time
            interval *= self.multiplier

        raise TimeoutError("Session timed out")
