from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from config import load_settings
from db import db

router = APIRouter()

_SETTINGS_KEY = "summarizer_config"
_ROOT = Path(__file__).resolve().parent.parent.parent
_ENV_PATH = _ROOT / ".env"


class SummarizerConfig(BaseModel):
    mode: str = "free"
    provider: str = ""
    model: str = ""
    limit: int = 10


class AppSettingsPayload(BaseModel):
    github_token: str = ""
    github_fg_token: str = ""
    supabase_url: str = ""
    supabase_key: str = ""
    database_mode: str = "local"


class ResetPayload(BaseModel):
    targets: list[str] = []


@router.get("/api/settings/summarizer")
async def get_summarizer_settings():
    try:
        rows = await db.select("app_settings", filters={"key": _SETTINGS_KEY})
        if rows:
            return json.loads(rows[0].get("value", "{}"))
    except Exception:
        try:
            if hasattr(db, "_get_conn"):
                db._get_conn().execute(
                    "CREATE TABLE IF NOT EXISTS app_settings (key TEXT PRIMARY KEY, value TEXT NOT NULL DEFAULT '{}')"
                )
                db._get_conn().commit()
        except Exception:
            pass
    return {"mode": "free", "provider": "", "model": "", "limit": 10}


@router.post("/api/settings/summarizer")
async def save_summarizer_settings(body: SummarizerConfig):
    value = json.dumps(body.model_dump())
    try:
        existing = await db.select("app_settings", filters={"key": _SETTINGS_KEY})
        if existing:
            await db.update("app_settings", {"value": value}, {"key": _SETTINGS_KEY})
        else:
            await db.insert("app_settings", {"key": _SETTINGS_KEY, "value": value})
    except Exception:
        pass
    return {"ok": True}


@router.get("/api/settings/status")
async def get_settings_status():
    s = load_settings()
    return {
        "github_token": {"status": "active" if s.github_token else "missing"},
        "github_fg_token": {"status": "active" if s.github_fg_token else "missing"},
        "supabase": {"status": "active" if (s.supabase_url and s.supabase_key) else "missing"},
        "supabase_url": {"status": "active" if s.supabase_url else "missing"},
        "supabase_key": {"status": "active" if s.supabase_key else "missing"},
    }


