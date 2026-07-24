from __future__ import annotations

from uuid import UUID

import structlog
from cryptography.fernet import Fernet

from clients.ai_providers import AIProviderPool, ProviderAccount, ProviderType
from clients.database import Database

log = structlog.get_logger()


class KeyVault:
    """Encrypts/decrypts API keys using Fernet symmetric encryption.
    The encryption key lives in the backend's env, never in the database."""

    def __init__(self, encryption_key: str) -> None:
        if not encryption_key:
            self._fernet = None
            return
        try:
            self._fernet = Fernet(encryption_key.encode())
        except (ValueError, Exception):
            self._fernet = None

    def encrypt(self, plaintext: str) -> str:
        if not self._fernet:
            return plaintext
        return self._fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        if not self._fernet:
            return ciphertext
        return self._fernet.decrypt(ciphertext.encode()).decode()

    @staticmethod
    def generate_key() -> str:
        return Fernet.generate_key().decode()


class AIInterface:
    def __init__(
        self, supabase: Database, pool: AIProviderPool, vault: KeyVault
    ) -> None:
        self._db = supabase
        self._pool = pool
        self._vault = vault

    async def add_provider(
        self,
        provider_type: str,
        name: str,
        api_key: str,
        model: str = "",
        base_url: str = "",
        daily_limit: int = 0,
    ) -> dict:
        encrypted = self._vault.encrypt(api_key) if api_key else None
        row = await self._db.insert("ai_providers", {
            "provider_type": provider_type,
            "name": name,
            "api_key_encrypted": encrypted,
            "model": model,
            "base_url": base_url,
            "daily_limit": daily_limit,
            "enabled": True,
        })

        account = ProviderAccount(
            provider_type=ProviderType(provider_type),
            name=name,
            api_key=api_key,
            model=model,
            base_url=base_url,
        )
        self._pool.add_account(account)
        return row

    async def remove_provider(self, provider_id: str) -> None:
        rows = await self._db.select("ai_providers", filters={"id": provider_id})
        if rows:
            name = rows[0]["name"]
            try:
                account = self._pool.find_by_name(name)
                self._pool.remove_account(account.id)
            except ValueError:
                pass
        await self._db.delete("ai_providers", {"id": provider_id})

    async def list_providers(self) -> list[dict]:
        rows = await self._db.select("ai_providers")
        return [{
            "id": r["id"],
            "provider_type": r["provider_type"],
            "name": r["name"],
            "model": r["model"],
            "base_url": r["base_url"],
            "enabled": r["enabled"],
            "daily_limit": r["daily_limit"],
            "has_key": r["api_key_encrypted"] is not None,
        } for r in rows]

    async def load_providers_into_pool(self) -> None:
        """Called on startup to hydrate the in-memory pool from Supabase."""
        rows = await self._db.select("ai_providers", filters={"enabled": True})
        for r in rows:
            api_key = ""
            if r["api_key_encrypted"]:
                api_key = self._vault.decrypt(r["api_key_encrypted"])
            account = ProviderAccount(
                provider_type=ProviderType(r["provider_type"]),
                name=r["name"],
                api_key=api_key,
                model=r["model"],
                base_url=r["base_url"],
            )
            self._pool.add_account(account)
