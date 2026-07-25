"""
Builder for agent system and user prompts with template caching.

Responsibilities:
- Interpolates rules, anti-patterns, and environment details into an integrated agent prompt.

Coupling:
- Core component for session initialization.
"""


from __future__ import annotations

from pathlib import Path

import structlog

log = structlog.get_logger()

PROMPTS_DIR = Path(__file__).parent.parent.parent / "prompts"


def build_session_prompt(
    task: str,
    dependency_context: list[dict] | None = None,
    plan_tier: str = "Ultra",
    daily_used: int = 0,
    daily_limit: int = 300,
    concurrent_used: int = 0,
    concurrent_limit: int = 60,
    account_name: str = "default",
) -> str:
    from core.config_loader import load_config, get_prompt_settings
    flags = get_prompt_settings(load_config())

    sections = []

    if flags.get("inject_rules", True):
        sections.append(_load_template("rules.xml"))
    if flags.get("inject_gates", True):
        sections.append(_load_template("gates.xml"))
    if flags.get("inject_anti_patterns", True):
        sections.append(_load_template("anti_patterns.xml"))
    if flags.get("inject_environment", True):
        environment = _load_template("environment.xml")
        environment = environment.replace("{plan_tier}", plan_tier)
        environment = environment.replace("{daily_used}", str(daily_used))
        environment = environment.replace("{daily_limit}", str(daily_limit))
        environment = environment.replace("{concurrent_used}", str(concurrent_used))
        environment = environment.replace("{concurrent_limit}", str(concurrent_limit))
        environment = environment.replace("{account_name}", account_name)
        sections.append(environment)

    if flags.get("inject_context", True) and dependency_context:
        context_template = _load_template("context.xml")
        context_body = _format_dependency_context(dependency_context)
        sections.append(context_template.replace("{dependency_context}", context_body))

    sections.append(f"---\n\nTASK:\n{task}")

    return "\n\n".join(sections)


def build_agent_xml_prompt(
    agent_index: int,
    total_agents: int,
    title: str,
    description: str,
    branch_name: str,
    files_scope: list[str],
    acceptance_criteria: list[str],
    repo_owner: str,
    repo_name: str,
    dependency_context: str = "",
    steps: str = "",
) -> str:
    template = _load_template("xml_agent_template.xml")
    scope_str = "\n      ".join(f"<file>{f}</file>" for f in files_scope)
    criteria_str = "\n      ".join(f"<criterion>{c}</criterion>" for c in acceptance_criteria)

    return (
        template
        .replace("{agent_index}", str(agent_index))
        .replace("{total_agents}", str(total_agents))
        .replace("{title}", title)
        .replace("{description}", description)
        .replace("{branch_name}", branch_name)
        .replace("{files_scope}", scope_str)
        .replace("{acceptance_criteria}", criteria_str)
        .replace("{repo_owner}", repo_owner)
        .replace("{repo_name}", repo_name)
        .replace("{dependency_context}", dependency_context or "None")
        .replace("{steps}", steps or "Follow the task description")
    )


_TEMPLATE_CACHE: dict[str, str] = {}


def clear_template_cache() -> None:
    """Clears the in-memory prompt template cache."""
    _TEMPLATE_CACHE.clear()


def _load_template(filename: str) -> str:
    if filename in _TEMPLATE_CACHE:
        return _TEMPLATE_CACHE[filename]

    path = PROMPTS_DIR / filename
    if not path.exists():
        log.warning("template_missing", file=filename)
        return ""

    content = path.read_text(encoding="utf-8").strip()
    _TEMPLATE_CACHE[filename] = content
    return content


def _format_dependency_context(contexts: list[dict]) -> str:
    lines = []
    for ctx in contexts:
        prompt = ctx.get("prompt", "unknown task")[:100]
        status = ctx.get("status", "unknown")
        pr_url = ctx.get("pr_url", "")
        entry = f"- [{status}] {prompt}"
        if pr_url:
            entry += f" | PR: {pr_url}"
        lines.append(entry)
    return "\n".join(lines) if lines else "No prior context available."
