"""
CLI entrypoint for running tasks and workflows.

Responsibilities:
- Handles command-line arguments, triggers workflow plan dispatches, and initializes the local environment.

Coupling:
- Depends on 'src/core/plan_executor.py' and 'src/core/workflow_engine.py' to run CLI operations.
"""


from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

# Ensure src/ is on path for bare imports used throughout the codebase
sys.path.insert(0, str(Path(__file__).resolve().parent))

import structlog

from config import load_settings, configure_logging
from clients.jules import JulesClient
from clients.github import GitHubClient
from db import db
from core.session_runner import run_session

log = structlog.get_logger()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="JAT - Jules Agent Tree")
    sub = parser.add_subparsers(dest="command")

    run_cmd = sub.add_parser("run", help="Create and track a Jules session")
    run_cmd.add_argument("--prompt", required=True, help="Task prompt for Jules")
    run_cmd.add_argument("--owner", help="Repo owner (overrides env)")
    run_cmd.add_argument("--repo", help="Repo name (overrides env)")
    run_cmd.add_argument("--branch", default="main")
    run_cmd.add_argument("--title", default="")
    run_cmd.add_argument("--api-key", help="Jules API key (overrides env)")
    run_cmd.add_argument("--auto-merge", action="store_true", help="Auto-merge PR after CI passes")
    run_cmd.add_argument("--merge-strategy", default="squash", choices=["squash", "merge", "rebase"])

    list_cmd = sub.add_parser("list-sessions", help="List Jules sessions")
    list_cmd.add_argument("--api-key", help="Jules API key (overrides env)")
    list_cmd.add_argument("--limit", type=int, default=10)

    sources_cmd = sub.add_parser("list-sources", help="List connected sources")
    sources_cmd.add_argument("--api-key", help="Jules API key (overrides env)")

    status_cmd = sub.add_parser("status", help="Get session status")
    status_cmd.add_argument("session_id")
    status_cmd.add_argument("--api-key", help="Jules API key (overrides env)")

    activities_cmd = sub.add_parser("activities", help="List session activities")
    activities_cmd.add_argument("session_id")
    activities_cmd.add_argument("--api-key", help="Jules API key (overrides env)")

    wf_cmd = sub.add_parser("workflow", help="Run a multi-task workflow from a JSON file")
    wf_cmd.add_argument("file", help="Path to workflow JSON file")
    wf_cmd.add_argument("--api-key", help="Jules API key (overrides env)")
    wf_cmd.add_argument("--auto-merge", action="store_true")
    wf_cmd.add_argument("--merge-strategy", default="squash", choices=["squash", "merge", "rebase"])

    prov_cmd = sub.add_parser("providers", help="Manage AI providers")
    prov_sub = prov_cmd.add_subparsers(dest="prov_action")
    prov_add = prov_sub.add_parser("add", help="Add a provider account")
    prov_add.add_argument("--type", required=True, choices=["groq", "google", "cloudflare", "openrouter", "ollama"])
    prov_add.add_argument("--name", required=True)
    prov_add.add_argument("--key", default="")
    prov_add.add_argument("--model", default="")
    prov_add.add_argument("--base-url", default="")
    prov_add.add_argument("--daily-limit", type=int, default=0)
    prov_sub.add_parser("list", help="List all providers")
    prov_rm = prov_sub.add_parser("remove", help="Remove a provider")
    prov_rm.add_argument("id", help="Provider ID to remove")

    chat_cmd = sub.add_parser("chat", help="Start or continue a conversation")
    chat_cmd.add_argument("--provider", required=True, help="Provider name")
    chat_cmd.add_argument("--model", default="")
    chat_cmd.add_argument("--mode", default="plan", choices=["plan", "direct"])
    chat_cmd.add_argument("--template", default="custom")
    chat_cmd.add_argument("--owner", default="")
    chat_cmd.add_argument("--repo", default="")
    chat_cmd.add_argument("--conversation-id", default="", help="Continue existing conversation")
    chat_cmd.add_argument("message", nargs="?", default="")

    tmpl_cmd = sub.add_parser("templates", help="List available prompt templates")

    decompose_cmd = sub.add_parser("decompose", help="Decompose a task into agent specs")
    decompose_cmd.add_argument("--provider", required=True, help="Provider name for AI")
    decompose_cmd.add_argument("--task", required=True, help="Task description")
    decompose_cmd.add_argument("--context", default="", help="Optional repo context file")

    return parser


async def run_task(settings, api_key: str, args) -> None:
    owner = args.owner or settings.default_repo_owner
    repo = args.repo or settings.default_repo_name

    if not owner or not repo:
        print("Repo owner and name required. Set DEFAULT_REPO_OWNER/DEFAULT_REPO_NAME in .env or pass --owner/--repo.")
        sys.exit(1)

    source = f"sources/github/{owner}/{repo}"
    jules = JulesClient(api_key)

    github = None
    if args.auto_merge and settings.github_token:
        github = GitHubClient(settings.github_token)

    try:
        result = await run_session(
            jules=jules,
            db=db,
            prompt=args.prompt,
            source=source,
            branch=args.branch,
            title=args.title,
            github=github,
            auto_merge=args.auto_merge,
            merge_strategy=args.merge_strategy,
        )
        print(json.dumps(result, indent=2))
    finally:
        await jules.close()
        if github:
            await github.close()


