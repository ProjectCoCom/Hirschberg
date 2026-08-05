"""
JDOCS prompt template manager.

Responsibilities:
- Compiles XML structures and manages prompt templates for agent context, rules, and history.

Coupling:
- Utilized by 'src/core/prompt_builder.py'.
"""


from __future__ import annotations

import base64
from datetime import UTC, datetime

import httpx

JDOCS_PATH = ".jules/jdocs"

CONTEXT_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<context>
  <agents>
  </agents>
</context>
"""

RULES_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<rules>
  <style>
    <rule>Use consistent naming conventions</rule>
    <rule>Keep functions under 40 lines</rule>
    <rule>No commented-out code</rule>
  </style>
  <git>
    <rule>Atomic commits with descriptive messages</rule>
    <rule>One logical change per commit</rule>
  </git>
  <testing>
    <rule>Write tests for new functionality</rule>
    <rule>Ensure existing tests pass before committing</rule>
  </testing>
</rules>
"""

SESSION_HISTORY_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<session_history>
</session_history>
"""


async def _get_file_sha(
    client: httpx.AsyncClient, owner: str, repo: str,
    path: str, branch: str, headers: dict
) -> str | None:
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}?ref={branch}"
    res = await client.get(url, headers=headers)
    if res.status_code == 200:
        return res.json().get("sha")
    return None


async def _create_or_update_file(
    client: httpx.AsyncClient, owner: str, repo: str, path: str, content: str, branch: str, headers: dict, message: str
) -> bool:
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
    encoded = base64.b64encode(content.encode()).decode()
    body: dict = {"message": message, "content": encoded, "branch": branch}

    sha = await _get_file_sha(client, owner, repo, path, branch, headers)
    if sha:
        body["sha"] = sha

    res = await client.put(url, json=body, headers=headers)
    return res.status_code in (200, 201)


async def init_jdocs(owner: str, repo: str, branch: str, token: str) -> dict[str, bool]:
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
    results = {}

    async with httpx.AsyncClient(timeout=15.0) as client:
        gitignore_url = f"https://api.github.com/repos/{owner}/{repo}/contents/.gitignore?ref={branch}"
        gi_res = await client.get(gitignore_url, headers=headers)
        if gi_res.status_code == 200:
            gi_data = gi_res.json()
            gi_content = base64.b64decode(gi_data["content"]).decode()
            if ".jules/" not in gi_content:
                gi_content = gi_content.rstrip() + "\n.jules/\n"
                results["gitignore"] = await _create_or_update_file(
                    client, owner, repo, ".gitignore", gi_content, branch, headers, "jat: add .jules/ to .gitignore"
                )
        else:
            results["gitignore"] = await _create_or_update_file(
                client, owner, repo, ".gitignore", ".jules/\n", branch, headers, "jat: create .gitignore with .jules/"
            )

        results["context"] = await _create_or_update_file(
            client, owner, repo, f"{JDOCS_PATH}/context.xml",
            CONTEXT_TEMPLATE, branch, headers, "jat: init .jules/jdocs/context.xml"
        )
        results["rules"] = await _create_or_update_file(
            client, owner, repo, f"{JDOCS_PATH}/rules.xml",
            RULES_TEMPLATE, branch, headers, "jat: init .jules/jdocs/rules.xml"
        )
        results["session_history"] = await _create_or_update_file(
            client, owner, repo, f"{JDOCS_PATH}/session-history.xml",
            SESSION_HISTORY_TEMPLATE, branch, headers, "jat: init .jules/jdocs/session-history.xml"
        )

    return results


async def update_context_after_agent(
    owner: str, repo: str, branch: str, token: str,
    agent_id: str, task_description: str, status: str, pr_url: str | None, files_changed: list[str] | None
) -> bool:
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
    now = datetime.now(UTC).isoformat()

    async with httpx.AsyncClient(timeout=15.0) as client:
        url = f"https://api.github.com/repos/{owner}/{repo}/contents/{JDOCS_PATH}/context.xml?ref={branch}"
        res = await client.get(url, headers=headers)

        if res.status_code == 200:
            data = res.json()
            existing = base64.b64decode(data["content"]).decode()
            sha = data["sha"]
        else:
            existing = CONTEXT_TEMPLATE
            sha = None

    files_xml = ""
    if files_changed:
        files_xml = "\n    ".join(f"<file>{f}</file>" for f in files_changed)
        files_xml = f"\n    <files_changed>{files_xml}</files_changed>"

    agent_entry = f"""  <agent id="{agent_id}">
    <task>{task_description}</task>
    <status>{status}</status>
    <timestamp>{now}</timestamp>
    <pr_url>{pr_url or ""}</pr_url>{files_xml}
  </agent>
"""

    updated = existing.replace("</agents>", f"{agent_entry}</agents>")

    async with httpx.AsyncClient(timeout=15.0) as client:
        url = f"https://api.github.com/repos/{owner}/{repo}/contents/{JDOCS_PATH}/context.xml"
        encoded = base64.b64encode(updated.encode()).decode()
        body: dict = {
            "message": f"jat: update context after {agent_id}",
            "content": encoded,
            "branch": branch,
        }
        if sha:
            body["sha"] = sha
        res = await client.put(url, json=body, headers=headers)
        return res.status_code in (200, 201)


async def append_session_history(
    owner: str, repo: str, branch: str, token: str,
    agent_id: str, session_id: str, status: str, prompt_summary: str
) -> bool:
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
    now = datetime.now(UTC).isoformat()

    async with httpx.AsyncClient(timeout=15.0) as client:
        url = f"https://api.github.com/repos/{owner}/{repo}/contents/{JDOCS_PATH}/session-history.xml?ref={branch}"
        res = await client.get(url, headers=headers)

        if res.status_code == 200:
            data = res.json()
            existing = base64.b64decode(data["content"]).decode()
            sha = data["sha"]
        else:
            existing = SESSION_HISTORY_TEMPLATE
            sha = None

    entry = f"""  <session agent="{agent_id}" id="{session_id}" status="{status}" timestamp="{now}">
    <prompt>{prompt_summary[:200]}</prompt>
  </session>
"""

    updated = existing.replace("</session_history>", f"{entry}</session_history>")

    async with httpx.AsyncClient(timeout=15.0) as client:
        url = f"https://api.github.com/repos/{owner}/{repo}/contents/{JDOCS_PATH}/session-history.xml"
        encoded = base64.b64encode(updated.encode()).decode()
        body: dict = {
            "message": f"jat: session history for {agent_id}",
            "content": encoded,
            "branch": branch,
        }
        if sha:
            body["sha"] = sha
        res = await client.put(url, json=body, headers=headers)
        return res.status_code in (200, 201)
