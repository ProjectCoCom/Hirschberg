from __future__ import annotations

from dataclasses import dataclass, field

from api.chat import _call_provider, _get_enabled_keys, _decrypt_key, MODE_SYSTEM_PROMPTS
from core.plan_executor import parse_plan
from core.repomix import analyze_repo, get_cached_xml
from config import load_settings

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
    start = raw_response.find("{")
    end = raw_response.rfind("}") + 1
    if start == -1 or end == 0:
        raise ValueError("No JSON found in AI response")
    return raw_response[start:end]


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
    jules_key = await get_jules_key()
    if not jules_key:
        state.status = "failed"
        state.errors.append("No Jules API key")
        return state

    if state.interrupted:
        state.status = "interrupted"
        return state

    from api.execute import _execute_sequential, _execute_parallel, _execute_hybrid
    plan = parse_plan(plan_json, config.repo_owner, config.repo_name)
    plan.execution_mode = config.execution_mode
    plan.max_sessions = config.max_sessions
    plan.timeout_minutes = config.timeout_minutes

    if config.execution_mode == "parallel":
        results = await _execute_parallel(plan, jules_key, token)
    elif config.execution_mode == "hybrid":
        results = await _execute_hybrid(plan, jules_key, token)
    else:
        results = await _execute_sequential(plan, jules_key, token)

    state.sessions_used = len(results)
    failed = [r for r in results if r.status != "completed"]

    consecutive_failures = 0
    for r in results:
        if r.status != "completed":
            consecutive_failures += 1
        else:
            consecutive_failures = 0
    if consecutive_failures >= 2:
        state.status = "paused"
        state.errors.append(f"Auto-paused: {consecutive_failures} consecutive failures")
        return state

    if failed:
        state.errors.extend(f"{r.task_id}: {r.error}" for r in failed)
        state.status = "partial"
    else:
        state.status = "completed"

    return state
