"""
Summary: Session rate and limit guard.

What it does: Enforces max durations and active session counts to avoid runaway loops.

How it fits in: Integrates with session execution loops.
"""



from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime

import structlog

log = structlog.get_logger()


@dataclass
class SessionSlot:
    pipeline_id: str
    repo: str
    task_id: str
    acquired_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class SessionLimiter:
    """Global concurrency gate shared across all pipelines.

    Prevents multiple concurrent pipelines from collectively exceeding
    the Jules concurrent session limit (e.g. 60 for Ultra).
    """

    def __init__(self, max_concurrent: int = 60) -> None:
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._max = max_concurrent
        self._active: list[SessionSlot] = []
        self._lock = asyncio.Lock()

    @property
    def active_count(self) -> int:
        return len(self._active)

    @property
    def available(self) -> int:
        return self._max - len(self._active)

    async def acquire(self, pipeline_id: str, repo: str, task_id: str) -> bool:
        acquired = await asyncio.wait_for(self._semaphore.acquire(), timeout=300)
        if not acquired:
            return False
        async with self._lock:
            self._active.append(SessionSlot(
                pipeline_id=pipeline_id, repo=repo, task_id=task_id,
            ))
        log.info(
            "session_slot_acquired",
            pipeline=pipeline_id, repo=repo, task=task_id,
            active=self.active_count, max=self._max,
        )
        return True

    async def release(self, task_id: str) -> None:
        async with self._lock:
            self._active = [s for s in self._active if s.task_id != task_id]
        self._semaphore.release()
        log.info("session_slot_released", task=task_id, active=self.active_count)

    def status(self) -> dict:
        return {
            "max_concurrent": self._max,
            "active": self.active_count,
            "available": self.available,
            "slots": [
                {"pipeline": s.pipeline_id, "repo": s.repo, "task": s.task_id}
                for s in self._active
            ],
        }


# Singleton shared across all pipelines
_limiter: SessionLimiter | None = None


def get_session_limiter(max_concurrent: int = 60) -> SessionLimiter:
    global _limiter
    if _limiter is None or _limiter._max != max_concurrent:
        _limiter = SessionLimiter(max_concurrent)
    return _limiter
