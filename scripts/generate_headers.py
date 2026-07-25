#!/usr/bin/env python3
"""
Python logic module 'Generate Headers'.

Responsibilities:
- Provides backend utility operations and core logical helper interfaces for 'Generate Headers'.

Coupling:
- Imported and utilized by surrounding backend structures.
"""


import os
import json
import sys

# Standardized exclusions
EXCLUSIONS = [
    "node_modules", ".venv", "site-packages", ".git", ".pytest_cache", "__pycache__", ".jules", "docs/map.json"
]
LOCK_FILES = ["uv.lock", "package-lock.json", "pnpm-lock.yaml"]

# Detailed high-quality custom metadata for key files
CUSTOM_METADATA = {
    # Backend server & utilities
    "src/db.py": (
        "Database connection and session management.",
        "Initializes the SQLite database engine, sets WAL mode, enforces foreign keys, and manages thread-local connection sessions.",
        "Used by 'src/clients/database.py' and across the API controllers to interact with the database."
    ),
    "src/exceptions.py": (
        "System-wide custom exception classes.",
        "Defines standard error classes (e.g., JATException, AccountPoolExhausted) to organize error handling.",
        "Imported by core managers, clients, and API handlers to raise and catch exceptions consistently."
    ),
    "src/config.py": (
        "Core application configuration loaded from the environment.",
        "Retrieves and exposes configurations like database URL, GitHub keys, and security credentials.",
        "Referenced by server launch and backend clients to get operational parameters."
    ),
    "src/cli.py": (
        "CLI entrypoint for running tasks and workflows.",
        "Handles command-line arguments, triggers workflow plan dispatches, and initializes the local environment.",
        "Depends on 'src/core/plan_executor.py' and 'src/core/workflow_engine.py' to run CLI operations."
    ),
    "src/cli_ai.py": (
        "Interactive AI-assisted CLI command runner.",
        "Implements command-line AI-assistant interactions, streaming completions, and workspace context parsing.",
        "Relies on 'src/core/ai_interface.py' to chat and stream responses to the CLI."
    ),
    "src/server_launcher.py": (
        "Launcher script to spin up the API server.",
        "Configures Uvicorn parameters, resolves host/port settings, and starts the FastAPI server instance.",
        "Depends on 'src/api/server.py' to run the actual FastAPI app."
    ),
    # Backend API Handlers
    "src/api/server.py": (
        "FastAPI application entrypoint and middleware setup.",
        "Instantiates the FastAPI app, configures CORS and JSON response overrides, and registers all feature routers.",
        "Relies on router modules in 'src/api/*.py' and database initialization."
    ),
    "src/api/chat.py": (
        "API router for interactive chat sessions.",
        "Manages chat message streams, historical message lookups, and direct user-facing AI chat completions.",
        "Uses 'src/core/conversation.py' and 'src/core/ai_interface.py'."
    ),
    "src/api/conversations.py": (
        "API router for conversation logs and history.",
        "Handles endpoints for creating, deleting, and fetching chat conversation models and transcripts.",
        "Communicates with local database client."
    ),
    "src/api/execute.py": (
        "API router for task and session execution.",
        "Triggers manual task dispatches, polls running session logs, and relays task feedback.",
        "Integrates with 'src/core/session_runner.py' and 'src/core/workflow_engine.py'."
    ),
    "src/api/github.py": (
        "API router for GitHub repository integration.",
        "Exposes endpoints for listing files, branches, PRs, and triggers file-write or branch operations.",
        "Depends on 'src/clients/github.py'."
    ),
    "src/api/jules_accounts.py": (
        "API router for managing Jules account configurations.",
        "Handles CRUD operations for roles, labels, plans, and budget metrics on Jules accounts in SQLite.",
        "Queries and updates accounts via 'src/clients/database.py'."
    ),
    "src/api/plans.py": (
        "API router for parsing and managing agent workflow plans.",
        "Exposes endpoints for plan generation, DAG parsing, and standing orchestrator plan approvals.",
        "Connects with 'src/core/workflow_engine.py' and database."
    ),
    "src/api/providers.py": (
        "API router for model providers (e.g., Anthropic, OpenAI).",
        "Lists available models, verifies API keys, and checks provider health.",
        "Uses 'src/clients/ai_providers.py'."
    ),
    "src/api/repos.py": (
        "API router for workspace repository metadata.",
        "Manages target repo details and configurations for the agent runtime.",
        "Interacts with database."
    ),
    "src/api/settings.py": (
        "API router for workspace settings.",
        "Saves and retrieves global settings, recursion limits, and system configurations.",
        "Reads/writes settings via local database."
    ),
    "src/api/usage.py": (
        "API router for token and task budget tracking.",
        "Returns detailed metrics of daily token consumption, costs, and remaining task budgets.",
        "Queries session activities and database logs."
    ),
    # Clients
    "src/clients/github.py": (
        "High-level GitHub API client wrapper.",
        "Handles branch management, PR creation/merging, auto-retries for 5xx/429s, and file manipulation on GitHub.",
        "Tightly coupled to GitHub API endpoints and utilized across core engines."
    ),
    "src/clients/jules.py": (
        "HTTP client for interacting with Jules APIs.",
        "Manages connection sessions, runs workspace command executions, and fetches agent logs.",
        "Tightly coupled to Jules execution services."
    ),
    "src/clients/local_db.py": (
        "Low-level SQLite database client.",
        "Manages raw connection pools, implements JSON/Array serialization/deserialization transparently, and supports WAL.",
        "Foundation of data-access layer; wrapped by 'src/clients/database.py'."
    ),
    "src/clients/database.py": (
        "High-level database transaction helper.",
        "Exposes typed operations (e.g. select, insert, update) for accounts, sessions, tasks, and activities.",
        "Utilized by API endpoints and core state poller."
    ),
    "src/clients/ai_providers.py": (
        "Client factory for Anthropic, OpenAI, and other LLM services.",
        "Resolves API credentials, instantiates clients, and standardizes completion payloads.",
        "Foundation for 'src/core/ai_interface.py'."
    ),
    # Core Engine
    "src/core/account_pool.py": (
        "Jules account pool manager.",
        "Loads, tracks, and manages concurrency slots and daily budgets; sorts accounts by headroom score for balanced routing.",
        "Used by 'src/core/workflow_engine.py' and 'src/core/coordinator.py'."
    ),
    "src/core/adaptive_context.py": (
        "RAG and adaptive workspace context builder.",
        "Indexes files, trims overly long file contexts, and compiles relevant context snippets for agents.",
        "Depends on 'src/core/rag_store.py'."
    ),
    "src/core/ai_interface.py": (
        "Structured interface for LLM calls.",
        "Executes non-streaming and streaming LLM completion requests across various model backends.",
        "Relies on 'src/clients/ai_providers.py'."
    ),
    "src/core/auto_merge.py": (
        "Automated PR merger with checks validation.",
        "Monitors CI status with adaptive backoff, and safely merges PRs with retry-protected API calls.",
        "Uses 'src/clients/github.py'."
    ),
    "src/core/auto_mode.py": (
        "Auto-run orchestrator loop for standalone agent sessions.",
        "Parses goals, maintains loop state, and automatically proceeds with agent instructions.",
        "Integrates with 'src/core/ai_interface.py'."
    ),
    "src/core/config_loader.py": (
        "Configuration loader with in-memory caching.",
        "Loads and caches database accounts and global configurations to eliminate redundant disk reads.",
        "Used by startup initialization and account pool loaders."
    ),
    "src/core/context_compressor.py": (
        "Text and context compressor helper.",
        "Compresses excessive token streams and long histories to keep agent contexts within model limits.",
        "Assists prompt construction."
    ),
    "src/core/context_store.py": (
        "Context store for tracking task dependencies.",
        "Batch-queries dependency context messages in a single query to maintain scalable context forwarding.",
        "Feeds context into 'src/core/prompt_builder.py'."
    ),
    "src/core/conversation.py": (
        "Session message history manager.",
        "Appends and retrieves message models for ongoing chats and records them in SQLite.",
        "Connected to backend chat endpoints."
    ),
    "src/core/conversation_summarizer.py": (
        "LLM-based conversation summarization helper.",
        "Shrinks long chat transcripts into concise summaries to save context window tokens.",
        "Invoked by conversation manager."
    ),
    "src/core/coordinator.py": (
        "Task coordinator for running multi-step agent workflows.",
        "Coordinates task runs, creates git branches, builds prompts, handles pool exhaustions, and notifies orchestrators.",
        "Heart of task-dispatch system; couples with WorkflowEngine."
    ),
    "src/core/decomposer.py": (
        "Goal decomposer and DAG plan planner.",
        "Takes a high-level user objective and decomposes it into a parallelizable DAG plan of AgentTasks.",
        "Used during workflow instantiation."
    ),
    "src/core/jdocs.py": (
        "JDOCS prompt template manager.",
        "Compiles XML structures and manages prompt templates for agent context, rules, and history.",
        "Utilized by 'src/core/prompt_builder.py'."
    ),
    "src/core/logging.py": (
        "Structured logger setup.",
        "Configures structlog, console formatters, and outputs logs to server.log.",
        "Base utility used by every backend module."
    ),
    "src/core/merge_review.py": (
        "Evaluator for pull request merge reviews.",
        "Performs pre-merge checks and orchestrates QA evaluations.",
        "Used by 'src/core/auto_merge.py'."
    ),
    "src/core/orchestrator_relay.py": (
        "Feedback relay loop between workers and orchestrators.",
        "Coordinates multi-turn message exchanges when a worker session requires interactive feedback.",
        "Used by 'src/core/coordinator.py'."
    ),
    "src/core/plan_executor.py": (
        "Script-level plan executor.",
        "Triggers serial plan run execution for manual plans.",
        "Used by legacy CLI runner."
    ),
    "src/core/prompt_builder.py": (
        "Builder for agent system and user prompts with template caching.",
        "Interpolates rules, anti-patterns, and environment details into an integrated agent prompt.",
        "Core component for session initialization."
    ),
    "src/core/qa_reviewer.py": (
        "Automated QA reviewer gatekeeper.",
        "Spins up a QA review session to validate changes on completed branches and parses verdict blocks.",
        "Mandatory step prior to pull request merge."
    ),
    "src/core/rag_store.py": (
        "Simple text vector store for codebase RAG.",
        "Embeds text fragments, retrieves nearest matches, and supports localized codebase searches.",
        "Backing store for 'src/core/adaptive_context.py'."
    ),
    "src/core/repomix.py": (
        "Repomix file tree compiler.",
        "Packages files in the workspace into a structured format for LLM processing.",
        "Used by context compilation tools."
    ),
    "src/core/session_limiter.py": (
        "Session rate and limit guard.",
        "Enforces max durations and active session counts to avoid runaway loops.",
        "Integrates with session execution loops."
    ),
    "src/core/session_poller.py": (
        "Shared adaptive polling engine.",
        "Centralizes polling for both tasks and standalone sessions using adaptive backoff and jitter.",
        "Direct replacement of scattered thread-loops."
    ),
    "src/core/session_runner.py": (
        "Runner for standalone agent sessions.",
        "Sets up, runs, and monitors standalone agent tasks from creation through completion.",
        "Connected to API execution endpoints."
    ),
    "src/core/state_recovery.py": (
        "Crash recovery state manager.",
        "Scans SQLite for crashed/hanging tasks on startup and moves them to failed states cleanly.",
        "Runs at backend startup."
    ),
    "src/core/templates.py": (
        "XML string helpers and raw templates.",
        "Holds hardcoded fallbacks and templates for quick XML construction.",
        "Used by JDocs."
    ),
    "src/core/think_block.py": (
        "Thinking block XML parser.",
        "Extracts '<thought>' blocks from raw LLM responses to isolate reasoning from code output.",
        "Used by 'src/core/ai_interface.py'."
    ),
    "src/core/tracker.py": (
        "Realtime state and activity tracker.",
        "Maintains pub/sub mechanism to broadcast session updates and writes activity logs using custom database indexes.",
        "Supplies real-time events to React dashboard."
    ),
    "src/core/workflow_engine.py": (
        "Multi-task parallel workflow engine.",
        "Orchestrates parallel DAG task executions, manages integration branches, and coordinates multi-agent merges.",
        "Orchestrates coordinator, AutoMerge, and QAReviewer."
    ),
    # MCP
    "src/mcp/server.py": (
        "Model Context Protocol (MCP) server.",
        "Defines async-native tool functions and allows external tools/agents to safely inspect databases and coordinate tasks.",
        "Exposes tools to MCP clients."
    ),
    # SQL Schemas
    "supabase/schema.sql": (
        "Supabase-compatible PostgreSQL schema definitions.",
        "Defines tables, triggers, and views for the remote workspace database layout.",
        "Kept for reference and documentation of schema structure."
    ),
    "supabase/schema_local.sql": (
        "Local SQLite schema definition.",
        "Establishes SQLite database tables, indexes, busy timeouts, and WAL configuration.",
        "Used to initialize 'data/jat.db' database instances."
    ),
    # Scripts
    "scripts/install.sh": (
        "Unix setup and installation shell script.",
        "Installs python requirements and configures NPM/PNPM frontend packages.",
        "Main environment setup script."
    ),
    "scripts/install.bat": (
        "Windows setup and installation batch script.",
        "Installs python dependencies and configures PNPM packages on Windows.",
        "Windows equivalent of install.sh."
    ),
    "scripts/jat.sh": (
        "Unix CLI command wrapper.",
        "Executes the python-based JAT commands on Unix machines.",
        "CLI command script."
    ),
    "scripts/jat.bat": (
        "Windows CLI command wrapper.",
        "Executes the python-based JAT commands on Windows machines.",
        "Windows equivalent of jat.sh."
    ),
    # Configurations
    "config.example.json": (
        "Configuration template file.",
        "Details standard settings, recursion limits, default models, and provider keys for the agent workspace.",
        "Template for creating actual 'config.json' instances."
    ),
    "pyproject.toml": (
        "Python project metadata and dev dependency settings.",
        "Defines project dependencies, packaging configuration, entrypoints, and Pytest/Ruff environments.",
        "Core configuration used by uv, pip, and Pytest."
    ),
    "dashboard/package.json": (
        "React dashboard NPM packages and scripts.",
        "Directs frontend dependency downloads, Vite build operations, and dev server configurations.",
        "Key build manifest for pnpm."
    ),
    "dashboard/tsconfig.json": (
        "TypeScript project compiler configurations.",
        "Specifies module resolution, typing paths, and target output specifications for frontend source code.",
        "Governs TypeScript checking during development and Vite builds."
    ),
    "dashboard/vite.config.ts": (
        "Vite bundler configuration.",
        "Configures development port, asset proxies, and bundling plugins for building dashboard assets.",
        "Used by pnpm build/dev commands."
    ),
    "dashboard/index.html": (
        "Main HTML template for React dashboard.",
        "Provides mount target and scripts injection for Vite SPA.",
        "Standard entry point for frontend web server."
    ),
    "dashboard/api-mock.mjs": (
        "Mock server script for dashboard API prototyping.",
        "Spins up an express/node API mock serving pre-packaged dummy metrics and tasks data.",
        "Used to prototype UI views without running a full SQLite server backend."
    ),
    "dashboard/OCTOGENT_ADAPTATION.md": (
        "Documentation detailing adaptation details.",
        "Documents design choices for porting dashboards and terminal snapshot displays.",
        "Helpful reference for UI state management."
    ),
    "dashboard/dead-code-audit.md": (
        "Dead-code audit documentation.",
        "Details findings and cleanups from historical audits on components.",
        "Provides guidelines for UI cleanliness."
    ),
    "examples/seed_dashboard.py": (
        "Dashboard seeding script.",
        "Seeds SQLite databases with initial active worker sessions, budgets, and mock tasks for testing dashboard renders.",
        "Used for development or manual verifications."
    ),
    "examples/workflow_parallel.json": (
        "Sample workflow JSON schema.",
        "Details structured parallel/dependent multi-task agent workflow instructions.",
        "Used as standard target input for workflow engine test dispatches."
    )
}

