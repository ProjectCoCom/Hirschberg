"""
Task coordinator for running multi-step agent workflows.

Responsibilities:
- Coordinates task runs, creates git branches, builds prompts, handles pool exhaustions, and notifies orchestrators.

Coupling:
- Heart of task-dispatch system; couples with WorkflowEngine.
"""


from __future__ import annotations

import asyncio
from uuid import UUID

import structlog

from core.account_pool import AccountPool
from core.context_store import ContextStore
from models.jules import SessionState
from models.workflow import AgentTask, TaskStatus

log = structlog.get_logger()

POLL_INTERVAL = 30
SESSION_TIMEOUT = 1800


class AgentCoordinator:
    """Coordinates multi-step agent workflows and task execution.
    
    This class manages the lifecycle of agent tasks including:
    - Waiting for task completion via async events
    - Managing task dependencies
    - Running individual tasks with proper context setup
    
    Attributes:
        _pool: Account pool for managing API credentials
        _store: Context store for persisting task state
        _completion_events: Map of task IDs to completion events
    """
    
    def __init__(
        self, pool: AccountPool, store: ContextStore
    ) -> None:
        """Initialize the coordinator with pool and store.
        
        Args:
            pool: AccountPool instance for API credential management
            store: ContextStore instance for state persistence
        """
        self._pool = pool
        self._store = store
        self._completion_events: dict[UUID, asyncio.Event] = {}

    def _get_or_create_event(self, task_id: UUID) -> asyncio.Event:
        """Get or create a completion event for a task.
        
        Args:
            task_id: The unique identifier of the task
            
        Returns:
            An asyncio.Event for signaling task completion
        """
        if task_id not in self._completion_events:
            self._completion_events[task_id] = asyncio.Event()
        return self._completion_events[task_id]

    async def wait_for_task(self, task_id: UUID, timeout: float = SESSION_TIMEOUT) -> dict:
        """Wait for a task to complete with timeout.
        
        Args:
            task_id: The unique identifier of the task to wait for
            timeout: Maximum time to wait in seconds (default: SESSION_TIMEOUT)
            
        Returns:
            The final task state from the context store
            
        Raises:
            asyncio.TimeoutError: If the task doesn't complete within timeout
        """
        event = self._get_or_create_event(task_id)
        await asyncio.wait_for(event.wait(), timeout=timeout)
        return await self._store.get_task_state(task_id)

    async def wait_for_dependencies(self, task: AgentTask) -> list[dict]:
        """Wait for all dependency tasks to complete.
        
        Args:
            task: The task whose dependencies need to be waited on
            
        Returns:
            List of dependency task results
        """
        if not task.depends_on:
            return []

        results = await asyncio.gather(
            *[self.wait_for_task(dep_id) for dep_id in task.depends_on]
        )
        return list(results)

    async def run_task(self, task: AgentTask) -> AgentTask:
        """Execute a single agent task.
        
        Args:
            task: The task to execute
            
        Returns:
            The updated task with new status
        """
        source = f"sources/github/{task.repo_owner}/{task.repo_name}"
        from config import load_settings
        from core.account_pool import AccountRole
        settings = load_settings()
        max_depth = getattr(settings, "max_delegation_depth", 0)

        role_to_acquire = AccountRole.WORKER

        # Check if assign_to targets an orchestrator account and max delegation depth allows it
        is_orchestrator_assignee = False
        if task.assign_to:
            for acc in self._pool._accounts:
                if (acc.name == task.assign_to or acc.label == task.assign_to) and acc.role == AccountRole.ORCHESTRATOR:
                    is_orchestrator_assignee = True
                    break

        if is_orchestrator_assignee and max_depth > 0:
            # Resolve delegating orchestrator task ID from orchestrator_session_id
            delegating_task_id = None
            if task.orchestrator_session_id:
                try:
                    orch_row = await self._store.get_task_by_session(task.orchestrator_session_id)
                    if orch_row:
                        delegating_task_id = orch_row["id"]
                except Exception as e:
                    log.error("failed_to_resolve_delegating_task", error=str(e))
                    pass

            # Calculate current depth by climbing parent_task_id tree
            current_depth = 0
            curr_parent_id = delegating_task_id
            while curr_parent_id:
                try:
                    parent_row = await self._store.get_task_state(curr_parent_id)
                    if parent_row and parent_row.get("parent_task_id"):
                        curr_parent_id = parent_row["parent_task_id"]
                        current_depth += 1
                    else:
                        break
                except Exception as e:
                    log.error("failed_to_climb_parent_tree", error=str(e), task_id=curr_parent_id)
                    break

            if current_depth < max_depth:
                role_to_acquire = AccountRole.ORCHESTRATOR
                task.prompt = f"you are responsible for this subtree of the goal: {task.prompt}"
                if delegating_task_id:
                    task.parent_task_id = (
                        UUID(delegating_task_id)
                        if isinstance(delegating_task_id, str)
                        else delegating_task_id
                    )

        from exceptions import AccountPoolExhaustedError
        retries = 3
        backoff = 2
        account = None
        for attempt in range(retries):
            try:
                account = self._pool.acquire(source, role=role_to_acquire, assign_to=task.assign_to)
                break
            except AccountPoolExhaustedError as exc:
                if attempt == retries - 1:
                    raise exc
                log.info("task_waiting_on_capacity", task_id=str(task.id), attempt=attempt+1)
                try:
                    from core.orchestrator_relay import notify_orchestrator
                    await notify_orchestrator(
                        self._pool,
                        self._store,
                        task,
                        "waiting_on_capacity",
                        summary=(
                            f"Task is waiting for pool capacity "
                            f"(attempt {attempt+1}/{retries})"
                        ),
                    )
                except Exception as e:
                    log.error("failed_to_notify_waiting", error=str(e), task_id=str(task.id))
                    pass
                await asyncio.sleep(backoff)

        task.account_id = account.id
        task.status = TaskStatus.WAITING

        try:
            await self.wait_for_dependencies(task)
            task.status = TaskStatus.RUNNING

            # Dynamically create Git branch on GitHub if token is available
            from clients.github import GitHubClient
            from config import load_settings
            settings = load_settings()
            if settings.github_token:
                gh_client = GitHubClient(settings.github_token)
                try:
                    base_branch = None
                    if task.workflow_id:
                        wf_row = await self._store.get_workflow_state(task.workflow_id)
                        if wf_row:
                            base_branch = wf_row.get("integration_branch") or None

                    await gh_client.create_branch_with_base(
                        task.repo_owner, task.repo_name, task.branch, base_branch
                    )
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
        from core.session_poller import SessionPoller, store_activity
        last_state = None

        async def on_transition(session, activities):
            nonlocal last_state
            # 1. Fetching and storing session activities into the database (Step 13 gap closure)
            for activity in activities:
                await store_activity(self._store._db, str(task.id), session.id, activity)

            # 2. Check state transitions and notify
            if session.state != last_state:
                if session.state == SessionState.COMPLETED:
                    pr_url = ""
                    for output in session.outputs:
                        if output.pull_request:
                            pr_url = output.pull_request.url
                    from core.orchestrator_relay import notify_orchestrator
                    await notify_orchestrator(self._pool, self._store, task, "completed", pr_url=pr_url)
                elif session.state == SessionState.FAILED:
                    from core.orchestrator_relay import notify_orchestrator
                    await notify_orchestrator(self._pool, self._store, task, "failed", summary="Jules session failed")
                elif session.state == SessionState.AWAITING_USER_FEEDBACK:
                    from core.orchestrator_relay import notify_orchestrator, relay_worker_feedback
                    await notify_orchestrator(
                        self._pool,
                        self._store,
                        task,
                        "awaiting_user_feedback",
                        summary="Worker session needs feedback",
                    )
                    await relay_worker_feedback(self._pool, self._store, client, task.session_id, task)
                elif session.state == SessionState.AWAITING_PLAN_APPROVAL:
                    from core.orchestrator_relay import notify_orchestrator
                    await notify_orchestrator(
                        self._pool,
                        self._store,
                        task,
                        "awaiting_plan_approval",
                        summary="Session is awaiting plan approval",
                    )
                    try:
                        task.status = "awaiting_plan_approval"
                        await self._store.save_task_state(task.id, task.model_dump(mode="json"))
                    except Exception as e:
                        log.error("failed_to_save_awaiting_plan_state", error=str(e), task_id=str(task.id))
                        pass
                elif session.state == SessionState.PAUSED:
                    from core.orchestrator_relay import notify_orchestrator
                    await notify_orchestrator(self._pool, self._store, task, "paused", summary="Worker session paused")

                last_state = session.state

        poller = SessionPoller(client, task.session_id, on_transition)
        try:
            terminal_session = await poller.poll()
        except TimeoutError:
            task.status = TaskStatus.FAILED
            task.error = "Session timed out"
            return task

        if terminal_session.state == SessionState.COMPLETED:
            task.status = TaskStatus.COMPLETED
            for output in terminal_session.outputs:
                if output.pull_request:
                    task.pr_url = output.pull_request.url

            if task.pr_url:
                try:
                    from core.qa_reviewer import run_qa_review_for_task
                    await run_qa_review_for_task(self._pool, self._store, task, task.pr_url)
                except Exception as e:
                    log.warning("qa_trigger_failed", task_id=str(task.id), error=str(e))

            return task

        if terminal_session.state == SessionState.FAILED:
            task.status = TaskStatus.FAILED
            task.error = "Jules session failed"
            return task

        if terminal_session.state == SessionState.PAUSED:
            task.status = TaskStatus.FAILED
            task.error = "Jules session paused"
            return task

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
