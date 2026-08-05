"""
API router for GitHub repository integration.

Responsibilities:
- Exposes endpoints for listing files, branches, PRs, and triggers file-write or branch operations.

Coupling:
- Depends on 'src/clients/github.py'.
"""


from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx
from fastapi import APIRouter

from config import load_settings

router = APIRouter()
settings = load_settings()


def _now() -> str:
    return datetime.now(UTC).isoformat()


async def _fetch_all_repos(client: httpx.AsyncClient, headers: dict) -> list[dict]:
    repos = []
    page = 1
    while True:
        try:
            res = await client.get(
                "https://api.github.com/user/repos",
                params={"per_page": 100, "page": page, "sort": "pushed"},
                headers=headers
            )
        except (httpx.ReadTimeout, httpx.ConnectTimeout):
            break
        if res.status_code != 200:
            break
        batch = res.json()
        if not batch:
            break
        repos.extend(batch)
        page += 1
        if len(batch) < 100:
            break
    return repos


async def _fetch_commits(client: httpx.AsyncClient, owner: str, headers: dict, since: str) -> list[dict]:
    search_headers = {**headers, "Accept": "application/vnd.github.cloak-preview+json"}
    commits = []
    page = 1
    while page <= 10:
        try:
            res = await client.get(
                f"https://api.github.com/search/commits?q=author:{owner}+committer-date:>{since}&sort=committer-date&per_page=100&page={page}",
                headers=search_headers,
            )
        except (httpx.ReadTimeout, httpx.ConnectTimeout):
            break
        if res.status_code != 200:
            break
        if len(res.content) > 5_000_000:
            break
        items = res.json().get("items", [])
        if not items:
            break
        for c in items:
            commit_data = c.get("commit", {})
            author = commit_data.get("author", {})
            commits.append({
                "hash": c.get("sha", ""),
                "shortHash": c.get("sha", "")[:7],
                "subject": commit_data.get("message", "").split("\n")[0],
                "authorName": author.get("name", ""),
                "authorEmail": author.get("email", ""),
                "authoredAt": author.get("date", ""),
                "body": commit_data.get("message", "").split("\n")[0],
                "url": c.get("html_url", ""),
                "repo": c.get("repository", {}).get("full_name", ""),
                "filesChanged": 0,
                "insertions": 0,
                "deletions": 0,
            })
        if len(items) < 100:
            break
        page += 1
    return commits


async def _get_owner(client: httpx.AsyncClient, headers: dict) -> str:
    try:
        res = await client.get("https://api.github.com/user", headers=headers)
        return res.json().get("login", "unknown") if res.status_code == 200 else "unknown"
    except (httpx.ReadTimeout, httpx.ConnectTimeout):
        return "unknown"


async def _fetch_issue_count(client: httpx.AsyncClient, owner: str, headers: dict) -> int:
    try:
        res = await client.get(
            "https://api.github.com/search/issues",
            params={"q": f"author:{owner} is:issue is:open", "per_page": 1},
            headers=headers
        )
        return res.json().get("total_count", 0) if res.status_code == 200 else 0
    except (httpx.ReadTimeout, httpx.ConnectTimeout):
        return 0


async def _fetch_pr_count(client: httpx.AsyncClient, owner: str, headers: dict) -> int:
    try:
        res = await client.get(
            "https://api.github.com/search/issues",
            params={"q": f"author:{owner} is:pr is:open", "per_page": 1},
            headers=headers
        )
        return res.json().get("total_count", 0) if res.status_code == 200 else 0
    except (httpx.ReadTimeout, httpx.ConnectTimeout):
        return 0