def clean_name(path_or_file: str) -> str:
    # Get base name without extension and convert to friendly title
    base = os.path.basename(path_or_file)
    name_no_ext = os.path.splitext(base)[0]
    friendly = name_no_ext.replace("_", " ").replace("-", " ").title()
    return friendly

def get_metadata_for_file(filepath: str) -> tuple[str, str, str]:
    # Match custom metadata first
    if filepath in CUSTOM_METADATA:
        return CUSTOM_METADATA[filepath]

    # Otherwise, apply dynamic fallback rules based on directories and file types
    parts = filepath.split("/")
    filename = parts[-1]
    name_friendly = clean_name(filename)

    if "dashboard/src/components" in filepath:
        return (
            f"React UI component '{name_friendly}'.",
            f"Renders the '{name_friendly}' dashboard interface, manages localized state, and handles user actions.",
            f"Layout component rendered by parent dashboard containers; interacts with hooks and contexts from 'dashboard/src/app'."
        )
    elif "dashboard/src/app/hooks" in filepath:
        return (
            f"Custom React hook '{name_friendly}'.",
            f"Abstracts state management, data polling, or backend API actions for '{name_friendly}' into a reusable hook.",
            f"Consumed by React UI components inside the 'dashboard/src/components' component tree."
        )
    elif "dashboard/core/domain" in filepath:
        return (
            f"Domain model definitions for '{name_friendly}'.",
            f"Defines TypeScript interfaces, validation types, and helper algorithms for '{name_friendly}' model states.",
            f"Core domain logic consumed by application ports, adapters, and UI presentation views."
        )
    elif "dashboard/src/styles" in filepath:
        return (
            f"Custom CSS style sheet '{name_friendly}'.",
            f"Specifies UI class designs, responsive layouts, animations, and color scheme tokens.",
            f"Loaded by 'main.tsx' or 'App.tsx' to style React dashboard views."
        )
    elif "dryrun" in filepath and filepath.endswith(".py"):
        return (
            f"Dry-run integration test suite '{name_friendly}'.",
            f"Implements automated tests, mock execution environments, or workflow assertions to verify core features.",
            f"Triggered by pytest or CI workflows to guarantee codebase stability without making active live API requests."
        )

    # Generic extension-based fallback
    ext = os.path.splitext(filename)[1]
    if ext == ".py":
        return (
            f"Python logic module '{name_friendly}'.",
            f"Provides backend utility operations and core logical helper interfaces for '{name_friendly}'.",
            f"Imported and utilized by surrounding backend structures."
        )
    elif ext in [".ts", ".tsx", ".js", ".mjs"]:
        return (
            f"Frontend JavaScript/TypeScript module '{name_friendly}'.",
            f"Provides application-level UI helper functions, adapters, or configurations for '{name_friendly}'.",
            f"Used to build or bundle the React dashboard application."
        )
    elif ext == ".json":
        return (
            f"JSON configuration/data file '{name_friendly}'.",
            f"Maintains static metadata, options, or mock parameters for JAT-AI workspaces.",
            f"Read and parsed by backend configurations or frontend loaders."
        )
    elif ext == ".sql":
        return (
            f"SQL database scripts for '{name_friendly}'.",
            f"Handles database tables setup or seed actions on local or remote database instances.",
            f"Parsed and executed by the database client connection on setup."
        )

    return (
        f"Workspace file '{name_friendly}'.",
        f"Maintains specialized configuration, script, or template parameters.",
        f"Used by relevant backend/frontend build or runtime engines."
    )

