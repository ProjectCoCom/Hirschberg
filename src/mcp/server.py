from __future__ import annotations

import asyncio
import json
import os
import sys

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

# MCP server runs as a standalone process, needs src/ on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

load_dotenv()

mcp = FastMCP("JAT MCP Server")


def _get_jules():
    import asyncio
    from clients.jules import JulesClient
    from core.plan_executor import get_jules_key
    key = asyncio.run(get_jules_key())
    if not key:
        raise RuntimeError("No Jules API key configured. Add one via the dashboard APIs page.")
    return JulesClient(key)


def _get_github():
    from clients.github import GitHubClient
    return GitHubClient(os.environ["GITHUB_TOKEN"])


def _get_db():
    from db import db
    return db


@mcp.tool()
def jat_list_sources() -> str:
    """List all repos connected to Jules."""
    async def _run():
        client = _get_jules()
        try:
            sources = await client.list_sources()
            return [{"name": s.name, "id": s.id} for s in sources]
        finally:
            await client.close()
    return json.dumps(asyncio.run(_run()), indent=2)


@mcp.tool()
def jat_list_sessions(page_size: int = 10) -> str:
    """List recent Jules sessions."""
    async def _run():
        client = _get_jules()
        try:
            sessions = await client.list_sessions(page_size=page_size)
            return [
                {"id": s.id, "title": s.title, "state": s.state}
                for s in sessions
            ]
        finally:
            await client.close()
    return json.dumps(asyncio.run(_run()), indent=2)


@mcp.tool()
def jat_get_session(session_id: str) -> str:
    """Get details of a specific Jules session."""
    async def _run():
        client = _get_jules()
        try:
            s = await client.get_session(session_id)
            return s.model_dump(mode="json")
        finally:
            await client.close()
    return json.dumps(asyncio.run(_run()), indent=2)


@mcp.tool()
def jat_run_session(
    prompt: str,
    owner: str,
    repo: str,
    branch: str = "main",
    title: str = "",
) -> str:
    """Create a Jules session, track it to completion, return the result."""
    async def _run():
        from core.session_runner import run_session
        jules = _get_jules()
        db = _get_db()
        try:
            source = f"sources/github/{owner}/{repo}"
            return await run_session(
                jules=jules, db=db,
                prompt=prompt, source=source,
                branch=branch, title=title,
            )
        finally:
            await jules.close()
    return json.dumps(asyncio.run(_run()), indent=2)


@mcp.tool()
def jat_get_activities(session_id: str) -> str:
    """Get activities for a Jules session."""
    async def _run():
        client = _get_jules()
        try:
            acts = await client.list_activities(session_id)
            return [
                {
                    "id": a.id,
                    "originator": a.originator,
                    "description": a.description,
                }
                for a in acts
            ]
        finally:
            await client.close()
    return json.dumps(asyncio.run(_run()), indent=2)


@mcp.tool()
def jat_send_message(session_id: str, prompt: str) -> str:
    """Send a follow-up message to an active Jules session."""
    async def _run():
        client = _get_jules()
        try:
            await client.send_message(session_id, prompt)
            return {"status": "sent"}
        finally:
            await client.close()
    return json.dumps(asyncio.run(_run()))


@mcp.tool()
def jat_create_repo(name: str, private: bool = True, description: str = "") -> str:
    """Create a new GitHub repo. Jules gets access automatically."""
    async def _run():
        gh = _get_github()
        try:
            return await gh.create_repo(name, private=private, description=description)
        finally:
            await gh.close()
    return json.dumps(asyncio.run(_run()), indent=2)


@mcp.tool()
def jat_merge_pr(owner: str, repo: str, pr_number: int, strategy: str = "squash") -> str:
    """Merge a pull request after CI passes."""
    async def _run():
        from core.auto_merge import AutoMerge, MergeStrategy
        gh = _get_github()
        try:
            merger = AutoMerge(gh, strategy=MergeStrategy(strategy))
            result = await merger.merge_when_ready(owner, repo, pr_number)
            return {"merged": result.merged, "sha": result.sha, "message": result.message}
        finally:
            await gh.close()
    return json.dumps(asyncio.run(_run()), indent=2)


if __name__ == "__main__":
    mcp.run()
