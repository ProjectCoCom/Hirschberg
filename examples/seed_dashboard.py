"""
Dashboard seeding script.

Responsibilities:
- Seeds SQLite databases with initial active worker sessions, budgets, and mock tasks for testing dashboard renders.

Coupling:
- Used for development or manual verifications.
"""


# Usage: python examples/seed_dashboard.py
from __future__ import annotations

import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone

from dotenv import load_dotenv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
load_dotenv()

from clients.supabase import SupabaseClient


async def seed() -> None:
    db = SupabaseClient(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

    workflow_id = str(uuid.uuid4())
    task_1_id = str(uuid.uuid4())
    task_2_id = str(uuid.uuid4())
    task_3_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    tasks = [
        {
            "id": task_1_id,
            "workflow_id": workflow_id,
            "prompt": "Review the frontend code for accessibility issues and create a report.",
            "repo_owner": "iceyxsm",
            "repo_name": "Abhiacharyaji",
            "branch": "master",
            "status": "completed",
            "session_id": "sample-session-001",
            "pr_url": "https://github.com/iceyxsm/Abhiacharyaji/pull/1",
            "created_at": now,
        },
        {
            "id": task_2_id,
            "workflow_id": workflow_id,
            "prompt": "Review the API endpoints for security vulnerabilities.",
            "repo_owner": "iceyxsm",
            "repo_name": "AnyWebApi",
            "branch": "main",
            "status": "running",
            "session_id": "sample-session-002",
            "pr_url": "",
            "created_at": now,
        },
        {
            "id": task_3_id,
            "workflow_id": workflow_id,
            "prompt": "Create a consolidated improvement plan from the review results.",
            "repo_owner": "iceyxsm",
            "repo_name": "Abhiacharyaji",
            "branch": "master",
            "status": "pending",
            "session_id": "",
            "pr_url": "",
            "created_at": now,
        },
    ]

    for t in tasks:
        await db.upsert("agent_tasks", t)
        print(f"Inserted task: {t['status']} - {t['prompt'][:50]}")

    activities = [
        {
            "id": str(uuid.uuid4()),
            "task_id": task_1_id,
            "session_id": "sample-session-001",
            "activity_id": "act-001",
            "originator": "agent",
            "description": "Analyzing component tree for ARIA attributes",
            "activity_type": "progress_updated",
            "raw_data": {},
            "created_at": now,
        },
        {
            "id": str(uuid.uuid4()),
            "task_id": task_1_id,
            "session_id": "sample-session-001",
            "activity_id": "act-002",
            "originator": "agent",
            "description": "Generated plan with 4 steps",
            "activity_type": "plan_generated",
            "raw_data": {},
            "created_at": now,
        },
        {
            "id": str(uuid.uuid4()),
            "task_id": task_2_id,
            "session_id": "sample-session-002",
            "activity_id": "act-003",
            "originator": "agent",
            "description": "Scanning route handlers for injection vulnerabilities",
            "activity_type": "progress_updated",
            "raw_data": {},
            "created_at": now,
        },
    ]

    for a in activities:
        await db.upsert("session_activities", a)
        print(f"Inserted activity: {a['activity_type']} - {a['description'][:50]}")

    print("\nDone. Open the dashboard to see the data.")


if __name__ == "__main__":
    asyncio.run(seed())
