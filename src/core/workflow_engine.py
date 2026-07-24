from __future__ import annotations

import asyncio
from uuid import UUID

import structlog

from core.coordinator import AgentCoordinator
from core.context_store import ContextStore
from exceptions import WorkflowValidationError
from models.workflow import AgentTask, TaskStatus, Workflow, WorkflowStatus

log = structlog.get_logger()


class WorkflowEngine:
    def __init__(
        self, coordinator: AgentCoordinator, store: ContextStore
    ) -> None:
        self._coordinator = coordinator
        self._store = store

    def validate(self, workflow: Workflow) -> None:
        task_ids = {t.id for t in workflow.tasks}
        for task in workflow.tasks:
            for dep in task.depends_on:
                if dep not in task_ids:
                    raise WorkflowValidationError(
                        f"Task {task.id} depends on unknown task {dep}"
                    )
        if self._has_cycle(workflow.tasks):
            raise WorkflowValidationError("Workflow contains a dependency cycle")

    def _has_cycle(self, tasks: list[AgentTask]) -> bool:
        adjacency: dict[UUID, list[UUID]] = {t.id: list(t.depends_on) for t in tasks}
        visited: set[UUID] = set()
        in_stack: set[UUID] = set()

        def dfs(node: UUID) -> bool:
            visited.add(node)
            in_stack.add(node)
            for neighbor in adjacency.get(node, []):
                if neighbor in in_stack:
                    return True
                if neighbor not in visited and dfs(neighbor):
                    return True
            in_stack.discard(node)
            return False

        return any(dfs(t_id) for t_id in adjacency if t_id not in visited)

    async def run(self, workflow: Workflow) -> Workflow:
        self.validate(workflow)
        workflow.status = WorkflowStatus.RUNNING

        pending: dict[UUID, AgentTask] = {t.id: t for t in workflow.tasks}
        running: dict[UUID, asyncio.Task] = {}
        completed: set[UUID] = set()
        has_failures = False

        try:
            while pending or running:
                ready = self._find_ready_tasks(pending, completed)
                for task in ready:
                    del pending[task.id]
                    coro = self._coordinator.run_task(task)
                    running[task.id] = asyncio.create_task(coro)

                if not running:
                    break

                done, _ = await asyncio.wait(
                    running.values(), return_when=asyncio.FIRST_COMPLETED
                )

                for future in done:
                    result: AgentTask = future.result()
                    running.pop(result.id, None)

                    if result.status == TaskStatus.FAILED:
                        has_failures = True
                        # Find all transitive dependents (full closure propagation)
                        dependents = _get_transitive_dependents(result.id, workflow.tasks)
                        for dep_id in dependents:
                            if dep_id in pending:
                                dep_task = pending[dep_id]
                                dep_task.status = TaskStatus.CANCELLED
                                dep_task.error = f"Dependency failed: parent task {result.id} failed."
                                await self._store.save_task_state(dep_id, dep_task.model_dump(mode="json"))
                                del pending[dep_id]
                            if dep_id in running:
                                running[dep_id].cancel()
                    else:
                        completed.add(result.id)

            if has_failures:
                workflow.status = WorkflowStatus.FAILED
            else:
                workflow.status = WorkflowStatus.COMPLETED

        except Exception as exc:
            workflow.status = WorkflowStatus.FAILED
            log.error("workflow_failed", workflow_id=str(workflow.id), error=str(exc))
            await self._cancel_remaining(running)

        return workflow

    def _find_ready_tasks(
        self, pending: dict[UUID, AgentTask], completed: set[UUID]
    ) -> list[AgentTask]:
        return [
            task for task in pending.values()
            if all(dep in completed for dep in task.depends_on)
        ]

    async def _cancel_remaining(self, running: dict[UUID, asyncio.Task]) -> None:
        for task in running.values():
            task.cancel()
        if running:
            await asyncio.gather(*running.values(), return_exceptions=True)
        running.clear()


def _get_transitive_dependents(failed_task_id: UUID, tasks: list[AgentTask]) -> set[UUID]:
    dependents = set()
    queue = [failed_task_id]
    while queue:
        current = queue.pop(0)
        for t in tasks:
            if current in t.depends_on and t.id not in dependents:
                dependents.add(t.id)
                queue.append(t.id)
    return dependents