async def run_list_sessions(api_key: str, limit: int) -> None:
    client = JulesClient(api_key)
    try:
        sessions = await client.list_sessions(page_size=limit)
        for s in sessions:
            print(f"{s.id} | {s.title} | {s.state}")
    finally:
        await client.close()


async def run_list_sources(api_key: str) -> None:
    client = JulesClient(api_key)
    try:
        sources = await client.list_sources()
        for s in sources:
            print(f"{s.name} | {s.id}")
    finally:
        await client.close()


async def run_status(api_key: str, session_id: str) -> None:
    client = JulesClient(api_key)
    try:
        session = await client.get_session(session_id)
        print(json.dumps(session.model_dump(mode="json"), indent=2))
    finally:
        await client.close()


async def run_activities(api_key: str, session_id: str) -> None:
    client = JulesClient(api_key)
    try:
        activities = await client.list_activities(session_id)
        for a in activities:
            print(f"{a.originator} | {a.description}")
    finally:
        await client.close()


async def run_workflow(settings, api_key: str, args) -> None:
    import json as json_mod
    from core.account_pool import AccountPool, Account, PlanTier
    from core.context_store import ContextStore
    from core.coordinator import AgentCoordinator
    from core.workflow_engine import WorkflowEngine

    with open(args.file) as f:
        data = json_mod.load(f)

    pool = AccountPool()
    pool.add_account(Account(name="default", api_key=api_key, plan=PlanTier.ULTRA))

    store = ContextStore(db)
    coordinator = AgentCoordinator(pool, store)
    engine = WorkflowEngine(coordinator, store)

    workflow = _build_workflow(data, settings)

    log.info("workflow_starting", name=workflow.name, task_count=len(workflow.tasks))
    result = await engine.run(workflow)
    log.info("workflow_done", status=result.status)

    _print_workflow_result(result)
    await pool.close_all()


def _build_workflow(data: dict, settings) -> "Workflow":
    from uuid import UUID
    from models.workflow import AgentTask, Workflow

    tasks = []
    id_map: dict[str, UUID] = {}

    for t in data.get("tasks", []):
        task = AgentTask(
            prompt=t["prompt"],
            repo_owner=t.get("owner", settings.default_repo_owner),
            repo_name=t.get("repo", settings.default_repo_name),
            branch=t.get("branch", "main"),
        )
        id_map[t.get("name", str(task.id))] = task.id
        tasks.append((task, t.get("depends_on", [])))

    for task, dep_names in tasks:
        task.depends_on = [id_map[name] for name in dep_names if name in id_map]

    return Workflow(
        name=data.get("name", "workflow"),
        description=data.get("description", ""),
        tasks=[t for t, _ in tasks],
    )


def _print_workflow_result(result) -> None:
    import json as json_mod
    print(json_mod.dumps({
        "workflow_id": str(result.id),
        "status": result.status,
        "tasks": [
            {
                "id": str(t.id),
                "prompt": t.prompt[:60],
                "status": t.status,
                "pr_url": t.pr_url,
                "error": t.error,
            }
            for t in result.tasks
        ],
    }, indent=2))


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    settings = load_settings()
    configure_logging(settings.log_level)

    api_key = getattr(args, "api_key", None)
    if not api_key:
        from core.auto_mode import get_jules_key
        api_key = asyncio.run(get_jules_key())

    if not api_key:
        print("No Jules API key found. Add one via the dashboard APIs page or pass --api-key.")
        sys.exit(1)

    if args.command == "run":
        asyncio.run(run_task(settings, api_key, args))
    elif args.command == "list-sessions":
        asyncio.run(run_list_sessions(api_key, args.limit))
    elif args.command == "list-sources":
        asyncio.run(run_list_sources(api_key))
    elif args.command == "status":
        asyncio.run(run_status(api_key, args.session_id))
    elif args.command == "activities":
        asyncio.run(run_activities(api_key, args.session_id))
    elif args.command == "workflow":
        asyncio.run(run_workflow(settings, api_key, args))
    elif args.command == "providers":
        from cli_ai import run_providers
        asyncio.run(run_providers(settings, args))
    elif args.command == "chat":
        from cli_ai import run_chat
        asyncio.run(run_chat(settings, args))
    elif args.command == "templates":
        from cli_ai import run_templates
        asyncio.run(run_templates())
    elif args.command == "decompose":
        from cli_ai import run_decompose
        asyncio.run(run_decompose(settings, args))


if __name__ == "__main__":
    main()
