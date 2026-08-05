"""
Summary: Evaluator for pull request merge reviews.

What it does: Performs pre-merge checks and orchestrates QA evaluations.

How it fits in: Used by 'src/core/auto_merge.py'.
"""



from __future__ import annotations

import asyncio

from clients.github import GitHubClient
from clients.jules import JulesClient
from models.jules import SessionState


async def merge_branches(owner: str, repo: str, branches: list[str], target_branch: str, token: str) -> dict:
    results: dict[str, str] = {}
    gh_client = GitHubClient(token)
    try:
        for branch in branches:
            res_str = await gh_client.merge_branch(
                owner, repo, target_branch, branch, f"jat: merge {branch} into {target_branch}"
            )
            results[branch] = res_str
    finally:
        await gh_client.close()
    return results


async def create_integration_branch(owner: str, repo: str, base_sha: str, branch_name: str, token: str) -> bool:
    gh_client = GitHubClient(token)
    try:
        return await gh_client.create_branch_from_ref(owner, repo, branch_name, base_sha)
    finally:
        await gh_client.close()


async def run_review_session(
    owner: str, repo: str, integration_branch: str, jules_key: str,
    context_summary: str, timeout_minutes: int = 20
) -> dict:
    prompt = (
        "You are the final reviewer. All agent work has been merged into this branch.\n\n"
        f"Agent context:\n{context_summary}\n\n"
        "Tasks:\n"
        "1. Review all changes for integration issues\n"
        "2. Run tests if available\n"
        "3. Verify exit criteria from each agent were met\n"
        "4. Create a REVIEW.md summarizing what was done and any issues found"
    )

    client = JulesClient(jules_key)
    try:
        session = await client.create_session(
            prompt=prompt,
            source=f"sources/github/{owner}/{repo}",
            branch=integration_branch,
            title="JAT-AI: Review Session",
        )
        session_id = session.id
    except Exception as e:
        await client.close()
        return {"status": "failed", "error": f"Could not create review session: {e}"}

    deadline = asyncio.get_event_loop().time() + (timeout_minutes * 60)
    result_data = {}
    try:
        while asyncio.get_event_loop().time() < deadline:
            try:
                session = await client.get_session(session_id)
                if session.state in (SessionState.COMPLETED, SessionState.FAILED):
                    result_data = {
                        "state": str(session.state),
                        "outputs": [{"pull_request": {"url": o.pull_request.url}} for o in session.outputs if o.pull_request] if session.outputs else []
                    }
                    break
                if session.state == SessionState.AWAITING_PLAN_APPROVAL:
                    await client.approve_plan(session_id)
            except Exception:
                pass
            await asyncio.sleep(15)
        else:
            result_data = {"state": "TIMEOUT"}
    finally:
        await client.close()

    return {"status": result_data.get("state", "UNKNOWN"), "session_id": session_id, "data": result_data}


async def cleanup_branches(owner: str, repo: str, branches: list[str], token: str) -> dict[str, bool]:
    gh_client = GitHubClient(token)
    results = {}
    try:
        for branch in branches:
            results[branch] = await gh_client.delete_branch(owner, repo, branch)
    finally:
        await gh_client.close()
    return results


async def create_final_pr(owner: str, repo: str, integration_branch: str, base: str, title: str, token: str) -> str | None:
    gh_client = GitHubClient(token)
    try:
        return await gh_client.create_pull_request(
            owner, repo, title, integration_branch, base, "Automated PR from JAT-AI orchestrator."
        )
    finally:
        await gh_client.close()