def _mask(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "*" * len(value)
    return value[:4] + "*" * (len(value) - 8) + value[-4:]


async def _get_db_mode() -> str:
    try:
        rows = await db.select("app_settings", filters={"key": "database_mode"})
        if rows:
            return rows[0].get("value", "local")
    except Exception:
        pass
    return "local"


@router.get("/api/settings")
async def get_app_settings():
    s = load_settings()
    return {
        "github_token": _mask(s.github_token),
        "github_fg_token": _mask(s.github_fg_token),
        "supabase_url": s.supabase_url,
        "supabase_key": _mask(s.supabase_key),
        "encryption_key_status": "configured" if s.encryption_key else "missing",
        "database_mode": await _get_db_mode(),
    }


_ENV_KEY_RE = re.compile(r"^([A-Z_][A-Z0-9_]*)\s*=")


def _read_env() -> dict[str, str]:
    if not _ENV_PATH.exists():
        return {}
    out: dict[str, str] = {}
    for line in _ENV_PATH.read_text(encoding="utf-8").splitlines():
        m = _ENV_KEY_RE.match(line)
        if m:
            out[m.group(1)] = line.split("=", 1)[1] if "=" in line else ""
    return out


def _write_env(updates: dict[str, str]) -> None:
    """Write back .env preserving existing keys and comments. Updates override existing values."""
    if _ENV_PATH.exists():
        backup = _ENV_PATH.with_suffix(".env.bak")
        shutil.copy2(_ENV_PATH, backup)
        lines = _ENV_PATH.read_text(encoding="utf-8").splitlines()
    else:
        lines = []

    seen: set[str] = set()
    new_lines: list[str] = []
    for line in lines:
        m = _ENV_KEY_RE.match(line)
        if m and m.group(1) in updates:
            key = m.group(1)
            new_lines.append(f"{key}={updates[key]}")
            seen.add(key)
        else:
            new_lines.append(line)

    for key, value in updates.items():
        if key not in seen:
            new_lines.append(f"{key}={value}")

    _ENV_PATH.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


def _is_masked(value: str) -> bool:
    return "*" in value


@router.put("/api/settings")
async def update_app_settings(body: AppSettingsPayload):
    existing = _read_env()
    updates: dict[str, str] = {}
    incoming = body.model_dump()
    key_map = {
        "github_token": "GITHUB_TOKEN",
        "github_fg_token": "GITHUB_FG_TOKEN",
        "supabase_url": "SUPABASE_URL",
        "supabase_key": "SUPABASE_KEY",
    }
    for field, env_key in key_map.items():
        incoming_val = incoming.get(field, "")
        if not incoming_val or _is_masked(incoming_val):
            continue
        updates[env_key] = incoming_val

    if updates:
        _write_env(updates)

    try:
        mode = incoming.get("database_mode", "local")
        rows = await db.select("app_settings", filters={"key": "database_mode"})
        if rows:
            await db.update("app_settings", {"value": mode}, {"key": "database_mode"})
        else:
            await db.insert("app_settings", {"key": "database_mode", "value": mode})
    except Exception:
        pass

    return {"ok": True, "restart_required": bool(updates)}


def _migrate_encrypted_rows(old_key: str, new_key: str) -> tuple[int, int]:
    """Re-encrypt all stored API keys with a new Fernet key. Returns (migrated, failed)."""
    from core.ai_interface import KeyVault

    old_vault = KeyVault(old_key)
    new_vault = KeyVault(new_key)

    migrated = 0
    failed = 0

    conn = db._get_conn() if hasattr(db, "_get_conn") else None
    if conn is None:
        return 0, 0

    for table, id_col in (("ai_providers", "id"), ("accounts", "id")):
        try:
            rows = conn.execute(f"SELECT {id_col}, api_key_encrypted FROM {table}").fetchall()
        except Exception:
            continue
        for row in rows:
            encrypted = row["api_key_encrypted"] if isinstance(row, dict) or hasattr(row, "keys") else row[1]
            row_id = row[id_col] if isinstance(row, dict) else row[0]
            if not encrypted:
                continue
            try:
                plain = old_vault.decrypt(encrypted)
                new_encrypted = new_vault.encrypt(plain)
                conn.execute(f"UPDATE {table} SET api_key_encrypted = ? WHERE {id_col} = ?", (new_encrypted, row_id))
                migrated += 1
            except Exception:
                failed += 1
    conn.commit()
    return migrated, failed


@router.post("/api/settings/regenerate-key")
async def regenerate_encryption_key():
    from cryptography.fernet import Fernet

    current = load_settings().encryption_key
    if not current:
        new_key = Fernet.generate_key().decode()
        _write_env({"ENCRYPTION_KEY": new_key})
        return {"ok": True, "migrated": 0, "failed": 0, "restart_required": True}

    new_key = Fernet.generate_key().decode()
    migrated, failed = _migrate_encrypted_rows(current, new_key)
    if failed > 0 and migrated == 0:
        raise HTTPException(500, f"Migration failed: {failed} rows could not be re-encrypted with the new key")
    _write_env({"ENCRYPTION_KEY": new_key})
    return {"ok": True, "migrated": migrated, "failed": failed, "restart_required": True}


_RESET_ACTIONS: dict[str, dict] = {
    "ai_providers": {"type": "table", "table": "ai_providers"},
    "jules_accounts": {"type": "table", "table": "accounts"},
    "conversations": {"type": "tables", "tables": ["messages", "conversations"]},
    "custom_prompts": {"type": "filtered", "table": "prompts", "filters": {"source": "user"}},
    "system_prompt_overrides": {"type": "filtered", "table": "prompts", "filters": {"source": "system"}},
    "agent_tasks": {"type": "tables", "tables": ["session_activities", "agent_tasks"]},
    "workflows": {"type": "table", "table": "workflows"},
    "context_messages": {"type": "table", "table": "context_messages"},
    "merge_queue": {"type": "table", "table": "merge_queue"},
    "github_tokens": {"type": "env_clear", "keys": ["GITHUB_TOKEN", "GITHUB_FG_TOKEN"]},
    "env_keys": {
        "type": "env_clear",
        "keys": [
            "GITHUB_TOKEN",
            "GITHUB_FG_TOKEN",
            "SUPABASE_URL",
            "SUPABASE_KEY",
            "DEFAULT_REPO_OWNER",
            "DEFAULT_REPO_NAME",
        ],
    },
}


@router.post("/api/settings/reset")
async def reset_data(body: ResetPayload):
    cleared = []
    errors = []
    for target in body.targets:
        action = _RESET_ACTIONS.get(target)
        if not action:
            errors.append(f"unknown target: {target}")
            continue
        try:
            if action["type"] == "table":
                await db.delete(action["table"])
                cleared.append(target)
            elif action["type"] == "tables":
                for t in action["tables"]:
                    await db.delete(t)
                cleared.append(target)
            elif action["type"] == "filtered":
                await db.delete(action["table"], action["filters"])
                cleared.append(target)
            elif action["type"] == "env_clear":
                updates = {k: "" for k in action["keys"]}
                _write_env(updates)
                cleared.append(target)
        except Exception as e:
            errors.append(f"{target}: {e}")
    return {
        "ok": True,
        "cleared": cleared,
        "errors": errors,
        "restart_required": any(_RESET_ACTIONS.get(t, {}).get("type") == "env_clear" for t in cleared),
    }