@router.get("/api/github/summary")
async def get_github_summary():
    token = settings.github_token
    if not token:
        return {
            "status": "error",
            "source": "none",
            "fetchedAt": _now(),
            "message": "No GitHub token",
            "commitsPerDay": [],
            "recentCommits": []
        }
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
    since = (datetime.now(UTC) - timedelta(days=30)).strftime("%Y-%m-%d")
    async with httpx.AsyncClient(timeout=30.0) as client:
        owner = await _get_owner(client, headers)
        if owner == "unknown":
            return {
                "status": "error",
                "source": "none",
                "fetchedAt": _now(),
                "message": "GitHub API timeout",
                "commitsPerDay": [],
                "recentCommits": []
            }
        repos = await _fetch_all_repos(client, headers)
        total_stars = sum(r.get("stargazers_count", 0) for r in repos)
        total_issues = await _fetch_issue_count(client, owner, headers)
        total_prs = await _fetch_pr_count(client, owner, headers)
        recent_commits = await _fetch_commits(client, owner, headers, since)
        commits_by_day: dict[str, int] = {}
        for c in recent_commits:
            date = (c.get("authoredAt") or "")[:10]
            if date:
                commits_by_day[date] = commits_by_day.get(date, 0) + 1
        today = datetime.now(UTC).date()
        commits_per_day = [
            {
                "date": (today - timedelta(days=29 - i)).strftime("%Y-%m-%d"),
                "count": commits_by_day.get((today - timedelta(days=29 - i)).strftime("%Y-%m-%d"), 0)
            }
            for i in range(30)
        ]
        return {
            "status": "ok",
            "source": "gh-cli",
            "fetchedAt": _now(),
            "repo": f"{owner} ({len(repos)} repos)",
            "stargazerCount": total_stars,
            "openIssueCount": total_issues,
            "openPullRequestCount": total_prs,
            "commitsPerDay": commits_per_day[-30:],
            "recentCommits": recent_commits[:50],
        }


@router.get("/api/github/issues")
async def get_github_issues():
    token = settings.github_token
    if not token:
        return []
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
    async with httpx.AsyncClient(timeout=15.0) as client:
        owner = await _get_owner(client, headers)
        res = await client.get(
            "https://api.github.com/search/issues",
            params={"q": f"author:{owner} is:issue is:open", "per_page": 20},
            headers=headers
        )
        if res.status_code != 200:
            return []
        items = res.json().get("items", [])
        return [
            {
                "title": i["title"],
                "repo": i["repository_url"].split("/")[-1],
                "url": i["html_url"],
                "created": i["created_at"][:10],
                "labels": [label["name"] for label in i.get("labels", [])]
            }
            for i in items
        ]


@router.get("/api/github/pulls")
async def get_github_pulls():
    token = settings.github_token
    if not token:
        return []
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
    async with httpx.AsyncClient(timeout=15.0) as client:
        owner = await _get_owner(client, headers)
        res = await client.get(
            "https://api.github.com/search/issues",
            params={"q": f"author:{owner} is:pr is:open", "per_page": 20},
            headers=headers
        )
        if res.status_code != 200:
            return []
        items = res.json().get("items", [])
        return [
            {
                "title": i["title"],
                "repo": i["repository_url"].split("/")[-1],
                "url": i["html_url"],
                "created": i["created_at"][:10],
                "draft": i.get("draft", False)
            }
            for i in items
        ]


@router.get("/api/github/stars")
async def get_github_stars():
    token = settings.github_token
    if not token:
        return []
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
    async with httpx.AsyncClient(timeout=15.0) as client:
        repos = await _fetch_all_repos(client, headers)
        return [
            {"repo": r["full_name"], "stars": r["stargazers_count"], "url": r["html_url"]}
            for r in repos if r.get("stargazers_count", 0) > 0
        ]


@router.get("/api/github/repos")
async def get_github_repos():
    token = settings.github_token
    if not token:
        return {"repos": []}
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
    async with httpx.AsyncClient(timeout=30.0) as client:
        repos = await _fetch_all_repos(client, headers)
        return {
            "repos": [
                {"name": r["name"], "full_name": r["full_name"], "private": r.get("private", False)}
                for r in repos
            ]
        }
