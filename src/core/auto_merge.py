"""
Summary: Automated PR merger with checks validation.

What it does: Monitors CI status with adaptive backoff, and safely merges PRs with retry-protected API calls.

How it fits in: Uses 'src/clients/github.py'.
"""



from __future__ import annotations

import asyncio
import random
from enum import StrEnum

import structlog

from clients.github import GitHubClient
from models.github import CheckConclusion, CheckStatus, MergeResult

log = structlog.get_logger()

CHECK_INITIAL_INTERVAL = 15.0
CHECK_MULTIPLIER = 1.5
CHECK_MAX_INTERVAL = 90.0
CHECK_TIMEOUT = 600.0


class MergeStrategy(StrEnum):
    SQUASH = "squash"
    MERGE = "merge"
    REBASE = "rebase"


class AutoMerge:
    def __init__(
        self,
        github: GitHubClient,
        strategy: MergeStrategy = MergeStrategy.SQUASH,
        store: ContextStore | None = None,
    ) -> None:
        self._github = github
        self._strategy = strategy
        if store is None:
            from core.context_store import ContextStore
            from db import db
            self._store = ContextStore(db)
        else:
            self._store = store

    async def merge_when_ready(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        commit_title: str = "",
    ) -> MergeResult:
        pr = await self._github.get_pull_request(owner, repo, pr_number)
        if pr.merged:
            return MergeResult(merged=True, message="Already merged")

        checks_passed = await self._wait_for_checks(owner, repo, pr.head_ref)
        if not checks_passed:
            return MergeResult(merged=False, message="CI checks failed or timed out")

        # Check if the head branch matches a known integration_branch of any workflow
        is_integration_pr = False
        try:
            workflow_row = await self._store.get_workflow_by_branch(pr.head_ref)
            if workflow_row:
                is_integration_pr = bool(workflow_row.get("integration_branch"))
        except Exception:
            pass

        if is_integration_pr:
            # Look for integrator task
            rows = await self._store.get_tasks_by_branch(owner, repo, pr.head_ref)
            integrator_verdict_data = None
            integrator_task_row = None
            for r in rows:
                ctx = r.get("context", {})
                if isinstance(ctx, dict) and ctx.get("is_integrator_task"):
                    integrator_verdict_data = ctx.get("integrator_verdict")
                    integrator_task_row = r
                    break

            if not integrator_verdict_data:
                return MergeResult(merged=False, message="Integrator review is pending")

            verdict = integrator_verdict_data.get("verdict", "").lower()
            if verdict == "reject":
                # Notify responsible orchestrator
                try:
                    from core.account_pool import get_singleton_pool
                    from models.workflow import AgentTask

                    task_obj = AgentTask.model_validate(integrator_task_row)
                    pool = get_singleton_pool()
                    store = self._store

                    issues_summary = ""
                    for issue in integrator_verdict_data.get("blocking_issues", []):
                        issues_summary += f"- {issue.get('file', 'unknown')}: {issue.get('issue', '')} (Severity: {issue.get('severity', 'blocking')})\n"
                    summary = f"Integrator Review Rejected:\n{issues_summary}"

                    from core.orchestrator_relay import notify_orchestrator
                    await notify_orchestrator(pool, store, task_obj, "rejected", summary=summary)
                except Exception as e:
                    log.warning("failed_to_notify_orchestrator_on_integrator_rejection", error=str(e))

                return MergeResult(merged=False, message="Integrator review rejected the merge")

            if verdict != "approve":
                return MergeResult(merged=False, message=f"Integrator review has unhandled verdict: {verdict}")
        else:
            # Query database for the QA task matching this branch
            from core.account_pool import get_singleton_pool
            from models.workflow import AgentTask

            rows = await self._store.get_tasks_by_branch(owner, repo, pr.head_ref)
            qa_verdict_data = None
            qa_task_row = None
            for r in rows:
                ctx = r.get("context", {})
                if isinstance(ctx, dict) and ctx.get("is_qa_task"):
                    qa_verdict_data = ctx.get("qa_verdict")
                    qa_task_row = r
                    break

            if not qa_verdict_data:
                return MergeResult(merged=False, message="QA review is pending")

            verdict = qa_verdict_data.get("verdict", "").lower()
            if verdict == "reject":
                # Notify the orchestrator session on rejection
                try:
                    task_obj = AgentTask.model_validate(qa_task_row)
                    from core.account_pool import get_singleton_pool

                    pool = get_singleton_pool()
                    store = self._store

                    issues_summary = ""
                    for issue in qa_verdict_data.get("blocking_issues", []):
                        issues_summary += f"- {issue.get('file', 'unknown')}: {issue.get('issue', '')} (Severity: {issue.get('severity', 'blocking')})\n"
                    summary = f"QA Review Rejected:\n{issues_summary}"

                    from core.orchestrator_relay import notify_orchestrator
                    await notify_orchestrator(pool, store, task_obj, "rejected", summary=summary)
                except Exception as e:
                    log.warning("failed_to_notify_orchestrator_on_rejection", error=str(e))

                return MergeResult(merged=False, message="QA review rejected the merge")

            if verdict != "approve":
                return MergeResult(merged=False, message=f"QA review has unhandled verdict: {verdict}")

        merge_res = await self._github.merge_pull_request(
            owner, repo, pr_number,
            merge_method=self._strategy.value,
            commit_title=commit_title,
        )

        # Post-merge individual branch into integration branch for multi-task workflows
        if merge_res.merged and not is_integration_pr:
            try:
                task_rows = await self._store.get_tasks_by_branch(owner, repo, pr.head_ref)
                worker_task_row = None
                for tr in task_rows:
                    ctx = tr.get("context", {})
                    if not (isinstance(ctx, dict) and (ctx.get("is_qa_task") or ctx.get("is_integrator_task"))):
                        worker_task_row = tr
                        break

                if worker_task_row and worker_task_row.get("workflow_id"):
                    wf_row = await self._store.get_workflow_state(worker_task_row["workflow_id"])
                    if wf_row:
                        integration_branch = wf_row.get("integration_branch")
                        if integration_branch:
                            log.info("merging_individual_task_branch_into_integration", branch=pr.base_ref, integration=integration_branch)
                            await self._github.merge_branch(
                                owner, repo, integration_branch, pr.base_ref,
                                f"jat: merge task branch {pr.base_ref} into integration {integration_branch}"
                            )
            except Exception as e:
                log.warning("failed_to_merge_branch_into_integration", error=str(e))

        return merge_res

    async def _wait_for_checks(
        self, owner: str, repo: str, ref: str
    ) -> bool:
        elapsed = 0.0
        interval = CHECK_INITIAL_INTERVAL
        while elapsed < CHECK_TIMEOUT:
            checks = await self._github.list_check_runs(owner, repo, ref)

            if not checks:
                return True

            all_done = all(c.status == CheckStatus.COMPLETED for c in checks)
            if all_done:
                failures = [
                    c for c in checks
                    if c.conclusion not in (CheckConclusion.SUCCESS, CheckConclusion.SKIPPED, CheckConclusion.NEUTRAL)
                ]
                if failures:
                    names = ", ".join(c.name for c in failures)
                    log.warning("checks_failed", pr_ref=ref, failed=names)
                    return False
                return True

            # Calculate adaptive sleep interval with +/- 10% jitter
            jitter = random.uniform(0.9, 1.1)
            sleep_time = interval * jitter

            # Cap the final sleep to the exact remaining time before CHECK_TIMEOUT is reached
            remaining = CHECK_TIMEOUT - elapsed
            if sleep_time > remaining:
                sleep_time = remaining

            if sleep_time <= 0:
                break

            await asyncio.sleep(sleep_time)
            elapsed += sleep_time

            # Update the base interval for the next iteration
            interval = min(interval * CHECK_MULTIPLIER, CHECK_MAX_INTERVAL)

        if elapsed >= CHECK_TIMEOUT:
            log.warning("checks_timed_out", pr_ref=ref)
            return False
        return False
