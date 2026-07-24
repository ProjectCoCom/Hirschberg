from __future__ import annotations

import json
from pathlib import Path

import structlog

from clients.ai_providers import AIProviderPool, ProviderAccount, ProviderType
from core.account_pool import AccountPool, Account, PlanTier
from core.tracker import MonitorConfig

log = structlog.get_logger()

CONFIG_PATH = Path(__file__).parent.parent.parent / "config.json"


def load_config(path: Path = CONFIG_PATH) -> dict:
    if not path.exists():
        log.warning("config_not_found", path=str(path))
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def build_jules_pool(config: dict) -> AccountPool:
    pool = AccountPool()
    jules_cfg = config.get("jules", {})
    for acc in jules_cfg.get("accounts", []):
        if not acc.get("enabled", True):
            continue
        tier = PlanTier(acc.get("plan", "free").upper())
        pool.add_account(Account(
            name=acc["name"],
            api_key=acc.get("api_key", ""),
            plan=tier,
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