# Writers for each file extension using 'summary' instead of 'filepath' as the first line
def write_python_header(filepath: str, summary: str, responsibilities: str, coupling: str):
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    header = f'"""\n{summary}\n\nResponsibilities:\n- {responsibilities}\n\nCoupling:\n- {coupling}\n"""'
    lines = content.splitlines(keepends=True)
    shebang_idx = -1
    coding_idx = -1
    for i, line in enumerate(lines[:3]):
        if line.startswith("#!"):
            shebang_idx = i
        elif "coding:" in line:
            coding_idx = i

    insert_at = max(shebang_idx, coding_idx) + 1
    rest = lines[insert_at:]
    rest_str = "".join(rest)

    if rest_str.strip().startswith('"""') or rest_str.strip().startswith("'''"):
        marker = '"""' if rest_str.strip().startswith('"""') else "'''"
        first_marker_pos = rest_str.find(marker)
        second_marker_pos = rest_str.find(marker, first_marker_pos + 3)
        if second_marker_pos != -1:
            new_rest = rest_str[second_marker_pos + 3:]
            # Make sure to keep any leading newline if needed, but clean it up
            if new_rest.startswith("\n"):
                new_rest = new_rest[1:]
            content = "".join(lines[:insert_at]) + header + "\n\n" + new_rest
        else:
            content = "".join(lines[:insert_at]) + header + "\n\n" + rest_str
    else:
        content = "".join(lines[:insert_at]) + header + "\n\n" + rest_str

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

