from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable
from uuid import UUID

import structlog

from clients.database import Database

log = structlog.get_logger()

# Sessions with no activity for this long are considered stale
STALE_THRESHOLD_SECONDS = 600


class MonitorConfig:
    def __init__(
        self,
        poll_interval: int = 15,
        stale_threshold: int = STALE_THRESHOLD_SECONDS,
        max_cached_activities: int = 200,
    ) -> None:
        self.poll_interval = poll_interval
        self.stale_threshold = stale_threshold
        self.max_cached_activities = max_cached_activities


class Tracker:
    def __init__(
        self, db: Database, config: MonitorConfig | None = None
    ) -> None:
        self._db = db
        self._config = config or MonitorConfig()
        self._channels: list[str] = []
        self._activity_cache: list[dict] = []
        self._last_fetch: datetime | None = None

    @property
    def is_stale(self) -> bool:
        if not self._last_fetch:
            return True
        elapsed = (datetime.now(timezone.utc) - self._last_fetch).total_seconds()
        return elapsed > self._config.stale_threshold

    async def get_active_tasks(self) -> list[dict]:
        return await self._db.select(
            "agent_tasks",
            filters={"status": "running"},
        )

    async def get_stale_tasks(self) -> list[dict]:
        running = await self.get_active_tasks()
        stale = []
        now = datetime.now(timezone.utc)
        for task in running:
            updated = task.get("updated_at") or task.get("created_at")
            if not updated:
                stale.append(task)
                continue
            age = (now - datetime.fromisoformat(updated)).total_seconds()
            if age > self._config.stale_threshold:
                stale.append(task)
        return stale

    async def get_workflow_status(self, workflow_id: UUID) -> dict:
        tasks = await self._db.select(
            "agent_tasks",
            filters={"workflow_id": str(workflow_id)},
        )
        by_status: dict[str, int] = {}
        for t in tasks:
            status = t.get("status", "unknown")
            by_status[status] = by_status.get(status, 0) + 1

        return {
            "workflow_id": str(workflow_id),
            "total_tasks": len(tasks),
            "by_status": by_status,
            "tasks": tasks,
        }

    async def get_recent_activities(self, limit: int = 50) -> list[dict]:
        # self._activity_cache is vestigial (nothing else reads or writes to it),
        # but to keep signatures and attributes completely compatible we populate
        # it with the fetched rows. We push ORDER BY and LIMIT into SQLite.
        rows = await self._db.select(
            "session_activities",
            order_by="created_at DESC",
            limit=limit,
        )
        self._activity_cache = rows
        self._last_fetch = datetime.now(timezone.utc)
        return rows

    async def subscribe_task_updates(
        self, callback: Callable[[dict], None]
    ) -> None:
        sub_id = self._db.subscribe(
            "agent_tasks",
            "*",
            callback,
        )
        self._channels.append(sub_id)
        log.info("subscribed", table="agent_tasks")

    async def subscribe_activity_updates(
        self, callback: Callable[[dict], None]
    ) -> None:
        sub_id = self._db.subscribe(
            "session_activities",
            "INSERT",
            callback,
        )
        self._channels.append(sub_id)
        log.info("subscribed", table="session_activities")

    async def subscribe_workflow_tasks(
        self, workflow_id: UUID, callback: Callable[[dict], None]
    ) -> None:
        sub_id = self._db.subscribe(
            "agent_tasks",
            "*",
            callback,
            filter_fn=lambda payload: payload.get("new", {}).get("workflow_id") == str(workflow_id),
        )
        self._channels.append(sub_id)
        log.info("subscribed", table="agent_tasks", workflow_id=str(workflow_id))

    async def unsubscribe_all(self) -> None:
        for sub_id in self._channels:
            self._db.unsubscribe(sub_id)
        self._channels.clear()
        log.info("unsubscribed_all")
