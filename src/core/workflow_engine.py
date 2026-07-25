"""
Multi-task parallel workflow engine.

Responsibilities:
- Orchestrates parallel DAG task executions, manages integration branches, and coordinates multi-agent merges.

Coupling:
- Orchestrates coordinator, AutoMerge, and QAReviewer.
"""


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

        # 1. Multi-task workflow integration branch creation at dispatch time
        if len(workflow.tasks) > 1:
            from clients.github import GitHubClient
            from config import load_settings
            settings = load_settings()
            if settings.github_token and workflow.tasks:
                gh_client = GitHubClient(settings.github_token)
                try:
                    owner = workflow.tasks[0].repo_owner
                    repo = workflow.tasks[0].repo_name
                    base_sha = await gh_client.get_default_branch_sha(owner, repo)
                    if base_sha:
                        workflow.integration_branch = f"jat/integration-{workflow.id}"
                        await gh_client.create_branch_from_ref(owner, repo, workflow.integration_branch, base_sha)
                        # Persist integration branch on workflow in DB
                        await self._store._db.update("workflows", {"integration_branch": workflow.integration_branch}, {"id": str(workflow.id)})
                        log.info("integration_branch_created", workflow_id=str(workflow.id), branch=workflow.integration_branch)
                except Exception as e:
                    log.warning("failed_to_create_integration_branch", error=str(e))
                finally:
                    await gh_client.close()

        pending: dict[UUID, AgentTask] = {t.id: t for t in workflow.tasks}
        running: dict[UUID, asyncio.Task] = {}
        completed: set[UUID] = set()
        has_failures = False

        try:
            while pending or running:
                ready = self._find_ready_tasks(pending, completed)
                dispatched_any = False
                for task in ready:
                    role, source = self._get_task_requirements(task)
                    if self._coordinator._pool.has_capacity_for(source, role=role, assign_to=task.assign_to):
                        del pending[task.id]
                        coro = self._coordinator.run_task(task)
                        running[task.id] = asyncio.create_task(coro)
                        dispatched_any = True

                if not running:
                    if pending:
                        log.warning("pool_capacity_exhausted_deadlock", pending_count=len(pending))
                        for task_id, t in list(pending.items()):
                            t.status = TaskStatus.FAILED
                            t.error = "Pool capacity completely exhausted: no available accounts with capacity."
                            await self._store.save_task_state(task_id, t.model_dump(mode="json"))
                            del pending[task_id]
                        has_failures = True
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
                # Run the integrator review if an integration branch is set
                if workflow.integration_branch:
                    integrator_ok = await self._run_integrator_review(workflow)
                    if integrator_ok:
                        workflow.status = WorkflowStatus.COMPLETED
                    else:
                        workflow.status = WorkflowStatus.FAILED
                else:
                    workflow.status = WorkflowStatus.COMPLETED

        except Exception as exc:
            workflow.status = WorkflowStatus.FAILED
            log.error("workflow_failed", workflow_id=str(workflow.id), error=str(exc))
            await self._cancel_remaining(running)

        return workflow

    def _get_task_requirements(self, task: AgentTask) -> tuple[AccountRole, str]:
        from core.account_pool import AccountRole
        from config import load_settings
        settings = load_settings()
        max_depth = getattr(settings, "max_delegation_depth", 0)

        role_to_acquire = AccountRole.WORKER
        is_orchestrator_assignee = False
        if task.assign_to:
            for acc in self._coordinator._pool._accounts:
                if (acc.name == task.assign_to or acc.label == task.assign_to) and acc.role == AccountRole.ORCHESTRATOR:
                    is_orchestrator_assignee = True
                    break

        if is_orchestrator_assignee and max_depth > 0:
            role_to_acquire = AccountRole.ORCHESTRATOR

        source = f"sources/github/{task.repo_owner}/{task.repo_name}"
        return role_to_acquire, source

    def _find_ready_tasks(
        self, pending: dict[UUID, AgentTask], completed: set[UUID]
    ) -> list[AgentTask]:
        return [
            task for task in pending.values()
            if all(dep in completed for dep in task.depends_on)
        ]

    async def _run_integrator_review(self, workflow: Workflow) -> bool:
        """Dispatches an integrator review session, parses the final JSON verdict,
        and manages final PR, auto-merge, and branch cleanup.
        """
        from pathlib import Path
        from uuid import uuid4
        from config import load_settings
        from core.account_pool import AccountRole
        from core.qa_reviewer import extract_qa_verdict
        from core.merge_review import create_final_pr, cleanup_branches
        from core.auto_merge import AutoMerge, MergeStrategy
        from clients.github import GitHubClient

        owner = workflow.tasks[0].repo_owner
        repo = workflow.tasks[0].repo_name
        source = f"sources/github/{owner}/{repo}"
        settings = load_settings()

        log.info("integrator_review_dispatching", workflow_id=str(workflow.id), branch=workflow.integration_branch)

        # 1. Prepare contributing tasks references
        tasks_ref = []
        for i, t in enumerate(workflow.tasks):
            desc = t.prompt
            exit_crit = t.exit_criteria or "Task completed as described"
            tasks_ref.append(f"Task {i+1}: {desc}\nExit Criteria: {exit_crit}")
        tasks_context = "\n\n".join(tasks_ref)

        # 2. Load Integrator prompt template
        path = Path("prompts/integrator_reviewer.md")
        if path.exists():
            prompt_content = path.read_text(encoding="utf-8").replace("{contributing_tasks}", tasks_context)
        else:
            prompt_content = f"Identity: Integrator review.\nTasks:\n{tasks_context}"

        # 3. Acquire Integrator account
        try:
            integrator_account = self._coordinator._pool.acquire(source, role=AccountRole.INTEGRATOR)
        except Exception as e:
            log.warning("integrator_account_acquisition_failed", error=str(e))
            return False

        # 4. Insert integrator task in DB
        integrator_task_id = uuid4()
        await self._store._db.insert("agent_tasks", {
            "id": str(integrator_task_id),
            "workflow_id": str(workflow.id),
            "prompt": f"Integrator Review: {workflow.name}",
            "repo_owner": owner,
            "repo_name": repo,
            "branch": workflow.integration_branch,
            "status": "running",
            "orchestrator_session_id": workflow.tasks[0].orchestrator_session_id,
            "context": {"is_integrator_task": True},
        })

        client = self._coordinator._pool.get_client(integrator_account.id)
        parsed_verdict = None
        try:
            # 5. Create and poll integrator session
            session = await client.create_session(
                prompt=prompt_content,
                source=source,
                branch=workflow.integration_branch,
                title=f"Integrator Review: {workflow.name[:50]}",
                automation_mode="",
            )
            session_id = session.id
            await self._store._db.update("agent_tasks", {"session_id": session_id}, {"id": str(integrator_task_id)})

            deadline = asyncio.get_event_loop().time() + 1800
            from models.jules import SessionState
            while asyncio.get_event_loop().time() < deadline:
                session = await client.get_session(session_id)
                if session.state == SessionState.AWAITING_PLAN_APPROVAL:
                    await client.approve_plan(session_id)

                try:
                    acts = await client.list_activities(session_id)
                    for act in acts:
                        if act.agent_messaged and act.agent_messaged.agent_message:
                            verdict = extract_qa_verdict(act.agent_messaged.agent_message)
                            if verdict:
                                parsed_verdict = verdict
                except Exception:
                    pass

                if session.state in (SessionState.COMPLETED, SessionState.FAILED):
                    break

                await asyncio.sleep(15)

        except Exception as e:
            log.warning("integrator_session_execution_failed", error=str(e))
        finally:
            self._coordinator._pool.release(integrator_account.id)

        # 6. Fallback verdict if parsing failed
        if not parsed_verdict:
            parsed_verdict = {
                "verdict": "reject",
                "blocking_issues": [
                    {"file": "N/A", "issue": "Integrator session failed to produce a valid JSON verdict block", "severity": "blocking"}
                ],
                "summary": "Integrator execution error or missing verdict."
            }

        # 7. Update DB state
        await self._store._db.update("agent_tasks", {
            "status": "completed",
            "context": {"is_integrator_task": True, "integrator_verdict": parsed_verdict},
        }, {"id": str(integrator_task_id)})

        verdict_str = parsed_verdict.get("verdict", "").lower()
        log.info("integrator_review_completed", workflow_id=str(workflow.id), verdict=verdict_str)

        # 8. Handle approved/rejected results
        if verdict_str == "approve":
            # Open the final PR
            token = settings.github_token or ""
            pr_url = await create_final_pr(
                owner, repo, workflow.integration_branch, "main", f"JAT-AI Final PR: {workflow.name}", token
            )
            if pr_url:
                log.info("final_pr_opened", pr_url=pr_url)
                # Parse PR number
                try:
                    parts = pr_url.rstrip("/").split("/")
                    pr_number = int(parts[-1])
                    gh_client = GitHubClient(token)
                    merger = AutoMerge(gh_client, strategy=MergeStrategy.SQUASH)
                    # Trigger auto-merge loop which enforces green CI AND approved Integrator verdict
                    merge_res = await merger.merge_when_ready(owner, repo, pr_number)
                    await gh_client.close()
                    if merge_res.merged:
                        log.info("final_pr_merged", sha=merge_res.sha)
                        # Clean up individual task branches ONLY after confirmed successful merge
                        await cleanup_branches(owner, repo, [t.branch for t in workflow.tasks], token)
                        return True
                    else:
                        log.warning("final_pr_merge_failed", message=merge_res.message)
                except Exception as e:
                    log.warning("failed_to_complete_final_merge_flow", error=str(e))
            return False
        else:
            # Reject: notify responsible orchestrator
            try:
                from models.workflow import AgentTask as WorkflowAgentTask
                task_rows = await self._store._db.select("agent_tasks", {"id": str(integrator_task_id)})
                if task_rows:
                    task_obj = WorkflowAgentTask.model_validate(task_rows[0])
                    pool = self._coordinator._pool
                    store = self._store

                    issues_summary = ""
                    for issue in parsed_verdict.get("blocking_issues", []):
                        issues_summary += f"- {issue.get('file', 'unknown')}: {issue.get('issue', '')} (Severity: {issue.get('severity', 'blocking')})\n"
                    summary = f"Integrator Review Rejected:\n{issues_summary}"

                    from core.orchestrator_relay import notify_orchestrator
                    await notify_orchestrator(pool, store, task_obj, "rejected", summary=summary)
            except Exception as e:
                log.warning("failed_to_notify_orchestrator_on_integrator_rejection", error=str(e))
            return False

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
