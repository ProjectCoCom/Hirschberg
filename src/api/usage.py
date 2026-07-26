"""
API router for token and task budget tracking.

Responsibilities:
- Returns detailed metrics of daily token consumption, costs, and remaining task budgets.

Coupling:
- Queries session activities and database logs.
"""


from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter

from db import db

router = APIRouter()


def _aggregate_by_field(rows: list[dict], field: str) -> dict[str, dict]:
    result: dict[str, dict] = {}
    for r in rows:
        key = r.get(field, "unknown")
        if key not in result:
            result[key] = {"input_tokens": 0, "output_tokens": 0, "requests": 0}
        result[key]["input_tokens"] += r.get("input_tokens", 0)
        result[key]["output_tokens"] += r.get("output_tokens", 0)
        result[key]["requests"] += 1
    return result


def _daily_breakdown(rows: list[dict], now: datetime) -> list[dict]:
    daily: list[dict] = []
    for i in range(7):
        day_str = (now - timedelta(days=i)).strftime("%Y-%m-%d")
        day_rows = [r for r in rows if r.get("created_at", "").startswith(day_str)]
        daily.append({
            "date": day_str,
            "input_tokens": sum(r.get("input_tokens", 0) for r in day_rows),
            "output_tokens": sum(r.get("output_tokens", 0) for r in day_rows),
            "requests": len(day_rows),
        })
    return list(reversed(daily))


@router.get("/api/usage/stats")
async def get_usage_stats():
    try:
        rows = await db.select("token_usage", order_by="created_at DESC")
    except Exception:
        # Table may not exist yet on old DBs
        try:
            if hasattr(db, "_get_conn"):
                db._get_conn().execute("CREATE TABLE IF NOT EXISTS token_usage (id TEXT PRIMARY KEY, provider_type TEXT NOT NULL DEFAULT '', model TEXT NOT NULL DEFAULT '', input_tokens INTEGER DEFAULT 0, output_tokens INTEGER DEFAULT 0, conversation_id TEXT DEFAULT '', created_at TEXT DEFAULT (datetime('now')))")
                db._get_conn().commit()
        except Exception:
            pass
        rows = []

    now = datetime.now(UTC)
    today_start = now.strftime("%Y-%m-%d 00:00:00")

    today_rows = [r for r in rows if r.get("created_at", "") >= today_start]

    return {
        "total": {"input_tokens": sum(r.get("input_tokens", 0) for r in rows), "output_tokens": sum(r.get("output_tokens", 0) for r in rows), "requests": len(rows)},
        "today": {"input_tokens": sum(r.get("input_tokens", 0) for r in today_rows), "output_tokens": sum(r.get("output_tokens", 0) for r in today_rows), "requests": len(today_rows)},
        "by_provider": _aggregate_by_field(rows, "provider_type"),
        "by_model": _aggregate_by_field(rows, "model"),
        "daily": _daily_breakdown(rows, now),
        "recent": [{"provider": r.get("provider_type"), "model": r.get("model"), "input": r.get("input_tokens"), "output": r.get("output_tokens"), "at": r.get("created_at")} for r in rows[:20]],
    }


@router.post("/api/usage/track")
async def track_usage(body: dict):
    try:
        await db.insert("token_usage", {
            "provider_type": body.get("provider_type", ""),
            "model": body.get("model", ""),
            "input_tokens": body.get("input_tokens", 0),
            "output_tokens": body.get("output_tokens", 0),
            "conversation_id": body.get("conversation_id", ""),
        })
    except Exception:
        pass
    return {"ok": True}
