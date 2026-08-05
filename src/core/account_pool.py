"""
Summary: Jules account pool manager.

What it does: Loads, tracks, and manages concurrency slots and daily budgets; sorts accounts by headroom score for balanced routing.

How it fits in: Used by 'src/core/workflow_engine.py' and 'src/core/coordinator.py'.
"""



from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4
from typing import TYPE_CHECKING

import structlog
from fastapi import Request

if TYPE_CHECKING:
    from core.context_store import ContextStore

from clients.jules import JulesClient
from exceptions import AccountPoolExhausted

log = structlog.get_logger()


class PlanTier(StrEnum):
    FREE = "free"
    PRO = "pro"
    ULTRA = "ultra"


class AccountRole(StrEnum):
    ORCHESTRATOR = "orchestrator"
    WORKER = "worker"
    QA = "qa"
    INTEGRATOR = "integrator"


PLAN_LIMITS: dict[PlanTier, dict[str, int]] = {
    PlanTier.FREE: {"daily_tasks": 15, "concurrent": 3},
    PlanTier.PRO: {"daily_tasks": 100, "concurrent": 15},
    PlanTier.ULTRA: {"daily_tasks": 300, "concurrent": 60},
}


@dataclass
class Account:
    id: UUID = field(default_factory=uuid4)
    name: str = ""
    api_key: str = ""
    plan: PlanTier = PlanTier.FREE
    role: AccountRole = AccountRole.WORKER
    label: str = ""
    active_sessions: int = 0
    daily_tasks_used: int = 0
    daily_reset_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    sources: list[str] = field(default_factory=list)
    enabled: bool = True

    @property
    def limits(self) -> dict[str, int]:
        return PLAN_LIMITS[self.plan]

    @property
    def has_capacity(self) -> bool:
        if not self.enabled:
            return False
        self._maybe_reset_daily()
        return (
            self.active_sessions < self.limits["concurrent"]
            and self.daily_tasks_used < self.limits["daily_tasks"]
        )

    def _maybe_reset_daily(self) -> None:
        now = datetime.now(UTC)
        elapsed = (now - self.daily_reset_at).total_seconds()
        if elapsed >= 86400:
            self.daily_tasks_used = 0
            self.daily_reset_at = now


