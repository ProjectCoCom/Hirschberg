"""
Model Context Protocol (MCP) server.

Responsibilities:
- Defines async-native tool functions and allows external tools/agents to safely inspect databases and coordinate tasks.

Coupling:
- Exposes tools to MCP clients.
"""


from __future__ import annotations

import json
import os
import sys

from dotenv import load_dotenv

from mcp.server.fastmcp import FastMCP

# MCP server runs as a standalone process, needs src/ on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

load_dotenv()

mcp = FastMCP("JAT MCP Server")


async def _get_jules():
    from clients.jules import JulesClient
    from config import load_settings
    from core.ai_interface import KeyVault
    from db import db

    accounts = await db.select("accounts", {"enabled": True})
    if not accounts:
        raise RuntimeError("No enabled Jules accounts configured.")
    acc = accounts[0]
    encrypted = acc.get("api_key_encrypted", "")
    if encrypted:
        vault = KeyVault(load_settings().encryption_key)
        try:
            key = vault.decrypt(encrypted)
        except Exception:
            key = encrypted
    else:
        key = ""

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
async def jat_list_sources() -> str:
    """List all repos connected to Jules."""
    client = await _get_jules()
    try:
        sources = await client.list_sources()
        return json.dumps([{"name": s.name, "id": s.id} for s in sources], indent=2)
    finally:
        await client.close()


@mcp.tool()
async def jat_list_sessions(page_size: int = 10) -> str:
    """List recent Jules sessions."""
    client = await _get_jules()
    try:
        sessions = await client.list_sessions(page_size=page_size)
        return json.dumps([
            {"id": s.id, "title": s.title, "state": s.state}
            for s in sessions
        ], indent=2)
    finally:
        await client.close()


@mcp.tool()
async def jat_get_session(session_id: str) -> str:
    """Get details of a specific Jules session."""
    client = await _get_jules()
    try:
        s = await client.get_session(session_id)
        return json.dumps(s.model_dump(mode="json"), indent=2)
    finally:
        await client.close()


@mcp.tool()
async def jat_run_session(
    prompt: str,
    owner: str,
    repo: str,
    branch: str = "main",
    title: str = "",
) -> str:
    """Create a Jules session, track it to completion, return the result."""
    from core.session_runner import run_session
    jules = await _get_jules()
    db = _get_db()
    try:
        source = f"sources/github/{owner}/{repo}"
        res = await run_session(
            jules=jules, db=db,
            prompt=prompt, source=source,
            branch=branch, title=title,
        )
        return json.dumps(res, indent=2)
    finally:
        await jules.close()


@mcp.tool()
async def jat_get_activities(session_id: str) -> str:
    """Get activities for a Jules session."""
    client = await _get_jules()
    try:
        acts = await client.list_activities(session_id)
        return json.dumps([
            {
                "id": a.id,
                "originator": a.originator,
                "description": a.description,
            }
            for a in acts
        ], indent=2)
    finally:
        await client.close()


@mcp.tool()
async def jat_send_message(session_id: str, prompt: str) -> str:
    """Send a follow-up message to an active Jules session."""
    client = await _get_jules()
    try:
        await client.send_message(session_id, prompt)
        return json.dumps({"status": "sent"})
    finally:
        await client.close()


@mcp.tool()
async def jat_create_repo(name: str, private: bool = True, description: str = "") -> str:
    """Create a new GitHub repo. Jules gets access automatically."""
    gh = _get_github()
    try:
        res = await gh.create_repo(name, private=private, description=description)
        return json.dumps(res, indent=2)
    finally:
        await gh.close()


@mcp.tool()
async def jat_merge_pr(owner: str, repo: str, pr_number: int, strategy: str = "squash") -> str:
    """Merge a pull request after CI passes."""
    from core.auto_merge import AutoMerge, MergeStrategy
    gh = _get_github()
    try:
        merger = AutoMerge(gh, strategy=MergeStrategy(strategy))
        result = await merger.merge_when_ready(owner, repo, pr_number)
        return json.dumps({"merged": result.merged, "sha": result.sha, "message": result.message}, indent=2)
    finally:
        await gh.close()


if __name__ == "__main__":
    mcp.run()
