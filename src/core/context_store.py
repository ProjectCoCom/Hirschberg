"""
Context store for tracking task dependencies.

Responsibilities:
- Batch-queries dependency context messages in a single query to maintain scalable context forwarding.

Coupling:
- Feeds context into 'src/core/prompt_builder.py'.
"""


from __future__ import annotations

from uuid import UUID

import structlog

from clients.database import Database

log = structlog.get_logger()

MAX_CONTEXT_CHARS = 4000


class ContextStore:
    def __init__(self, db: Database) -> None:
        self._db = db

    async def save_task_state(self, task_id: UUID, state: dict) -> None:
        await self._db.upsert("agent_tasks", {"id": str(task_id), **state})

    async def get_task_state(self, task_id: UUID) -> dict:
        rows = await self._db.select("agent_tasks", filters={"id": str(task_id)})
        return rows[0] if rows else {}

    async def get_task_by_session(self, session_id: str) -> dict:
        rows = await self._db.select("agent_tasks", filters={"session_id": session_id})
        return rows[0] if rows else {}

    async def get_orchestrator_session(self, session_id: str) -> dict:
        rows = await self._db.select("orchestrator_sessions", filters={"session_id": session_id})
        return rows[0] if rows else {}

    async def save_task_orchestrator(self, task_id: UUID, orchestrator_session_id: str) -> None:
        await self._db.update("agent_tasks", {"orchestrator_session_id": orchestrator_session_id}, {"id": str(task_id)})

    async def get_task_orchestrator(self, task_id: UUID) -> str | None:
        rows = await self._db.select("agent_tasks", filters={"id": str(task_id)})
        return rows[0].get("orchestrator_session_id") if rows else None

    async def save_result(self, task_id: UUID, result: dict) -> None:
        await self._db.upsert(
            "context_messages",
            {
                "task_id": str(task_id),
                "context": _trim_context(result),
            },
        )

    async def get_dependency_context(self, dep_task_ids: list[UUID]) -> list[dict]:
        if not dep_task_ids:
            return []

        # Batch-fetch all context_messages rows with a single query
        tid_strs = [str(tid) for tid in dep_task_ids]
        rows = await self._db.select(
            "context_messages", filters={"task_id": tid_strs}
        )

        # Build a lookup map of task_id string to context dict
        context_by_tid = {r["task_id"]: r.get("context", {}) for r in rows if r.get("task_id")}

        # Preserve original dep_task_ids order, skipping any missing rows
        results = []
        for tid in dep_task_ids:
            tid_str = str(tid)
            if tid_str in context_by_tid:
                results.append(context_by_tid[tid_str])
        return results

    async def publish_message(
        self, from_task: UUID, to_task: UUID, message: dict
    ) -> None:
        await self._db.insert(
            "context_messages",
            {
                "from_task_id": str(from_task),
                "to_task_id": str(to_task),
                "message": message,
            },
        )

    async def get_messages_for_task(self, task_id: UUID) -> list[dict]:
        return await self._db.select(
            "context_messages", filters={"to_task_id": str(task_id)}
        )

    async def save_workflow_integration_branch(self, workflow_id: UUID, integration_branch: str) -> None:
        await self._db.update("workflows", {"integration_branch": integration_branch}, {"id": str(workflow_id)})

    async def get_workflow_state(self, workflow_id: UUID) -> dict:
        rows = await self._db.select("workflows", filters={"id": str(workflow_id)})
        return rows[0] if rows else {}

    async def get_workflow_by_branch(self, branch: str) -> dict:
        rows = await self._db.select("workflows", filters={"integration_branch": branch})
        return rows[0] if rows else {}

    async def insert_task(self, task_data: dict) -> dict:
        return await self._db.insert("agent_tasks", task_data)

    async def update_task(self, task_id: UUID, task_data: dict) -> list[dict]:
        return await self._db.update("agent_tasks", task_data, filters={"id": str(task_id)})

    async def get_tasks_by_branch(self, repo_owner: str, repo_name: str, branch: str) -> list[dict]:
        return await self._db.select(
            "agent_tasks",
            filters={"repo_owner": repo_owner, "repo_name": repo_name, "branch": branch}
        )


def _trim_context(result: dict) -> dict:
    # Jules prompts have size limits; truncate large fields to stay under budget
    trimmed = dict(result)
    for key in ("activities_summary", "summary"):
        if key in trimmed and len(str(trimmed[key])) > MAX_CONTEXT_CHARS:
            trimmed[key] = str(trimmed[key])[:MAX_CONTEXT_CHARS] + "...[trimmed]"
    return trimmed
