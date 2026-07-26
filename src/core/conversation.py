"""
Session message history manager.

Responsibilities:
- Appends and retrieves message models for ongoing chats and records them in SQLite.

Coupling:
- Connected to backend chat endpoints.
"""


from __future__ import annotations

import structlog

from clients.ai_providers import AIProviderPool, ProviderAccount, ProviderType
from clients.database import Database

log = structlog.get_logger()


class ConversationManager:
    def __init__(self, supabase: Database, pool: AIProviderPool) -> None:
        self._db = supabase
        self._pool = pool

    async def create(
        self,
        provider_name: str,
        model: str = "",
        mode: str = "plan",
        repo_owner: str = "",
        repo_name: str = "",
        template: str = "",
        title: str = "New Conversation",
    ) -> dict:
        account = self._pool.find_by_name(provider_name)
        provider_rows = await self._db.select(
            "ai_providers", filters={"name": provider_name}
        )
        provider_id = provider_rows[0]["id"] if provider_rows else None

        row = await self._db.insert("conversations", {
            "title": title,
            "provider_id": provider_id,
            "model": model or account.model,
            "mode": mode,
            "repo_owner": repo_owner,
            "repo_name": repo_name,
            "template": template,
            "status": "active",
        })
        return row

    async def list_conversations(self, status: str = "active") -> list[dict]:
        return await self._db.select("conversations", filters={"status": status})

    async def get_history(self, conversation_id: str) -> list[dict]:
        rows = await self._db.select(
            "conversation_messages",
            filters={"conversation_id": conversation_id},
        )
        return sorted(rows, key=lambda r: r["created_at"])

    async def send_message(
        self,
        conversation_id: str,
        content: str,
        image_urls: list[str] | None = None,
    ) -> dict:
        conv_rows = await self._db.select(
            "conversations", filters={"id": conversation_id}
        )
        if not conv_rows:
            raise ValueError(f"Conversation {conversation_id} not found")
        conv = conv_rows[0]

        await self._db.insert("conversation_messages", {
            "conversation_id": conversation_id,
            "role": "user",
            "content": content,
            "image_urls": image_urls or [],
        })

        history = await self.get_history(conversation_id)
        account = self._pool.find_by_name(
            await self._resolve_provider_name(conv["provider_id"])
        )
        model = conv["model"] or account.model

        response = await self._call_with_history(account, model, history, image_urls)

        row = await self._db.insert("conversation_messages", {
            "conversation_id": conversation_id,
            "role": "assistant",
            "content": response,
        })
        return row

    async def _call_with_history(
        self,
        account: ProviderAccount,
        model: str,
        history: list[dict],
        image_urls: list[str] | None = None,
    ) -> str:
        if account.provider_type == ProviderType.GOOGLE:
            return await self._call_google_chat(account, model, history, image_urls)
        return await self._call_openai_chat(account, model, history, image_urls)

    async def _call_openai_chat(
        self,
        account: ProviderAccount,
        model: str,
        history: list[dict],
        image_urls: list[str] | None = None,
    ) -> str:
        messages = []
        for msg in history:
            entry: dict = {"role": msg["role"], "content": msg["content"]}
            if msg["role"] == "user" and msg.get("image_urls"):
                entry["content"] = self._build_multimodal_content(
                    msg["content"], msg["image_urls"]
                )
            messages.append(entry)

        if image_urls and messages and messages[-1]["role"] == "user":
            messages[-1]["content"] = self._build_multimodal_content(
                messages[-1]["content"] if isinstance(messages[-1]["content"], str) else "",
                image_urls,
            )

        import httpx
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{account.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {account.api_key}"},
                json={"model": model, "messages": messages, "max_tokens": 4000},
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]

    async def _call_google_chat(
        self,
        account: ProviderAccount,
        model: str,
        history: list[dict],
        image_urls: list[str] | None = None,
    ) -> str:
        contents = []
        for msg in history:
            role = "user" if msg["role"] == "user" else "model"
            parts: list[dict] = [{"text": msg["content"]}]
            if msg["role"] == "user" and msg.get("image_urls"):
                for url in msg["image_urls"]:
                    parts.append({"fileData": {"fileUri": url, "mimeType": "image/jpeg"}})
            contents.append({"role": role, "parts": parts})

        if image_urls and contents and contents[-1]["role"] == "user":
            for url in image_urls:
                contents[-1]["parts"].append(
                    {"fileData": {"fileUri": url, "mimeType": "image/jpeg"}}
                )

        import httpx
        url = (
            f"{account.base_url}/models/{model}:generateContent"
            f"?key={account.api_key}"
        )
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(url, json={"contents": contents})
            resp.raise_for_status()
            candidates = resp.json().get("candidates", [])
            if not candidates:
                raise ValueError("No candidates in Google response")
            return candidates[0]["content"]["parts"][0]["text"]

    def _build_multimodal_content(
        self, text: str, image_urls: list[str]
    ) -> list[dict]:
        parts: list[dict] = [{"type": "text", "text": text}]
        for url in image_urls:
            parts.append({
                "type": "image_url",
                "image_url": {"url": url},
            })
        return parts

    async def _resolve_provider_name(self, provider_id: str | None) -> str:
        if not provider_id:
            raise ValueError("Conversation has no provider set")
        rows = await self._db.select("ai_providers", filters={"id": provider_id})
        if not rows:
            raise ValueError(f"Provider {provider_id} not found")
        return rows[0]["name"]
