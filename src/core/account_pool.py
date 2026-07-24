from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from uuid import UUID, uuid4

import structlog

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
    daily_reset_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
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
        now = datetime.now(timezone.utc)
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

        eligible.sort(key=lambda a: a.active_sessions)
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
        return [
            {
                "id": str(a.id),
                "name": a.name,
                "plan": a.plan,
                "role": a.role,
                "label": a.label,
                "active": a.active_sessions,
                "daily_used": a.daily_tasks_used,
                "daily_limit": a.limits["daily_tasks"],
                "concurrent_limit": a.limits["concurrent"],
                "has_capacity": a.has_capacity,
                "sources": a.sources,
            }
            for a in self._accounts
        ]

    async def close_all(self) -> None:
        for client in self._clients.values():
            await client.close()
        self._clients.clear()