class AccountPool:
    def __init__(self) -> None:
        self._accounts: list[Account] = []
        self._clients: dict[UUID, JulesClient] = {}

    def add_account(self, account: Account) -> None:
        self._accounts.append(account)
        self._clients[account.id] = JulesClient(account.api_key)
        log.info("account_added", name=account.name, plan=account.plan)

    def get_client(self, account_id: UUID) -> JulesClient:
        return self._clients[account_id]

    def has_capacity_for(self, source: str | None = None, role: AccountRole | None = None, assign_to: str | None = None) -> bool:
        eligible = [a for a in self._accounts if a.has_capacity]

        if role is not None:
            eligible = [a for a in eligible if a.role == role]

        if assign_to:
            eligible = [a for a in eligible if a.name == assign_to or a.label == assign_to]

        if source:
            with_source = [a for a in eligible if source in a.sources]
            if with_source:
                eligible = with_source

        return len(eligible) > 0

    def acquire(self, source: str | None = None, role: AccountRole | None = None, assign_to: str | None = None) -> Account:
        eligible = [a for a in self._accounts if a.has_capacity]

        if role is not None:
            eligible = [a for a in eligible if a.role == role]
            if not eligible:
                raise AccountPoolExhausted(f"No accounts available with role '{role}' and capacity")

        if assign_to:
            eligible = [a for a in eligible if a.name == assign_to or a.label == assign_to]
            if not eligible:
                raise AccountPoolExhausted(f"No accounts available with name or label '{assign_to}' and capacity")

        if source:
            with_source = [a for a in eligible if source in a.sources]
            if with_source:
                eligible = with_source

        if not eligible:
            raise AccountPoolExhausted("No accounts with available capacity")

        def get_sort_key(a: Account) -> tuple[float, int]:
            a._maybe_reset_daily()
            limits = PLAN_LIMITS[a.plan]
            daily_limit = limits["daily_tasks"]
            max_concurrent = limits["concurrent"]
            remaining_budget = daily_limit - a.daily_tasks_used

            # score = (remaining_daily_budget / daily_task_limit) - (active_sessions / max_concurrent)
            score = (remaining_budget / daily_limit) - (a.active_sessions / max_concurrent)

            # Sort descending by score, ascending by active_sessions as tie-breaker.
            # Python sorts tuples lexicographically, so returning (-score, a.active_sessions)
            # places higher score first, and then lower active_sessions first.
            return (-score, a.active_sessions)

        eligible.sort(key=get_sort_key)
        chosen = eligible[0]
        chosen.active_sessions += 1
        chosen.daily_tasks_used += 1
        log.info(
            "account_acquired",
            name=chosen.name,
            active=chosen.active_sessions,
            daily_used=chosen.daily_tasks_used,
            daily_limit=chosen.limits["daily_tasks"],
        )
        return chosen

    def release(self, account_id: UUID) -> None:
        for account in self._accounts:
            if account.id == account_id:
                account.active_sessions = max(0, account.active_sessions - 1)
                log.info("account_released", name=account.name, active=account.active_sessions)
                return

    def status(self) -> list[dict]:
        res = []
        for a in self._accounts:
            a._maybe_reset_daily()
            limits = PLAN_LIMITS[a.plan]
            daily_limit = limits["daily_tasks"]
            remaining_budget_fraction = (daily_limit - a.daily_tasks_used) / daily_limit
            res.append({
                "id": str(a.id),
                "name": a.name,
                "plan": a.plan,
                "role": a.role,
                "label": a.label,
                "active": a.active_sessions,
                "daily_used": a.daily_tasks_used,
                "daily_limit": daily_limit,
                "concurrent_limit": limits["concurrent"],
                "has_capacity": a.has_capacity,
                "sources": a.sources,
                "remaining_budget_fraction": remaining_budget_fraction,
            })
        return res

    def refresh(self, config: dict) -> None:
        """Re-syncs the account list from DB/config without discarding in-flight active_sessions."""
        from uuid import UUID

        from config import load_settings
        from core.account_pool import AccountRole, PlanTier
        from core.ai_interface import KeyVault
        from db import db

        vault = KeyVault(load_settings().encryption_key)
        try:
            rows = db.select_sync("accounts")
        except Exception as e:
            log.warning("refresh_accounts_db_error", error=str(e))
            return

        # Keep a map of current active accounts to preserve active_sessions and reset timestamps
        current_map = {a.id: a for a in self._accounts}
        new_accounts = []
        new_clients = {}

        for r in rows:
            if not r.get("enabled", True):
                continue
            acc_id = UUID(r["id"]) if isinstance(r["id"], str) else r["id"]

            try:
                decrypted_key = vault.decrypt(r["api_key_encrypted"]) if r.get("api_key_encrypted") else ""
            except Exception:
                decrypted_key = r.get("api_key_encrypted", "")

            tier_str = r.get("plan_tier", r.get("plan", "free")).lower()
            role_str = r.get("role", "worker").lower()

            if acc_id in current_map:
                # Update attributes while preserving active_sessions
                existing = current_map[acc_id]
                existing.name = r["name"]
                existing.api_key = decrypted_key
                existing.plan = PlanTier(tier_str)
                existing.role = AccountRole(role_str)
                existing.label = r.get("label", "")
                existing.daily_tasks_used = r.get("sessions_today", 0)
                new_accounts.append(existing)
                new_clients[acc_id] = self._clients.get(acc_id) or JulesClient(decrypted_key)
            else:
                # Add new account
                new_acc = Account(
                    id=acc_id,
                    name=r["name"],
                    api_key=decrypted_key,
                    plan=PlanTier(tier_str),
                    role=AccountRole(role_str),
                    label=r.get("label", ""),
                    daily_tasks_used=r.get("sessions_today", 0),
                )
                new_accounts.append(new_acc)
                new_clients[acc_id] = JulesClient(decrypted_key)

        # Close clients for accounts that were deleted
        for deleted_id in (set(self._clients.keys()) - set(new_clients.keys())):
            try:
                pass
            except Exception:
                pass

        self._accounts = new_accounts
        self._clients = new_clients
        log.info("account_pool_refreshed", count=len(self._accounts))

    async def get_client_for_session(self, session_id: str, store: ContextStore) -> JulesClient:
        """Looks up the account that owns the given session_id and returns its client."""
        row = await store.get_task_by_session(session_id)
        if not row:
            row = await store.get_orchestrator_session(session_id)
        if not row:
            raise KeyError(f"No task or session found with session_id '{session_id}'")

        account_id_str = row.get("account_id")
        if not account_id_str and "id" in row:
            task_row = await store.get_task_state(row["id"])
            if task_row:
                account_id_str = task_row.get("account_id")

        if not account_id_str:
            raise KeyError(f"No account_id associated with session_id '{session_id}'")

        from uuid import UUID
        account_id = UUID(account_id_str) if isinstance(account_id_str, str) else account_id_str
        return self.get_client(account_id)

    async def close_all(self) -> None:
        for client in self._clients.values():
            await client.close()
        self._clients.clear()


_pool_instance: AccountPool | None = None


def set_singleton_pool(pool: AccountPool) -> None:
    global _pool_instance
    _pool_instance = pool


def get_singleton_pool() -> AccountPool:
    global _pool_instance
    if _pool_instance is None:
        from core.config_loader import build_jules_pool, load_config
        config = load_config()
        _pool_instance = build_jules_pool(config)
    return _pool_instance


def get_account_pool(request: Request) -> AccountPool:
    return request.app.state.account_pool
