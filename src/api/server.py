from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from api.providers import router as providers_router
from api.github import router as github_router
from api.jules_accounts import router as jules_router
from api.chat import router as chat_router
from api.repos import router as repos_router
from api.execute import router as execute_router
from api.conversations import router as conversations_router
from api.settings import router as settings_router
from api.usage import router as usage_router
from api.plans import router as plans_router
from config import load_settings
from db import db


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


settings = load_settings()


async def _find_session_by_prompt(task_row: dict, jules_key: str) -> str | None:
    """When session_id is missing (server crashed before it was saved), search recent
    Jules sessions by title pattern and creation time to recover the link."""
    prompt_prefix = task_row.get("prompt", "")[:40].lower()
    repo = f"{task_row.get('repo_owner', '')}/{task_row.get('repo_name', '')}"
    task_created = task_row.get("created_at", "")
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            res = await client.get(
                "https://jules.googleapis.com/v1alpha/sessions?pageSize=20",
                headers={"X-Goog-Api-Key": jules_key},
            )
        if res.status_code != 200:
            return None
        for s in res.json().get("sessions", []):
            title = s.get("title", "").lower()
            source = s.get("sourceContext", {}).get("source", "").lower()
            create_time = s.get("createTime", "")

            # Match by title containing the prompt prefix
            title_match = prompt_prefix and prompt_prefix[:20] in title
            # Match by repo + JAT-AI prefix in title
            repo_match = repo.lower() in source and "jat-ai" in title
            # Timestamp proximity check (within 5 minutes of task creation)
            time_match = _times_within_minutes(task_created, create_time, 5)

            if (title_match or repo_match) and time_match:
                return s.get("name", "").split("/")[-1]
            # Fallback: title match alone if no timestamp available
            if title_match and not task_created:
                return s.get("name", "").split("/")[-1]
    except Exception:
        pass
    return None


