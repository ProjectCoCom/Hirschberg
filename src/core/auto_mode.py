"""
Auto-run orchestrator loop for standalone agent sessions.

Responsibilities:
- Parses goals, maintains loop state, and automatically proceeds with agent instructions.

Coupling:
- Integrates with 'src/core/ai_interface.py'.
"""


from __future__ import annotations

from dataclasses import dataclass, field

from api.chat import MODE_SYSTEM_PROMPTS, _call_provider, _decrypt_key, _get_enabled_keys
from config import load_settings
from core.plan_executor import parse_plan
from core.repomix import analyze_repo, get_cached_xml

settings = load_settings()


@dataclass
class AutoModeConfig:
    repo_owner: str
    repo_name: str
    goal: str
    provider_type: str
    model: str
    max_sessions: int = 10
    max_retries: int = 2
    timeout_minutes: int = 20
    execution_mode: str = "sequential"


@dataclass
class AutoModeState:
    status: str = "idle"
    sessions_used: int = 0
    plan_json: str = ""
    errors: list[str] = field(default_factory=list)
    interrupted: bool = False


async def _get_ai_key(provider_type: str) -> tuple[str, str]:
    keys = await _get_enabled_keys(provider_type)
    if not keys:
        raise RuntimeError(f"No enabled keys for {provider_type}")
    row = keys[0]
    api_key = _decrypt_key(row.get("api_key_encrypted", ""))
    return api_key, str(row["id"])


async def _ai_plan(config: AutoModeConfig, repo_xml: str) -> str:
    api_key, _ = await _get_ai_key(config.provider_type)
    system = MODE_SYSTEM_PROMPTS["plan"]
    prompt = (
        f"Goal: {config.goal}\n\n"
        f"Repo context (truncated):\n{repo_xml[:60000]}\n\n"
        "Create a plan with tasks. Output as JSON with a 'tasks' array. "
        f"Max {config.max_sessions} tasks. Execution mode: {config.execution_mode}."
    )
    messages = [{"role": "user", "content": prompt}]
    return await _call_provider(api_key, config.provider_type, config.model, messages, system)


async def _extract_plan_json(raw_response: str) -> str:
    import json

    from core.json_extract import extract_json_object
    data = extract_json_object(raw_response)
    if not isinstance(data, dict):
        raise ValueError("No valid JSON object found in AI response")
    return json.dumps(data)


async def _analyze_phase(config: AutoModeConfig, state: AutoModeState, token: str) -> str | None:
    repo_xml = get_cached_xml(config.repo_owner, config.repo_name)
    if not repo_xml:
        try:
            repo_xml = await analyze_repo(config.repo_owner, config.repo_name, token)
        except Exception as e:
            state.status = "failed"
            state.errors.append(f"Repomix failed: {e}")
            return None
    return repo_xml


async def _planning_phase(config: AutoModeConfig, state: AutoModeState, repo_xml: str) -> str | None:
    try:
        raw_plan = await _ai_plan(config, repo_xml)
        plan_json = await _extract_plan_json(raw_plan)
        state.plan_json = plan_json
        return plan_json
    except Exception as e:
        state.status = "failed"
        state.errors.append(f"Planning failed: {e}")
        return None


async def get_jules_key() -> str | None:
    from config import load_settings
    from core.ai_interface import KeyVault
    from db import db
    try:
        rows = await db.select("accounts")
    except Exception as e:
        log.error("unhandled_exception", error=str(e))
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
    except Exception as e:
        log.error("unhandled_exception", error=str(e))
        return encrypted


async def run_auto_mode(config: AutoModeConfig, state: AutoModeState) -> AutoModeState:
    state.status = "analyzing"
    token = settings.github_token
    if not token:
        state.status = "failed"
        state.errors.append("No GitHub token")
        return state

    repo_xml = await _analyze_phase(config, state, token)
    if not repo_xml:
        return state

    state.status = "planning"
    plan_json = await _planning_phase(config, state, repo_xml)
    if not plan_json:
        return state

    state.status = "executing"
    from core.config_loader import build_jules_pool, load_config
    config_data = load_config()
    pool = build_jules_pool(config_data)
    if not pool._accounts:
        await pool.close_all()
        state.status = "failed"
        state.errors.append("No enabled Jules API accounts configured")
        return state

    if state.interrupted:
        await pool.close_all()
        state.status = "interrupted"
        return state

    plan = parse_plan(plan_json, config.repo_owner, config.repo_name)
    plan.execution_mode = config.execution_mode

    from core.context_store import ContextStore
    from core.coordinator import AgentCoordinator
    from core.workflow_engine import WorkflowEngine
    from db import db
    from models.workflow import TaskStatus, WorkflowStatus

    try:
        await db.insert("workflows", {
            "id": str(plan.id),
            "name": plan.name,
            "description": plan.description,
            "status": str(plan.status),
            "execution_mode": plan.execution_mode,
        })
        for task in plan.tasks:
            task.workflow_id = plan.id
            await db.insert("agent_tasks", task.model_dump(mode="json"))
    except Exception as e:
        await pool.close_all()
        state.status = "failed"
        state.errors.append(f"Database persistence failed: {e}")
        return state

    store = ContextStore(db)
    coordinator = AgentCoordinator(pool, store)
    engine = WorkflowEngine(coordinator, store)

    try:
        plan = await engine.run(plan)
    except Exception as e:
        plan.status = WorkflowStatus.FAILED
        state.errors.append(f"Engine execution failed: {e}")
    finally:
        await db.update("workflows", {"status": str(plan.status)}, {"id": str(plan.id)})
        await pool.close_all()

    state.sessions_used = len([t for t in plan.tasks if t.session_id])

    for task in plan.tasks:
        try:
            db_task = await store.get_task_state(task.id)
            task.status = db_task.get("status", task.status)
            task.error = db_task.get("error", task.error)
        except Exception as e:
            log.error("unhandled_exception", error=str(e))
            pass

    failed = [t for t in plan.tasks if t.status != TaskStatus.COMPLETED]

    consecutive_failures = 0
    for t in plan.tasks:
        if t.status != TaskStatus.COMPLETED:
            consecutive_failures += 1
        else:
            consecutive_failures = 0

    if consecutive_failures >= 2:
        state.status = "paused"
        state.errors.append(f"Auto-paused: {consecutive_failures} consecutive failures")
        return state

    if failed:
        state.errors.extend(f"{t.id}: {t.error}" for t in failed)
        state.status = "partial"
    else:
        state.status = "completed"

    return state
