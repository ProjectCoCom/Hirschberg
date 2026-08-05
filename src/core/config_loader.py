"""
Configuration loader with in-memory caching.

Responsibilities:
- Loads and caches database accounts and global configurations to eliminate redundant disk reads.

Coupling:
- Used by startup initialization and account pool loaders.
"""


from __future__ import annotations

import json
from pathlib import Path

import structlog

from clients.ai_providers import AIProviderPool, ProviderAccount, ProviderType
from core.account_pool import Account, AccountPool, PlanTier
from core.tracker import MonitorConfig

log = structlog.get_logger()

CONFIG_PATH = Path(__file__).parent.parent.parent / "config.json"

_CONFIG_CACHE: dict[Path, dict] = {}


def clear_config_cache() -> None:
    """Clears the in-memory configuration cache."""
    _CONFIG_CACHE.clear()


def load_config(path: Path = CONFIG_PATH) -> dict:
    abs_path = path.resolve() if path.exists() else path
    if abs_path in _CONFIG_CACHE:
        return _CONFIG_CACHE[abs_path]

    if not path.exists():
        log.warning("config_not_found", path=str(path))
        return {}
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
        _CONFIG_CACHE[abs_path] = data
        return data


def build_jules_pool(config: dict) -> AccountPool:
    from uuid import UUID

    from config import load_settings
    from core.account_pool import AccountPool, AccountRole
    from core.ai_interface import KeyVault
    from db import db

    pool = AccountPool()
    vault = KeyVault(load_settings().encryption_key)

    # 1. Fetch from database
    try:
        rows = db.select_sync("accounts")
    except Exception as e:
        log.warning("build_jules_pool_db_error", error=str(e))
        rows = []

    # 2. One-time migration if table is empty
    if not rows:
        jules_cfg = config.get("jules", {})
        config_accounts = jules_cfg.get("accounts", [])
        if config_accounts:
            log.info("build_jules_pool_migration_started", count=len(config_accounts))
            plan_limits_map = {
                "free": {"daily": 15, "concurrent": 3},
                "pro": {"daily": 100, "concurrent": 15},
                "ultra": {"daily": 300, "concurrent": 60},
            }
            for acc in config_accounts:
                if not acc.get("enabled", True):
                    continue
                tier_str = acc.get("plan", "free").lower()
                limits = plan_limits_map.get(tier_str, plan_limits_map["free"])
                encrypted = vault.encrypt(acc.get("api_key", "")) if acc.get("api_key") else ""

                db_acc = {
                    "name": acc["name"],
                    "api_key_encrypted": encrypted,
                    "plan_tier": tier_str,
                    "plan": tier_str,
                    "role": acc.get("role", "worker").lower(),
                    "label": acc.get("label", ""),
                    "enabled": 1,
                    "sessions_today": 0,
                    "max_daily_tasks": limits["daily"],
                    "max_concurrent": limits["concurrent"],
                }
                try:
                    db.insert_sync("accounts", db_acc)
                except Exception as e:
                    log.warning("migration_insert_failed", name=acc["name"], error=str(e))

            # Select again after insertion
            try:
                rows = db.select_sync("accounts")
            except Exception as e:
                log.error("unhandled_exception", error=str(e))
                rows = []

    # 3. Load accounts from DB rows into pool
    for r in rows:
        if not r.get("enabled", True):
            continue
        try:
            decrypted_key = vault.decrypt(r["api_key_encrypted"]) if r.get("api_key_encrypted") else ""
        except Exception as e:
            log.error("unhandled_exception", error=str(e))
            decrypted_key = r.get("api_key_encrypted", "")

        tier_str = r.get("plan_tier", r.get("plan", "free")).lower()
        role_str = r.get("role", "worker").lower()

        pool.add_account(Account(
            id=UUID(r["id"]) if isinstance(r["id"], str) else r["id"],
            name=r["name"],
            api_key=decrypted_key,
            plan=PlanTier(tier_str),
            role=AccountRole(role_str),
            label=r.get("label", ""),
        ))
    return pool


def build_ai_pool(config: dict) -> AIProviderPool:
    pool = AIProviderPool()
    ai_cfg = config.get("ai_providers", {})
    for acc in ai_cfg.get("accounts", []):
        if not acc.get("enabled", True):
            continue
        provider_type = ProviderType(acc["provider"])
        account = ProviderAccount(
            provider_type=provider_type,
            name=acc["name"],
            api_key=acc.get("api_key", ""),
            model=acc.get("model", ""),
            base_url=acc.get("base_url", ""),
        )
        pool.add_account(account)
    return pool


def build_monitor_config(config: dict) -> MonitorConfig:
    mon_cfg = config.get("monitor", {})
    return MonitorConfig(
        poll_interval=mon_cfg.get("poll_interval", 15),
        stale_threshold=mon_cfg.get("stale_threshold", 600),
        max_cached_activities=mon_cfg.get("max_cached_activities", 200),
    )


def get_workflow_settings(config: dict) -> dict:
    return config.get("workflows", {})


def get_prompt_settings(config: dict) -> dict:
    return config.get("prompts", {})




def get_github_settings(config: dict) -> dict:
    return config.get("github", {})
