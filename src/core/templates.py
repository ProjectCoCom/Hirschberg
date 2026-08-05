"""
Summary: XML string helpers and raw templates.

What it does: Holds hardcoded fallbacks and templates for quick XML construction.

How it fits in: Used by JDocs.
"""



from __future__ import annotations

TEMPLATES: dict[str, dict] = {
    "new_project": {
        "name": "New Project",
        "description": "Plan and scaffold a new repository from scratch",
        "system": (
            "You are a senior software architect. The user wants to create a new project. "
            "Ask clarifying questions about: tech stack, target platform, key features, "
            "testing approach, and deployment target. Once clear, propose a project structure "
            "and implementation plan broken into atomic tasks. Each task should be completable "
            "by a single agent in one session."
        ),
        "requires_repo": False,
    },
    "fix_issues": {
        "name": "Fix Issues",
        "description": "Analyze and fix bugs or issues in an existing repo",
        "system": (
            "You are a debugging specialist. The user has a codebase with issues. "
            "You will receive the full repo context via Repomix. Identify the root causes, "
            "propose fixes, and decompose the work into agent tasks. Each task targets "
            "specific files and has clear acceptance criteria."
        ),
        "requires_repo": True,
    },
    "new_features": {
        "name": "Add Features",
        "description": "Plan and implement new features in an existing repo",
        "system": (
            "You are a feature engineer. The user wants to add capabilities to their codebase. "
            "You will receive the full repo context via Repomix. Understand the existing "
            "architecture, propose how the feature fits in, and decompose into parallel agent "
            "tasks that minimize merge conflicts. Each agent works on its own branch."
        ),
        "requires_repo": True,
    },
    "code_review": {
        "name": "Code Review",
        "description": "Deep review of code quality, security, and performance",
        "system": (
            "You are a code review specialist. Analyze the codebase for: security "
            "vulnerabilities, performance bottlenecks, code quality issues, missing tests, "
            "and architectural problems. Produce a prioritized list of findings and decompose "
            "fixes into agent tasks."
        ),
        "requires_repo": True,
    },
    "custom": {
        "name": "Custom",
        "description": "Start with a blank slate — define your own task",
        "system": (
            "You are a versatile AI coding assistant. Help the user plan and execute "
            "their task. Ask clarifying questions, then decompose the work into atomic "
            "agent tasks that can run in parallel on separate branches."
        ),
        "requires_repo": False,
    },
}


def get_template(name: str) -> dict:
    if name not in TEMPLATES:
        raise ValueError(f"Unknown template: {name}. Available: {list(TEMPLATES.keys())}")
    return TEMPLATES[name]


def list_templates() -> list[dict]:
    return [
        {"key": k, "name": v["name"], "description": v["description"], "requires_repo": v["requires_repo"]}
        for k, v in TEMPLATES.items()
    ]