def _times_within_minutes(local_time: str, jules_time: str, minutes: int) -> bool:
    """Check if two timestamps are within N minutes of each other.
    local_time: '2026-05-10 06:38:49', jules_time: '2026-05-10T06:38:00Z'"""
    if not local_time or not jules_time:
        return True  # Can't compare — assume match
    from datetime import datetime, timezone
    try:
        lt = local_time.replace("T", " ").replace("Z", "")[:19]
        jt = jules_time.replace("T", " ").replace("Z", "")[:19]
        local_dt = datetime.strptime(lt, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        jules_dt = datetime.strptime(jt, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        return abs((local_dt - jules_dt).total_seconds()) < minutes * 60
    except Exception:
        return True  # Parse failure — don't block on this


async def _get_jules_key() -> str | None:
    from db import db
    from core.ai_interface import KeyVault
    from config import load_settings
    try:
        rows = await db.select("accounts")
    except Exception:
        return None
    enabled = [r for r in rows if r.get("enabled", True)]
    if not enabled:
        return None
    best = min(enabled, key=lambda r: r.get("sessions_today", 0))
    daily_limit = best.get("max_daily_tasks", 300)
    if best.get("sessions_today", 0) >= daily_limit:
        return None
    encrypted = best.get("api_key_encrypted", "")
    if not encrypted:
        return None
    vault = KeyVault(load_settings().encryption_key)
    try:
        return vault.decrypt(encrypted)
    except Exception:
        return encrypted


async def _local_poll_session_status(session_id: str, jules_key: str, timeout_minutes: int = 20) -> dict:
    from clients.jules import JulesClient
    from models.jules import SessionState
    client = JulesClient(jules_key)
    deadline = asyncio.get_event_loop().time() + (timeout_minutes * 60)
    try:
        while asyncio.get_event_loop().time() < deadline:
            try:
                session = await client.get_session(session_id)
                state = session.state
                if state in (SessionState.COMPLETED, SessionState.FAILED):
                    return {"state": str(state)}
                if state == SessionState.AWAITING_PLAN_APPROVAL:
                    await client.approve_plan(session_id)
            except Exception:
                pass
            await asyncio.sleep(15)
        return {"state": "TIMEOUT"}
    finally:
        await client.close()


async def _recover_orphaned_tasks():
    """On startup, check tasks stuck as 'running' and sync their actual state from Jules."""
    await asyncio.sleep(2)  # Let the DB connection settle
    try:
        rows = await db.select("agent_tasks", {"status": "running"})
    except Exception:
        return
    if not rows:
        return

    jules_key = await _get_jules_key()
    if not jules_key:
        return

    print(f"[RECOVERY] Found {len(rows)} orphaned running tasks, syncing with Jules...")

    for row in rows:
        session_id = row.get("session_id", "")
        if not session_id:
            # Server may have crashed before session_id was saved — try to find it on Jules by title
            session_id = await _find_session_by_prompt(row, jules_key)
            if session_id:
                await db.update("agent_tasks", {"session_id": session_id}, {"id": row["id"]})
            else:
                await db.update("agent_tasks", {"status": "failed"}, {"id": row["id"]})
                continue

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.get(
                    f"https://jules.googleapis.com/v1alpha/sessions/{session_id}",
                    headers={"X-Goog-Api-Key": jules_key},
                )
            if res.status_code != 200:
                await db.update("agent_tasks", {"status": "failed"}, {"id": row["id"]})
                continue

            state = res.json().get("state", "")
            if state == "COMPLETED":
                await db.update("agent_tasks", {"status": "completed"}, {"id": row["id"]})
                print(f"[RECOVERY] {session_id}: completed")
            elif state == "FAILED":
                await db.update("agent_tasks", {"status": "failed"}, {"id": row["id"]})
                print(f"[RECOVERY] {session_id}: failed")
            elif state in ("IN_PROGRESS", "AWAITING_PLAN_APPROVAL", "AWAITING_USER_INPUT", "QUEUED", "PLANNING"):
                # Still active on Jules — resume polling in background
                asyncio.create_task(_resume_polling(row, session_id, jules_key))
                print(f"[RECOVERY] {session_id}: still running, resuming poll")
            else:
                await db.update("agent_tasks", {"status": "failed"}, {"id": row["id"]})
        except Exception as e:
            print(f"[RECOVERY] {session_id}: error checking state: {e}")
            await db.update("agent_tasks", {"status": "failed"}, {"id": row["id"]})

    # After syncing running tasks, check for pending tasks that never started
    await _resume_pending_tasks(jules_key)


async def _resume_polling(task_row: dict, session_id: str, jules_key: str):
    """Resume polling a still-active Jules session and update the DB when it finishes."""
    result = await _local_poll_session_status(
        session_id, jules_key, timeout_minutes=20
    )
    state = result.get("state", "UNKNOWN")
    new_status = "completed" if state == "COMPLETED" else "failed"
    await db.update("agent_tasks", {"status": new_status}, {"id": task_row["id"]})
    print(f"[RECOVERY] {session_id}: poll finished -> {new_status}")


async def _resume_pending_tasks(jules_key: str):
    """Resume execution of tasks stuck as 'pending' after a crash.
    Reads the persisted execution context to reconstruct provider/model/mode."""
    try:
        pending = await db.select("agent_tasks", {"status": "pending"})
    except Exception:
        pending = []
    if not pending:
        return

    from api.execute import (
        _load_execution_context, _clear_execution_context,
        _resolve_ai_ctx, _run_task_once, _track_task,
        AgentTask, ExecutionPlan,
    )
    from clients.github import GitHubClient

    ctx = await _load_execution_context()
    if not ctx:
        print(f"[RECOVERY] {len(pending)} pending tasks but no execution context — cannot resume")
        return

    print(f"[RECOVERY] Resuming {len(pending)} pending tasks ({ctx.get('execution_mode', 'sequential')} mode)...")

    token = settings.github_token
    if not token:
        print("[RECOVERY] No GitHub token — cannot resume pending tasks")
        return

    ai_ctx = await _resolve_ai_ctx(ctx.get("provider_type", ""), ctx.get("model", ""))
    gh_client = GitHubClient(token)
    try:
        base_sha = await gh_client.get_default_branch_sha(ctx["repo_owner"], ctx["repo_name"])
    finally:
        await gh_client.close()
    if not base_sha:
        print("[RECOVERY] Could not get base SHA — cannot resume")
        return

    plan = ExecutionPlan(
        repo_owner=ctx["repo_owner"],
        repo_name=ctx["repo_name"],
        tasks=[],
        execution_mode=ctx.get("execution_mode", "sequential"),
        max_retries=ctx.get("max_retries", 2),
        timeout_minutes=ctx.get("timeout_minutes", 20),
    )

    for i, row in enumerate(pending):
        task = AgentTask(
            id=row.get("id", f"agent-{i+1}"),
            description=row.get("prompt", ""),
            branch_name=f"jat/agent-{i+1}-recovery",
        )
        plan.tasks.append(task)

    # Execute sequentially regardless of original mode (safest for recovery)
    for i, task in enumerate(plan.tasks):
        result = await _run_task_once(task, plan, base_sha, jules_key, token, i, ai_ctx)
        print(f"[RECOVERY] Task '{task.description[:40]}': {result.status}")
        if result.status == "failed" and plan.execution_mode == "sequential":
            break

    await _clear_execution_context()
    print("[RECOVERY] Pending task resume complete")


@asynccontextmanager
async def lifespan(app: FastAPI):
    asyncio.create_task(_recover_orphaned_tasks())
    asyncio.create_task(_daily_reset_loop())
    yield


async def _daily_reset_loop():
    """Reset sessions_today at midnight UTC each day."""
    from datetime import datetime, timezone, timedelta

    while True:
        now = datetime.now(timezone.utc)
        tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        seconds_until_midnight = (tomorrow - now).total_seconds()
        await asyncio.sleep(seconds_until_midnight)
        try:
            rows = await db.select("accounts")
            for r in rows:
                if r.get("sessions_today", 0) > 0:
                    await db.update("accounts", {"sessions_today": 0}, {"id": r["id"]})
            print("[DAILY] Reset sessions_today counters")
        except Exception as e:
            print(f"[DAILY] Reset failed: {e}")


app = FastAPI(title="JAT-AI API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(providers_router)
app.include_router(github_router)
app.include_router(jules_router)
app.include_router(chat_router)
app.include_router(repos_router)
app.include_router(execute_router)
app.include_router(conversations_router)
app.include_router(settings_router)
app.include_router(usage_router)
app.include_router(plans_router)


class PromptCreate(BaseModel):
    name: str
    content: str = ""
    format: str = "xml"


class PromptUpdate(BaseModel):
    content: str


@app.get("/api/prompts")
async def list_prompts():
    rows = await db.select("prompts")
    return {"prompts": [{"id": r.get("id") or r["name"], "name": r["name"], "content": r.get("content", ""), "source": r.get("source", "user")} for r in rows]}


@app.get("/api/prompts/system")
async def list_system_prompts():
    from prompts.system_prompts import (
        ASK_MODE_SYSTEM, PLAN_MODE_SYSTEM, BUILD_MODE_SYSTEM,
        AUTO_MODE_SYSTEM, JULES_MASTER_PROMPT, JULES_QUESTION_HANDLER,
        REVIEW_SESSION_PROMPT,
    )
    return {"prompts": [
        {"name": "ask-mode", "content": ASK_MODE_SYSTEM},
        {"name": "plan-mode", "content": PLAN_MODE_SYSTEM},
        {"name": "build-mode", "content": BUILD_MODE_SYSTEM},
        {"name": "auto-mode", "content": AUTO_MODE_SYSTEM},
        {"name": "jules-master", "content": JULES_MASTER_PROMPT},
        {"name": "jules-question-handler", "content": JULES_QUESTION_HANDLER},
        {"name": "review-session", "content": REVIEW_SESSION_PROMPT},
    ]}


@app.put("/api/prompts/system/{name}")
async def update_system_prompt(name: str, body: PromptUpdate):
    rows = await db.select("prompts", filters={"name": name, "source": "system"})
    if rows:
        await db.update("prompts", {"content": body.content}, {"name": name})
    else:
        await db.insert("prompts", {
            "name": name, "source": "system", "content": body.content, "format": "xml",
        })
    return {"ok": True}


@app.post("/api/prompts/system/{name}/reset")
async def reset_system_prompt(name: str):
    from prompts.system_prompts import (
        ASK_MODE_SYSTEM, PLAN_MODE_SYSTEM, BUILD_MODE_SYSTEM,
        AUTO_MODE_SYSTEM, JULES_MASTER_PROMPT, JULES_QUESTION_HANDLER,
        REVIEW_SESSION_PROMPT,
    )
    defaults = {
        "ask-mode": ASK_MODE_SYSTEM,
        "plan-mode": PLAN_MODE_SYSTEM,
        "build-mode": BUILD_MODE_SYSTEM,
        "auto-mode": AUTO_MODE_SYSTEM,
        "jules-master": JULES_MASTER_PROMPT,
        "jules-question-handler": JULES_QUESTION_HANDLER,
        "review-session": REVIEW_SESSION_PROMPT,
    }
    if name not in defaults:
        raise HTTPException(404, f"Unknown system prompt '{name}'")
    await db.delete("prompts", {"name": name, "source": "system"})
    return {"content": defaults[name]}


@app.get("/api/prompts/{name}")
async def get_prompt(name: str):
    rows = await db.select("prompts", filters={"name": name})
    if not rows:
        raise HTTPException(404, f"Prompt '{name}' not found")
    return rows[0]


@app.post("/api/prompts", status_code=201)
async def create_prompt(body: PromptCreate):
    existing = await db.select("prompts", filters={"name": body.name})
    if existing:
        raise HTTPException(409, f"Prompt '{body.name}' already exists")
    row = await db.insert("prompts", {
        "name": body.name,
        "source": "user",
        "content": body.content,
        "format": body.format,
    })
    return row


@app.put("/api/prompts/{name}")
async def update_prompt(name: str, body: PromptUpdate):
    rows = await db.select("prompts", filters={"name": name})
    if not rows:
        raise HTTPException(404, f"Prompt '{name}' not found")
    updated = await db.update("prompts", {"content": body.content}, {"name": name})
    return updated[0] if updated else {"ok": True}


@app.delete("/api/prompts/{name}")
async def delete_prompt(name: str):
    rows = await db.select("prompts", filters={"name": name})
    if not rows:
        raise HTTPException(404, f"Prompt '{name}' not found")
    if rows[0].get("source") == "system":
        raise HTTPException(403, "System prompts cannot be deleted")
    await db.delete("prompts", {"name": name})
    return {"ok": True}


# --- Agent tasks (terminals on the canvas) ---

@app.get("/api/terminals")
async def list_terminals():
    try:
        rows = await db.select("agent_tasks")
    except Exception:
        return []
    return [{
        "terminalId": r["id"],
        "label": r.get("prompt", "")[:40],
        "state": "live" if r["status"] == "running" else ("queued" if r["status"] == "pending" else "idle"),
        "tentacleId": f"{r['repo_owner']}/{r['repo_name']}",
        "tentacleName": r.get("prompt", "")[:30],
        "workspaceMode": "shared",
        "createdAt": r["created_at"],
        "agentRuntimeState": "processing" if r["status"] == "running" else "idle",
        "lifecycleState": "running" if r["status"] == "running" else ("registered" if r["status"] == "pending" else "exited"),
        "hasUserPrompt": True,
        "sessionId": r.get("session_id", ""),
    } for r in rows]


@app.delete("/api/agent-tasks/{task_id}")
async def delete_agent_task(task_id: str):
    await db.delete("agent_tasks", {"id": task_id})
    return {"ok": True}


@app.delete("/api/agent-tasks")
async def delete_all_agent_tasks():
    await db.delete("agent_tasks")
    return {"ok": True}


@app.get("/api/terminal-snapshots")
async def list_terminal_snapshots():
    return await list_terminals()


# --- Repos (tentacles on the canvas) ---

@app.get("/api/deck/tentacles")
async def list_tentacles():
    try:
        rows = await db.select("agent_tasks")
    except Exception:
        rows = []

    repos: dict[str, dict] = {}
    for r in rows:
        key = f"{r['repo_owner']}/{r['repo_name']}"
        if key not in repos:
            repos[key] = {
                "tentacleId": key,
                "displayName": key,
                "name": r["repo_name"],
                "description": key,
                "status": "idle",
                "color": "#7c3aed",
                "octopus": {"animation": "idle", "expression": "normal", "accessory": "none", "hairColor": None},
                "scope": {"paths": [key], "tags": []},
                "vaultFiles": [],
                "todoTotal": 0,
                "todoDone": 0,
                "todoItems": [],
                "suggestedSkills": [],
                "_has_running": False,
                "_has_pending": False,
            }
        repo = repos[key]
        repo["todoTotal"] += 1
        status = r.get("status", "pending")
        if status == "completed":
            repo["todoDone"] += 1
        elif status == "running":
            repo["_has_running"] = True
        elif status in ("pending", "blocked"):
            repo["_has_pending"] = True
        repo["todoItems"].append({
            "text": r.get("prompt", "")[:80],
            "done": status == "completed",
        })

    for repo in repos.values():
        if repo["todoDone"] == repo["todoTotal"] and repo["todoTotal"] > 0:
            repo["status"] = "idle"
            repo["octopus"]["animation"] = "sleeping"
            repo["octopus"]["expression"] = "sleepy"
        elif repo["_has_running"]:
            repo["status"] = "active"
            repo["octopus"]["animation"] = "working"
        elif repo["_has_pending"]:
            repo["status"] = "idle"
            repo["octopus"]["animation"] = "idle"
        del repo["_has_running"]
        del repo["_has_pending"]

    if not repos:
        fallback = await _fetch_jules_repos_as_tentacles()
        return list(fallback.values())
    return list(repos.values())


@app.get("/api/canvas/sessions")
async def list_canvas_sessions():
    try:
        tasks = await db.select("agent_tasks")
    except Exception:
        tasks = []

    sessions = []
    for t in tasks:
        is_done = t["status"] in ("completed", "failed")
        preview = t.get("prompt", "")[:60]
        sessions.append({
            "sessionId": t.get("session_id") or t["id"],
            "tentacleId": f"{t['repo_owner']}/{t['repo_name']}",
            "startedAt": t.get("created_at", ""),
            "endedAt": t.get("updated_at", "") if is_done else None,
            "lastEventAt": t.get("updated_at", ""),
            "eventCount": 1,
            "turnCount": 1,
            "userTurnCount": 1,
            "assistantTurnCount": 0,
            "firstUserTurnPreview": f"[done] {preview}" if is_done else preview,
            "lastUserTurnPreview": preview,
            "lastAssistantTurnPreview": t["status"],
        })

    return sessions


@app.get("/api/claude/usage")
async def get_usage():
    accounts = await db.select("accounts")
    total_daily = sum(a.get("max_daily_tasks", 0) for a in accounts)
    active_count = len([a for a in accounts if a.get("enabled")])

    # Query Jules API for real today's session count across all accounts
    sessions_today = await _count_today_sessions(accounts)

    # Sync the local counter with reality
    if accounts and sessions_today > 0:
        try:
            best = accounts[0]
            await db.update("accounts", {"sessions_today": sessions_today}, {"id": best["id"]})
        except Exception:
            pass

    pct = int((sessions_today / total_daily) * 100) if total_daily > 0 else 0
    return {
        "status": "ok",
        "fetchedAt": "connected",
        "source": "cli-pty",
        "planType": "ultra" if total_daily >= 300 else ("pro" if total_daily >= 100 else "free"),
        "primaryUsedPercent": pct,
        "primaryResetAt": None,
        "secondaryUsedPercent": active_count,
        "secondaryResetAt": None,
        "extraUsageCostUsed": sessions_today,
        "extraUsageCostLimit": total_daily,
        "message": f"{sessions_today}/{total_daily} daily sessions | {active_count} account{'s' if active_count != 1 else ''}",
    }


async def _count_today_sessions(accounts: list[dict]) -> int:
    """Query Jules API with each account key and count sessions created today."""
    from datetime import datetime, timezone
    from core.ai_interface import KeyVault
    vault = KeyVault(settings.encryption_key)

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    total = 0

    for acc in accounts:
        if not acc.get("enabled"):
            continue
        encrypted = acc.get("api_key_encrypted", "")
        if not encrypted:
            continue
        try:
            key = vault.decrypt(encrypted)
        except Exception:
            key = encrypted
        if not key:
            continue

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.get(
                    "https://jules.googleapis.com/v1alpha/sessions?pageSize=100",
                    headers={"X-Goog-Api-Key": key},
                )
            if res.status_code != 200:
                continue
            for s in res.json().get("sessions", []):
                create_time = s.get("createTime", "")
                if create_time.startswith(today):
                    total += 1
        except Exception:
            continue

    return total


@app.get("/api/ui-state")
async def get_ui_state():
    return {
        "activePrimaryNav": 1,
        "sidebarWidth": 260,
        "isAgentsSidebarVisible": True,
        "isRuntimeStatusStripVisible": True,
        "isBottomTelemetryVisible": False,
        "isMonitorVisible": True,
        "minimizedTerminalIds": [],
        "isActiveAgentsSectionExpanded": True,
        "isClaudeUsageSectionExpanded": True,
        "isCodexUsageSectionExpanded": False,
        "terminalCompletionSound": "none",
        "canvasOpenTerminalIds": [],
        "canvasOpenTentacleIds": [],
        "canvasTerminalsPanelWidth": None,
    }


@app.put("/api/ui-state")
async def put_ui_state():
    return {"ok": True}


@app.patch("/api/ui-state")
async def patch_ui_state():
    return {"ok": True}


@app.get("/api/setup")
async def get_setup():
    return {"shouldShowSetupCard": False, "steps": []}


@app.get("/api/codex/usage")
async def get_codex_usage():
    return {"status": "unavailable", "source": "none"}


async def _fetch_jules_repos_as_tentacles() -> dict[str, dict]:
    jules_key = await _get_jules_key() or ""
    if not jules_key:
        return {}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.get(
                "https://jules.googleapis.com/v1alpha/sources",
                headers={"X-Goog-Api-Key": jules_key},
            )
        if res.status_code != 200:
            return {}
        sources = res.json().get("sources", [])
        repos: dict[str, dict] = {}
        for s in sources:
            gh = s.get("gitHubRepo", {})
            name = gh.get("repoName", "")
            owner = gh.get("repoOwner", "")
            if not name or not owner:
                continue
            key = f"{owner}/{name}"
            repos[key] = {
                "tentacleId": key,
                "displayName": key,
                "name": name,
                "description": key,
                "status": "idle",
                "color": "#7c3aed",
                "octopus": {"animation": "sway", "expression": "normal", "accessory": "none", "hairColor": None},
                "scope": {"paths": [key], "tags": []},
                "vaultFiles": [],
                "todoTotal": 0,
                "todoDone": 0,
                "todos": [],
                "suggestedSkills": [],
            }
        return repos
    except (httpx.ReadTimeout, httpx.ConnectTimeout):
        return {}


async def _fetch_jules_sessions_all_accounts() -> tuple[dict[str, list[dict]], set[str]]:
    """Query all enabled Jules accounts and aggregate sessions by date."""
    from core.ai_interface import KeyVault
    vault = KeyVault(settings.encryption_key)

    sessions_by_date: dict[str, list[dict]] = {}
    projects: set[str] = set()

    try:
        accounts = await db.select("accounts")
    except Exception:
        accounts = []

    for acc in accounts:
        if not acc.get("enabled"):
            continue
        encrypted = acc.get("api_key_encrypted", "")
        if not encrypted:
            continue
        try:
            key = vault.decrypt(encrypted)
        except Exception:
            key = encrypted
        if not key:
            continue

        page_token = None
        while True:
            try:
                params: dict[str, str] = {"pageSize": "100"}
                if page_token:
                    params["pageToken"] = page_token
                async with httpx.AsyncClient(timeout=15.0) as client:
                    res = await client.get(
                        "https://jules.googleapis.com/v1alpha/sessions",
                        headers={"X-Goog-Api-Key": key},
                        params=params,
                    )
                if res.status_code != 200:
                    break
                data = res.json()
                for s in data.get("sessions", []):
                    date = s.get("createTime", "")[:10]
                    if not date:
                        continue
                    source = s.get("sourceContext", {}).get("source", "")
                    repo = source.replace("sources/github/", "") if source else "unknown"
                    projects.add(repo)
                    if date not in sessions_by_date:
                        sessions_by_date[date] = []
                    sessions_by_date[date].append({
                        "repo": repo,
                        "account": acc.get("name", ""),
                        "state": s.get("state", ""),
                        "title": s.get("title", ""),
                    })
                page_token = data.get("nextPageToken")
                if not page_token:
                    break
            except (httpx.ReadTimeout, httpx.ConnectTimeout):
                break

    return sessions_by_date, projects


@app.get("/api/analytics/usage-heatmap")
async def get_usage_heatmap():
    from datetime import datetime, timezone, timedelta
    now = datetime.now(timezone.utc)

    sessions_by_date, projects = await _fetch_jules_sessions_all_accounts()

    # Only include last 30 days
    cutoff = (now - timedelta(days=30)).strftime("%Y-%m-%d")
    days: list[dict] = []
    total_sessions = 0
    total_days_active = 0

    for i in range(30):
        date = (now - timedelta(days=29 - i)).strftime("%Y-%m-%d")
        day_sessions = sessions_by_date.get(date, [])
        day_projects: dict[str, int] = {}
        for s in day_sessions:
            day_projects[s["repo"]] = day_projects.get(s["repo"], 0) + 1
        count = len(day_sessions)
        total_sessions += count
        if count > 0:
            total_days_active += 1
        days.append({
            "date": date,
            "totalTokens": count,
            "sessions": count,
            "projects": [{"key": k, "tokens": v} for k, v in day_projects.items()] if day_projects else [{"key": "none", "tokens": 0}],
            "models": [{"key": "sessions", "tokens": count}],
        })

    all_projects = sorted(projects) if projects else ["none"]
    return {
        "days": days,
        "projects": all_projects,
        "models": ["sessions"],
        "totalSessions": total_sessions,
        "totalDaysActive": total_days_active,
    }


@app.get("/api/monitor/feed")
async def get_monitor_feed():
    return {"providerId": "x", "queryTerms": [], "posts": [], "isStale": False, "lastError": None}


@app.get("/api/monitor/config")
async def get_monitor_config():
    return {"providerId": "x", "queryTerms": [], "refreshPolicy": {"maxCacheAgeMs": 3600000, "maxPosts": 30, "searchWindowDays": 7}, "providers": {}}


@app.get("/api/code-intel/events")
async def get_code_intel():
    return {"events": []}


@app.get("/api/deck/skills")
async def get_deck_skills():
    return []


@app.post("/api/terminals")
async def post_terminals():
    return {"ok": True}


@app.put("/api/deck/tentacles/{tentacle_id}")
async def put_tentacle(tentacle_id: str):
    return {"ok": True}


@app.post("/api/deck/tentacles")
async def post_tentacle():
    return {"ok": True}
