"""
Goal decomposer and DAG plan planner.

Responsibilities:
- Takes a high-level user objective and decomposes it into a parallelizable DAG plan of AgentTasks.

Coupling:
- Used during workflow instantiation.
"""


from __future__ import annotations

import json
from dataclasses import dataclass, field

import structlog

from clients.ai_providers import AIProviderPool

log = structlog.get_logger()

MAX_AGENTS_PER_PIPELINE = 5


@dataclass
class AgentSpec:
    index: int
    title: str
    description: str
    files_scope: list[str] = field(default_factory=list)
    acceptance_criteria: list[str] = field(default_factory=list)
    depends_on: list[int] = field(default_factory=list)
    branch_name: str = ""

    def __post_init__(self) -> None:
        if not self.branch_name:
            slug = self.title.lower().replace(" ", "-")[:30]
            self.branch_name = f"agent-{self.index}-{slug}"


@dataclass
class DecompositionResult:
    specs: list[AgentSpec]
    warnings: list[str] = field(default_factory=list)
    valid: bool = True


DECOMPOSE_SYSTEM = (
    "You are a task decomposition engine. Given a high-level task and optional repo context, "
    "break it into 2-5 parallel agent tasks. Each agent works on its own git branch.\n\n"
    "Output ONLY valid JSON with this structure:\n"
    '{"agents": [{"index": 1, "title": "...", "description": "...", '
    '"files_scope": ["src/auth/"], "acceptance_criteria": ["..."], "depends_on": []}]}\n\n'
    "Rules:\n"
    "- Max 5 agents\n"
    "- Minimize file scope overlap between agents\n"
    "- depends_on references other agent indices (for sequential work)\n"
    "- Each agent must be completable in a single session\n"
    "- Be specific about which files/directories each agent owns"
)


async def decompose_task(
    pool: AIProviderPool,
    account_name: str,
    task_description: str,
    repo_context: str = "",
) -> DecompositionResult:
    prompt = task_description
    if repo_context:
        prompt = f"REPO CONTEXT:\n{repo_context[:50000]}\n\nTASK:\n{task_description}"

    account = pool.find_by_name(account_name)
    raw = await pool.complete(prompt, account.id, system=DECOMPOSE_SYSTEM)

    return _parse_and_validate(raw)


def _parse_and_validate(raw: str) -> DecompositionResult:
    try:
        start = raw.index("{")
        end = raw.rindex("}") + 1
        data = json.loads(raw[start:end])
    except (ValueError, json.JSONDecodeError) as exc:
        return DecompositionResult(
            specs=[], warnings=[f"Failed to parse AI output: {exc}"], valid=False
        )

    agents_raw = data.get("agents", [])
    if not agents_raw:
        return DecompositionResult(
            specs=[], warnings=["AI returned no agents"], valid=False
        )

    if len(agents_raw) > MAX_AGENTS_PER_PIPELINE:
        return DecompositionResult(
            specs=[],
            warnings=[f"Too many agents ({len(agents_raw)}), max is {MAX_AGENTS_PER_PIPELINE}"],
            valid=False,
        )

    specs = [
        AgentSpec(
            index=a.get("index", i + 1),
            title=a.get("title", f"Agent {i + 1}"),
            description=a.get("description", ""),
            files_scope=a.get("files_scope", []),
            acceptance_criteria=a.get("acceptance_criteria", []),
            depends_on=a.get("depends_on", []),
        )
        for i, a in enumerate(agents_raw)
    ]

    warnings = _check_overlaps(specs) + _check_circular_deps(specs)
    valid = not any("CRITICAL" in w for w in warnings)

    return DecompositionResult(specs=specs, warnings=warnings, valid=valid)


def _check_overlaps(specs: list[AgentSpec]) -> list[str]:
    warnings: list[str] = []
    for i, a in enumerate(specs):
        for b in specs[i + 1:]:
            overlap = set(a.files_scope) & set(b.files_scope)
            if overlap:
                warnings.append(
                    f"CRITICAL: Agent {a.index} and {b.index} overlap on: {overlap}"
                )
    return warnings


def _check_circular_deps(specs: list[AgentSpec]) -> list[str]:
    indices = {s.index for s in specs}
    visited: set[int] = set()
    path: set[int] = set()
    deps_map = {s.index: s.depends_on for s in specs}

    def has_cycle(node: int) -> bool:
        if node in path:
            return True
        if node in visited:
            return False
        visited.add(node)
        path.add(node)
        for dep in deps_map.get(node, []):
            if dep in indices and has_cycle(dep):
                return True
        path.discard(node)
        return False

    for idx in indices:
        if has_cycle(idx):
            return ["CRITICAL: Circular dependency detected in agent specs"]
    return []