def write_ts_header(filepath: str, summary: str, responsibilities: str, coupling: str):
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    header = f'/**\n * {summary}\n *\n * Responsibilities:\n * {responsibilities}\n *\n * Coupling:\n * {coupling}\n */'
    stripped = content.strip()
    if stripped.startswith("/**") or stripped.startswith("/*"):
        end_pos = content.find("*/")
        if end_pos != -1:
            rest = content[end_pos + 2:]
            if rest.startswith("\n"):
                rest = rest[1:]
            content = header + "\n\n" + rest
        else:
            content = header + "\n\n" + content
    else:
        content = header + "\n\n" + content

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

def write_css_header(filepath: str, summary: str, responsibilities: str, coupling: str):
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    header = f'/* {summary}\n *\n * Responsibilities:\n * {responsibilities}\n *\n * Coupling:\n * {coupling}\n */'
    stripped = content.strip()
    if stripped.startswith("/*"):
        end_pos = content.find("*/")
        if end_pos != -1:
            rest = content[end_pos + 2:]
            if rest.startswith("\n"):
                rest = rest[1:]
            content = header + "\n\n" + rest
        else:
            content = header + "\n\n" + content
    else:
        content = header + "\n\n" + content

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

def write_html_header(filepath: str, summary: str, responsibilities: str, coupling: str):
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    header = f'<!--\n  {summary}\n\n  Responsibilities:\n  {responsibilities}\n\n  Coupling:\n  {coupling}\n-->'
    stripped = content.strip()
    if stripped.startswith("<!--"):
        end_pos = content.find("-->")
        if end_pos != -1:
            rest = content[end_pos + 3:]
            if rest.startswith("\n"):
                rest = rest[1:]
            content = header + "\n\n" + rest
        else:
            content = header + "\n\n" + content
    else:
        content = header + "\n\n" + content

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

