from __future__ import annotations

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from config import load_settings
from core.ai_interface import KeyVault
from db import db

router = APIRouter()
settings = load_settings()
vault = KeyVault(settings.encryption_key)

PLAN_LIMITS = {
    "free": {"daily": 15, "concurrent": 3},
    "pro": {"daily": 100, "concurrent": 15},
    "ultra": {"daily": 300, "concurrent": 60},
}


class AccountCreate(BaseModel):
    name: str
    api_key: str
    plan_tier: str = "free"
    role: str = "worker"
    label: str = ""


class AccountPatch(BaseModel):
    enabled: bool | None = None
    plan_tier: str | None = None
    role: str | None = None
    label: str | None = None


@router.get("/api/jules/accounts")
async def list_accounts():
    try:
        rows = await db.select("accounts")
    except Exception:
        rows = []
    accounts = []
    for r in rows:
        tier = r.get("plan_tier", r.get("plan", "free"))
        limits = PLAN_LIMITS.get(tier, PLAN_LIMITS["free"])
        key_raw = r.get("api_key_encrypted", r.get("api_key", ""))
        masked = f"{key_raw[:4]}...{key_raw[-4:]}" if len(key_raw) > 8 else "****"
        accounts.append({
            "id": r["id"],
            "name": r.get("name", ""),
            "api_key_masked": masked,
            "plan_tier": tier,
            "role": r.get("role", "worker"),
            "label": r.get("label", ""),
            "daily_limit": limits["daily"],
            "concurrent_limit": limits["concurrent"],
            "sessions_today": r.get("sessions_today", 0),
            "enabled": bool(r.get("enabled", True)),
        })
    return {"accounts": accounts}


@router.post("/api/jules/accounts")
async def create_account(body: AccountCreate):
    if body.plan_tier not in PLAN_LIMITS:
        raise HTTPException(400, f"Invalid plan tier: {body.plan_tier}")
    limits = PLAN_LIMITS[body.plan_tier]
    encrypted = vault.encrypt(body.api_key)
    row = {
        "name": body.name,
        "api_key_encrypted": encrypted,
        "plan_tier": body.plan_tier,
        "plan": body.plan_tier,
        "role": body.role,
        "label": body.label,
        "enabled": True,
        "sessions_today": 0,
        "daily_limit": limits["daily"],
        "max_daily_tasks": limits["daily"],
    }
    try:
        await db.insert("accounts", row)
    except Exception as e:
        raise HTTPException(500, str(e))
    return {"ok": True}


@router.patch("/api/jules/accounts/{account_id}")
async def patch_account(account_id: str, body: AccountPatch):
    updates = {}
    if body.enabled is not None:
        updates["enabled"] = body.enabled
    if body.plan_tier is not None:
        if body.plan_tier not in PLAN_LIMITS:
            raise HTTPException(400, f"Invalid plan tier: {body.plan_tier}")
        updates["plan_tier"] = body.plan_tier
    if body.role is not None:
        updates["role"] = body.role
    if body.label is not None:
        updates["label"] = body.label
    if not updates:
        return {"ok": True}
    try:
        await db.update("accounts", updates, {"id": account_id})
    except Exception as e:
        raise HTTPException(500, str(e))
    return {"ok": True}


@router.delete("/api/jules/accounts/{account_id}")
async def delete_account(account_id: str):
    try:
        await db.delete("accounts", {"id": account_id})
    except Exception as e:
        raise HTTPException(500, str(e))
    return {"ok": True}


@router.get("/api/jules/accounts/{account_id}/test")
async def test_account(account_id: str):
    try:
        rows = await db.select("accounts")
    except Exception:
        raise HTTPException(500, "DB unavailable")
    row = next((r for r in rows if str(r["id"]) == account_id), None)
    if not row:
        raise HTTPException(404, "Account not found")
    key_raw = row.get("api_key_encrypted", row.get("api_key", ""))
    try:
        key = vault.decrypt(key_raw)
    except Exception:
        key = key_raw
    async with httpx.AsyncClient(timeout=15.0) as client:
        res = await client.get(
            "https://jules.googleapis.com/v1alpha/sources",
            headers={"X-Goog-Api-Key": key},
        )
    if res.status_code == 200:
        sources = res.json().get("sources", [])
        return {"ok": True, "sources_count": len(sources)}
    return {"ok": False, "error": f"HTTP {res.status_code}", "detail": res.text[:200]}


@router.get("/api/jules/sessions")
async def list_jules_sessions(repo: str | None = None):
    try:
        accounts = await db.select("accounts")
    except Exception:
        return {"sessions": []}

    all_sessions = []
    for acc in accounts:
        if not acc.get("enabled", True):
            continue
        key_raw = acc.get("api_key_encrypted", acc.get("api_key", ""))
        try:
            key = vault.decrypt(key_raw)
        except Exception:
            key = key_raw

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.get(
                    "https://jules.googleapis.com/v1alpha/sessions",
                    headers={"X-Goog-Api-Key": key},
                )
            if res.status_code == 200:
                sessions = res.json().get("sessions", [])
                for s in sessions:
                    s["_account_name"] = acc.get("name", "")
                    s["_account_id"] = str(acc["id"])
                all_sessions.extend(sessions)
        except Exception:
            continue

    if repo:
        owner, name = repo.split("/", 1) if "/" in repo else ("", repo)
        all_sessions = [
            s for s in all_sessions
            if s.get("repositoryOwner") == owner and s.get("repositoryName") == name
        ]

    all_sessions.sort(key=lambda s: s.get("createTime", ""), reverse=True)
    return {"sessions": all_sessions[:100]}


@router.get("/api/jules/sessions/{session_id}")
async def get_session_detail(session_id: str):
    try:
        accounts = await db.select("accounts")
    except Exception:
        raise HTTPException(404, "DB unavailable")

    for acc in accounts:
        key_raw = acc.get("api_key_encrypted", acc.get("api_key", ""))
        try:
            key = vault.decrypt(key_raw)
        except Exception:
            key = key_raw

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.get(
                    f"https://jules.googleapis.com/v1alpha/sessions/{session_id}",
                    headers={"X-Goog-Api-Key": key},
                )
            if res.status_code == 200:
                data = res.json()
                data["_account_name"] = acc.get("name", "")
                return data
        except Exception:
            continue

    raise HTTPException(404, "Session not found across any account")


@router.post("/api/jules/sessions/{session_id}/message")
async def send_session_message(session_id: str, body: dict):
    message = body.get("message", "")
    if not message:
        raise HTTPException(400, "Message required")

    try:
        accounts = await db.select("accounts")
    except Exception:
        raise HTTPException(500, "DB unavailable")

    for acc in accounts:
        key_raw = acc.get("api_key_encrypted", acc.get("api_key", ""))
        try:
            key = vault.decrypt(key_raw)
        except Exception:
            key = key_raw

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.post(
                    f"https://jules.googleapis.com/v1alpha/sessions/{session_id}:sendMessage",
                    headers={"X-Goog-Api-Key": key, "Content-Type": "application/json"},
                    json={"message": message},
                )
            if res.status_code == 200:
                return {"ok": True, "response": res.json()}
        except Exception:
            continue

    raise HTTPException(404, "Session not found or not in awaiting state")
