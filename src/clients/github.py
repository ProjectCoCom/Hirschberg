"""
High-level GitHub API client wrapper.

Responsibilities:
- Handles branch management, PR creation/merging, auto-retries for 5xx/429s, and file manipulation on GitHub.

Coupling:
- Tightly coupled to GitHub API endpoints and utilized across core engines.
"""


from __future__ import annotations

import httpx
import structlog
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from exceptions import GitHubApiError
from models.github import CheckRun, MergeResult, PullRequest

log = structlog.get_logger()

GITHUB_API_URL = "https://api.github.com"
DEFAULT_TIMEOUT = 30.0


def _is_retryable(exc: BaseException) -> bool:
    return isinstance(exc, GitHubApiError) and exc.is_retryable


_retry = retry(
    retry=retry_if_exception(_is_retryable),
    stop=stop_after_attempt(3),
    wait=wait_exponential(min=1, max=10),
)


class GitHubClient:
    def __init__(self, token: str) -> None:
        self._client = httpx.AsyncClient(
            base_url=GITHUB_API_URL,
            headers={
                "Authorization": f"token {token}",
                "Accept": "application/vnd.github.v3+json",
            },
            timeout=DEFAULT_TIMEOUT,
        )

    async def close(self) -> None:
        await self._client.aclose()

    def _raise_on_error(self, response: httpx.Response) -> None:
        self._check_rate_limit(response)
        if response.status_code >= 400:
            raise GitHubApiError(response.status_code, response.text)

    def _check_rate_limit(self, response: httpx.Response) -> None:
        remaining = response.headers.get("x-ratelimit-remaining")
        if remaining is not None and int(remaining) < 10:
            reset = response.headers.get("x-ratelimit-reset", "unknown")
            log.warning("rate_limit_low", remaining=remaining, reset_at=reset)

    @_retry
    async def get_pull_request(
        self, owner: str, repo: str, pr_number: int
    ) -> PullRequest:
        response = await self._client.get(
            f"/repos/{owner}/{repo}/pulls/{pr_number}"
        )
        self._raise_on_error(response)
        data = response.json()
        return PullRequest(
            number=data["number"],
            title=data.get("title", ""),
            state=data.get("state", ""),
            html_url=data.get("html_url", ""),
            head_ref=data.get("head", {}).get("ref", ""),
            base_ref=data.get("base", {}).get("ref", ""),
            mergeable=data.get("mergeable"),
            merged=data.get("merged", False),
        )

    @_retry
    async def list_check_runs(
        self, owner: str, repo: str, ref: str
    ) -> list[CheckRun]:
        response = await self._client.get(
            f"/repos/{owner}/{repo}/commits/{ref}/check-runs"
        )
        self._raise_on_error(response)
        data = response.json()
        return [
            CheckRun(
                id=cr["id"],
                name=cr.get("name", ""),
                status=cr.get("status", "queued"),
                conclusion=cr.get("conclusion"),
            )
            for cr in data.get("check_runs", [])
        ]

    @_retry
    async def merge_pull_request(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        merge_method: str = "squash",
        commit_title: str = "",
    ) -> MergeResult:
        payload: dict = {"merge_method": merge_method}
        if commit_title:
            payload["commit_title"] = commit_title

        response = await self._client.put(
            f"/repos/{owner}/{repo}/pulls/{pr_number}/merge",
            json=payload,
        )
        self._raise_on_error(response)
        data = response.json()
        return MergeResult(
            sha=data.get("sha", ""),
            merged=data.get("merged", False),
            message=data.get("message", ""),
        )

    @_retry
    async def list_pr_comments(
        self, owner: str, repo: str, pr_number: int
    ) -> list[dict]:
        response = await self._client.get(
            f"/repos/{owner}/{repo}/pulls/{pr_number}/comments"
        )
        self._raise_on_error(response)
        return response.json()

    async def create_branch_from_ref(
        self, owner: str, repo: str, branch_name: str, sha: str
    ) -> bool:
        url = f"/repos/{owner}/{repo}/git/refs"
        body = {"ref": f"refs/heads/{branch_name}", "sha": sha}
        try:
            res = await self._client.post(url, json=body)
            if res.status_code == 201:
                return True
            if res.status_code == 422:
                # Branch already exists — update it to the latest SHA
                update_url = f"/repos/{owner}/{repo}/git/refs/heads/{branch_name}"
                update_res = await self._client.patch(update_url, json={"sha": sha, "force": True})
                return update_res.status_code == 200
        except Exception as e:
            log.warning("branch_creation_failed", owner=owner, repo=repo, branch=branch_name, error=str(e))
        return False

    async def get_default_branch_sha(self, owner: str, repo: str) -> str | None:
        try:
            res = await self._client.get(f"/repos/{owner}/{repo}")
            if res.status_code != 200:
                return None
            default_branch = res.json().get("default_branch", "main")
            ref_res = await self._client.get(f"/repos/{owner}/{repo}/git/ref/heads/{default_branch}")
            if ref_res.status_code != 200:
                return None
            return ref_res.json()["object"]["sha"]
        except Exception as e:
            log.error("unhandled_exception", error=str(e))
            return None

    async def get_branch_sha(self, owner: str, repo: str, branch: str) -> str | None:
        try:
            ref_res = await self._client.get(f"/repos/{owner}/{repo}/git/ref/heads/{branch}")
            if ref_res.status_code != 200:
                return None
            return ref_res.json()["object"]["sha"]
        except Exception as e:
            log.error("unhandled_exception", error=str(e))
            return None

    async def create_branch_with_base(
        self, owner: str, repo: str, branch_name: str, base_branch: str | None = None
    ) -> bool:
        sha = None
        if base_branch:
            sha = await self.get_branch_sha(owner, repo, base_branch)
        if not sha:
            sha = await self.get_default_branch_sha(owner, repo)
        if not sha:
            return False
        return await self.create_branch_from_ref(owner, repo, branch_name, sha)

    async def merge_branch(self, owner: str, repo: str, base: str, head: str, commit_message: str) -> str:
        try:
            res = await self._client.post(
                f"/repos/{owner}/{repo}/merges",
                json={"base": base, "head": head, "commit_message": commit_message}
            )
            if res.status_code == 201:
                return "merged"
            elif res.status_code == 204:
                return "already_merged"
            elif res.status_code == 409:
                return "conflict"
            else:
                return f"error_{res.status_code}"
        except Exception as e:
            return f"error_{e}"

    async def delete_branch(self, owner: str, repo: str, branch_name: str) -> bool:
        try:
            res = await self._client.delete(f"/repos/{owner}/{repo}/git/refs/heads/{branch_name}")
            return res.status_code == 204
        except Exception as e:
            log.error("unhandled_exception", error=str(e))
            return False

    async def create_pull_request(self, owner: str, repo: str, title: str,
                                  head: str, base: str, body: str) -> str | None:
        try:
            res = await self._client.post(
                f"/repos/{owner}/{repo}/pulls",
                json={"title": title, "head": head, "base": base, "body": body}
            )
            if res.status_code == 201:
                return res.json().get("html_url")
        except Exception as e:
            log.error("unhandled_exception", error=str(e))
            pass
        return None

    async def create_repo(
        self,
        name: str,
        private: bool = True,
        description: str = "",
        auto_init: bool = True,
    ) -> dict:
        payload: dict = {
            "name": name,
            "private": private,
            "auto_init": auto_init,
        }
        if description:
            payload["description"] = description

        response = await self._client.post("/user/repos", json=payload)
        self._raise_on_error(response)
        data = response.json()
        return {
            "id": data["id"],
            "full_name": data["full_name"],
            "owner": data["owner"]["login"],
            "name": data["name"],
            "html_url": data["html_url"],
            "private": data["private"],
            "default_branch": data.get("default_branch", "main"),
            "source": f"sources/github/{data['owner']['login']}/{data['name']}",
        }