def write_sh_header(filepath: str, summary: str, responsibilities: str, coupling: str):
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    header_lines = [
        f"# {summary}",
        "#",
        f"# Responsibilities:",
        f"# {responsibilities}",
        "#",
        f"# Coupling:",
        f"# {coupling}"
    ]
    header = "\n".join(header_lines)
    lines = content.splitlines(keepends=True)
    shebang_idx = -1
    for i, line in enumerate(lines[:2]):
        if line.startswith("#!"):
            shebang_idx = i
            break
    insert_at = shebang_idx + 1
    rest_lines = lines[insert_at:]

    # Strip existing top comments if any
    while rest_lines and rest_lines[0].startswith("#"):
        rest_lines.pop(0)

    content = "".join(lines[:insert_at]) + header + "\n\n" + "".join(rest_lines)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

def write_bat_header(filepath: str, summary: str, responsibilities: str, coupling: str):
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    header_lines = [
        f"REM {summary}",
        "REM",
        f"REM Responsibilities:",
        f"REM {responsibilities}",
        "REM",
        f"REM Coupling:",
        f"REM {coupling}"
    ]
    header = "\n".join(header_lines)
    lines = content.splitlines(keepends=True)
    echo_idx = -1
    for i, line in enumerate(lines[:2]):
        if line.strip().lower() == "@echo off":
            echo_idx = i
            break
    insert_at = echo_idx + 1
    rest_lines = lines[insert_at:]

    while rest_lines and (rest_lines[0].startswith("REM") or rest_lines[0].startswith("::")):
        rest_lines.pop(0)

    content = "".join(lines[:insert_at]) + header + "\n\n" + "".join(rest_lines)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

