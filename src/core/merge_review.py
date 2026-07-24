from __future__ import annotations

import asyncio
import httpx

from clients.jules import JulesClient
from models.jules import SessionState


async def merge_branches(owner: str, repo: str, branches: list[str], target_branch: str, token: str) -> dict:
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
    results: dict[str, str] = {}

    async with httpx.AsyncClient(timeout=30.0) as client:
        for branch in branches:
            res = await client.post(
                f"https://api.github.com/repos/{owner}/{repo}/merges",
                json={"base": target_branch, "head": branch, "commit_message": f"jat: merge {branch} into {target_branch}"},
                headers=headers,
            )
            if res.status_code == 201:
                results[branch] = "merged"
            elif res.status_code == 204:
                results[branch] = "already_merged"
            elif res.status_code == 409:
                results[branch] = "conflict"
            else:
                results[branch] = f"error_{res.status_code}"

    return results


async def create_integration_branch(owner: str, repo: str, base_sha: str, branch_name: str, token: str) -> bool:
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
    async with httpx.AsyncClient(timeout=15.0) as client:
        res = await client.post(
            f"https://api.github.com/repos/{owner}/{repo}/git/refs",
            json={"ref": f"refs/heads/{branch_name}", "sha": base_sha},
            headers=headers,
        )
    return res.status_code == 201


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
        "3. Fix any conflicts or broken imports\n"
        "4. Verify exit criteria from each agent were met\n"
        "5. Create a REVIEW.md summarizing what was done and any issues found"
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
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
    results = {}
    async with httpx.AsyncClient(timeout=15.0) as client:
        for branch in branches:
            res = await client.delete(
                f"https://api.github.com/repos/{owner}/{repo}/git/refs/heads/{branch}",
                headers=headers,
            )
            results[branch] = res.status_code == 204
    return results


async def create_final_pr(owner: str, repo: str, integration_branch: str, base: str, title: str, token: str) -> str | None:
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
    async with httpx.AsyncClient(timeout=15.0) as client:
        res = await client.post(
            f"https://api.github.com/repos/{owner}/{repo}/pulls",
            json={"title": title, "head": integration_branch, "base": base, "body": "Automated PR from JAT-AI orchestrator."},
            headers=headers,
        )
    if res.status_code == 201:
        return res.json().get("html_url")
    return None
