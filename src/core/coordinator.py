from __future__ import annotations

import asyncio
from uuid import UUID

import structlog

from core.account_pool import AccountPool
from core.context_store import ContextStore
from models.workflow import AgentTask, TaskStatus
from models.jules import SessionState

log = structlog.get_logger()

POLL_INTERVAL = 30
SESSION_TIMEOUT = 1800


class AgentCoordinator:
    def __init__(
        self, pool: AccountPool, store: ContextStore
    ) -> None:
        self._pool = pool
        self._store = store
        self._completion_events: dict[UUID, asyncio.Event] = {}

    def _get_or_create_event(self, task_id: UUID) -> asyncio.Event:
        if task_id not in self._completion_events:
            self._completion_events[task_id] = asyncio.Event()
        return self._completion_events[task_id]

    async def wait_for_task(self, task_id: UUID, timeout: float = SESSION_TIMEOUT) -> dict:
        event = self._get_or_create_event(task_id)
        await asyncio.wait_for(event.wait(), timeout=timeout)
        return await self._store.get_task_state(task_id)

    async def wait_for_dependencies(self, task: AgentTask) -> list[dict]:
        if not task.depends_on:
            return []

        results = await asyncio.gather(
            *[self.wait_for_task(dep_id) for dep_id in task.depends_on]
        )
        return list(results)

    async def run_task(self, task: AgentTask) -> AgentTask:
        source = f"sources/github/{task.repo_owner}/{task.repo_name}"
        from core.account_pool import AccountRole
        account = self._pool.acquire(source, role=AccountRole.WORKER, assign_to=task.assign_to)
        task.account_id = account.id
        task.status = TaskStatus.WAITING

        try:
            dep_results = await self.wait_for_dependencies(task)
            task.status = TaskStatus.RUNNING

            # Dynamically create Git branch on GitHub if token is available
            from clients.github import GitHubClient
            from config import load_settings
            settings = load_settings()
            if settings.github_token:
                gh_client = GitHubClient(settings.github_token)
                try:
                    base_sha = await gh_client.get_default_branch_sha(task.repo_owner, task.repo_name)
                    if base_sha:
                        await gh_client.create_branch_from_ref(task.repo_owner, task.repo_name, task.branch, base_sha)
                except Exception as e:
                    log.warning("branch_creation_failed_ignored", error=str(e))
                finally:
                    await gh_client.close()

            client = self._pool.get_client(account.id)

            dep_contexts = []
            if task.depends_on:
                dep_contexts = await self._store.get_dependency_context(task.depends_on)

            from core.prompt_builder import build_session_prompt
            prompt = build_session_prompt(
                task=task.prompt,
                dependency_context=dep_contexts,
                plan_tier=account.plan,
                daily_used=account.daily_tasks_used,
                daily_limit=account.limits["daily_tasks"],
                concurrent_used=account.active_sessions,
                concurrent_limit=account.limits["concurrent"],
                account_name=account.name,
            )

            session = await client.create_session(
                prompt=prompt,
                source=source,
                branch=task.branch,
                title=task.prompt[:80],
            )
            task.session_id = session.id

            task = await self._poll_session(client, task)

        except Exception as exc:
            task.status = TaskStatus.FAILED
            task.error = str(exc)
            log.error("task_failed", task_id=str(task.id), error=str(exc))
        finally:
            self._pool.release(account.id)
            result_context = {
                "prompt": task.prompt[:200],
                "status": task.status,
                "pr_url": task.pr_url,
                "error": task.error,
            }
            await self._store.save_result(task.id, result_context)
            await self._store.save_task_state(task.id, task.model_dump(mode="json"))
            event = self._get_or_create_event(task.id)
            event.set()

        return task

    async def _poll_session(self, client, task: AgentTask) -> AgentTask:
        elapsed = 0
        while elapsed < SESSION_TIMEOUT:
            session = await client.get_session(task.session_id)

            if session.state == SessionState.COMPLETED:
                task.status = TaskStatus.COMPLETED
                for output in session.outputs:
                    if output.pull_request:
                        task.pr_url = output.pull_request.url
                return task

            if session.state == SessionState.FAILED:
                task.status = TaskStatus.FAILED
                task.error = "Jules session failed"
                return task

            terminal = {SessionState.FAILED, SessionState.COMPLETED}
            if session.state in terminal:
                return task

            await asyncio.sleep(POLL_INTERVAL)
            elapsed += POLL_INTERVAL

        task.status = TaskStatus.FAILED
        task.error = "Session timed out"
        return task


def _build_prompt_with_context(
    base_prompt: str, dep_results: list[dict], dep_contexts: list[dict]
) -> str:
    lines = [base_prompt, "", "Context from completed dependencies:"]

    for i, ctx in enumerate(dep_contexts):
        task_label = ctx.get("prompt", f"dependency {i + 1}")[:80]
        status = ctx.get("status", "unknown")
        pr_url = ctx.get("pr_url", "none")
        error = ctx.get("error", "")

        entry = f"- [{status}] {task_label}"
        if pr_url:
            entry += f" | PR: {pr_url}"
        if error:
            entry += f" | Error: {error}"
        lines.append(entry)

    # Fall back to task state if no saved context exists for some deps
    if len(dep_contexts) < len(dep_results):
        for r in dep_results[len(dep_contexts):]:
            lines.append(
                f"- {r.get('prompt', 'task')}: {r.get('status', 'unknown')}"
                f", PR: {r.get('pr_url', 'none')}"
            )

    return "\n".join(lines)