def write_sql_header(filepath: str, summary: str, responsibilities: str, coupling: str):
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    header_lines = [
        f"-- {summary}",
        "--",
        f"-- Responsibilities:",
        f"-- {responsibilities}",
        "--",
        f"-- Coupling:",
        f"-- {coupling}"
    ]
    header = "\n".join(header_lines)
    lines = content.splitlines(keepends=True)
    while lines and lines[0].startswith("--"):
        lines.pop(0)

    content = header + "\n\n" + "".join(lines)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

def write_toml_header(filepath: str, summary: str, responsibilities: str, coupling: str):
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    header_lines = [
        f"# {summary}",
        "#",
        f"# Responsibilities:",
        f"# {responsibilities}",
        "#",
        f"# Coupling:",
        f"# {coupling}"
    ]
    header = "\n".join(header_lines)
    lines = content.splitlines(keepends=True)
    while lines and lines[0].startswith("#"):
        lines.pop(0)

    content = header + "\n\n" + "".join(lines)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

def write_json_header(filepath: str, summary: str, responsibilities: str, coupling: str):
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    try:
        data = json.loads(content)
    except Exception as e:
        print(f"Error parsing JSON in {filepath}: {e}")
        return

    desc_val = f"1. {summary} 2. {responsibilities} 3. {coupling}"
    if isinstance(data, dict):
        new_data = {"_description": desc_val}
        for k, v in data.items():
            if k != "_description":
                new_data[k] = v

        # Detect indentation
        indent = 2
        if "  " in content:
            indent = 2
        elif "    " in content:
            indent = 4

        new_content = json.dumps(new_data, indent=indent, ensure_ascii=False) + "\n"
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(new_content)

def apply_header_to_file(filepath: str):
    summary, resp, coup = get_metadata_for_file(filepath)
    ext = os.path.splitext(filepath)[1]

    if ext == ".py":
        write_python_header(filepath, summary, resp, coup)
    elif ext in [".ts", ".tsx", ".js", ".mjs"]:
        write_ts_header(filepath, summary, resp, coup)
    elif ext == ".css":
        write_css_header(filepath, summary, resp, coup)
    elif ext == ".html":
        write_html_header(filepath, summary, resp, coup)
    elif ext == ".sh":
        write_sh_header(filepath, summary, resp, coup)
    elif ext == ".bat":
        write_bat_header(filepath, summary, resp, coup)
    elif ext == ".sql":
        write_sql_header(filepath, summary, resp, coup)
    elif ext == ".toml":
        write_toml_header(filepath, summary, resp, coup)
    elif ext == ".json":
        write_json_header(filepath, summary, resp, coup)

def main():
    print("Scanning repository for hand-authored source and config files...")
    included_files = []

    for root, dirs, files in os.walk("."):
        # Apply exclusions to directories
        dirs[:] = [d for d in dirs if d not in EXCLUSIONS and not d.startswith(".")]

        for file in files:
            if file in LOCK_FILES:
                continue

            filepath = os.path.join(root, file)
            filepath = os.path.relpath(filepath, ".")

            # Additional exclusions check
            if any(ex in filepath for ex in EXCLUSIONS):
                continue

            # Exclude known binary and media types
            if file.endswith((".db", ".log", ".png", ".jpg", ".jpeg", ".webp", ".ico", ".md", ".xml")):
                continue

            ext = os.path.splitext(file)[1]
            if ext in [".py", ".json", ".sql", ".sh", ".bat", ".toml", ".ts", ".tsx", ".css", ".html", ".mjs"]:
                included_files.append(filepath)

    print(f"Found {len(included_files)} files to update.")
    for fp in sorted(included_files):
        print(f"Updating: {fp}")
        apply_header_to_file(fp)

    print("Part A: All files updated successfully with structured headers!")

if __name__ == "__main__":
    main()
