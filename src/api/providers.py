"""
API router for model providers (e.g., Anthropic, OpenAI).

Responsibilities:
- Lists available models, verifies API keys, and checks provider health.

Coupling:
- Uses 'src/clients/ai_providers.py'.
"""


from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from config import load_settings
from db import db

settings = load_settings()

router = APIRouter(prefix="/api/providers")

PROVIDER_DOCS = {
    "groq": "https://console.groq.com/docs",
    "google": "https://ai.google.dev/docs",
    "cloudflare": "https://developers.cloudflare.com/workers-ai",
    "openrouter": "https://openrouter.ai/docs",
    "ollama": "https://github.com/ollama/ollama/blob/main/docs/api.md",
    "cerebras": "https://docs.cerebras.ai",
    "cohere": "https://docs.cohere.com",
    "mistral": "https://docs.mistral.ai",
    "nvidia_nim": "https://docs.api.nvidia.com",
    "github_models": "https://docs.github.com/en/github-models",
    "huggingface": "https://huggingface.co/docs/api-inference",
    "sambanova": "https://docs.sambanova.ai",
    "fireworks": "https://docs.fireworks.ai",
    "nebius": "https://docs.nebius.ai",
    "hyperbolic": "https://docs.hyperbolic.xyz",
    "scaleway": "https://www.scaleway.com/en/docs/ai-data/generative-apis",
    "longcat": "https://longcat.chat/platform/docs",
}


class ProviderCreate(BaseModel):
    provider_type: str
    name: str
    api_key: str = ""
    model: str = ""
    base_url: str = ""
    daily_limit: int = 0


class ProviderToggle(BaseModel):
    enabled: bool


class TestChatRequest(BaseModel):
    model: str
    message: str


@router.get("")
async def list_providers():
    rows = await db.select(
        "ai_providers",
        columns="id, provider_type, name, model, base_url, enabled, daily_limit, api_key_encrypted",
    )
    return {"providers": [{
        "id": r["id"],
        "provider_type": r["provider_type"],
        "name": r["name"],
        "model": r["model"],
        "base_url": r["base_url"],
        "enabled": r["enabled"],
        "daily_limit": r["daily_limit"],
        "has_key": r["api_key_encrypted"] is not None,
    } for r in rows]}


@router.post("", status_code=201)
async def create_provider(body: ProviderCreate):
    try:
        from core.ai_interface import KeyVault
        vault = KeyVault(settings.encryption_key)
        encrypted = vault.encrypt(body.api_key) if body.api_key else None
        row = await db.insert("ai_providers", {
            "provider_type": body.provider_type,
            "name": body.name,
            "api_key_encrypted": encrypted,
            "model": body.model,
            "base_url": body.base_url,
            "daily_limit": body.daily_limit,
            "enabled": True,
        })
        return row
    except Exception as exc:
        raise HTTPException(500, f"Failed to add provider: {exc}")


@router.patch("/{provider_id}")
async def toggle_provider(provider_id: str, body: ProviderToggle):
    updated = await db.update(
        "ai_providers", {"enabled": body.enabled}, {"id": provider_id}
    )
    return updated[0] if updated else {"ok": True}


@router.delete("/{provider_id}")
async def delete_provider(provider_id: str):
    await db.delete("ai_providers", {"id": provider_id})
    return {"ok": True}


@router.get("/{provider_id}/docs")
async def get_provider_docs(provider_id: str):
    rows = await db.select("ai_providers", filters={"id": provider_id})
    if not rows:
        raise HTTPException(404, "Provider not found")
    url = PROVIDER_DOCS.get(rows[0]["provider_type"], "")
    return {"url": url}


@router.get("/{provider_id}/models")
async def get_provider_models(provider_id: str):
    try:
        rows = await db.select("ai_providers", filters={"id": provider_id})
    except Exception:
        return {"models": [], "limits": {}, "provider_type": "unknown", "error": "Database timeout"}
    if not rows:
        raise HTTPException(404, "Provider not found")
    row = rows[0]

    try:
        from core.ai_interface import KeyVault
        from clients.ai_providers import AIProviderPool, ProviderAccount, ProviderType, PROVIDER_LIMITS, DEFAULT_BASE_URLS

        vault = KeyVault(settings.encryption_key)
        try:
            api_key = vault.decrypt(row["api_key_encrypted"]) if row["api_key_encrypted"] else ""
        except Exception:
            api_key = row["api_key_encrypted"] or ""

        provider_type = ProviderType(row["provider_type"])
        base_url = DEFAULT_BASE_URLS.get(provider_type, "")

        pool = AIProviderPool()
        account = ProviderAccount(
            provider_type=provider_type,
            name=row["name"],
            api_key=api_key,
            model=row["model"],
            base_url=base_url,
        )
        pool.add_account(account)

        try:
            models = await pool.list_models(account.id, force_refresh=True)
        except Exception as model_err:
            models = []
            print(f"[models] fetch failed for {row['provider_type']}: {model_err}")

        limits = PROVIDER_LIMITS.get(provider_type, {})
        await pool.close()

        # Fall back to extracting model names from limits if API returned nothing
        if not models and "models" in limits and isinstance(limits["models"], dict):
            models = [{"id": name, "name": name} for name in limits["models"]]

        return {"models": models, "limits": limits, "provider_type": row["provider_type"]}
    except Exception as exc:
        print(f"[models] endpoint error for {provider_id}: {type(exc).__name__}: {exc}")
        return {"models": [], "limits": {}, "provider_type": row.get("provider_type", "unknown"), "error": str(exc)}


@router.post("/{provider_id}/test")
async def test_provider_chat(provider_id: str, body: TestChatRequest):
    rows = await db.select("ai_providers", filters={"id": provider_id})
    if not rows:
        raise HTTPException(404, "Provider not found")
    row = rows[0]

    from core.ai_interface import KeyVault
    from clients.ai_providers import AIProviderPool, ProviderAccount, ProviderType, DEFAULT_BASE_URLS

    vault = KeyVault(settings.encryption_key)
    try:
        stored = row["api_key_encrypted"] or ""
        # Supabase bytea columns return hex-escaped strings
        if stored.startswith("\\x"):
            stored = bytes.fromhex(stored[2:]).decode()
        api_key = vault.decrypt(stored) if stored else ""
    except Exception:
        api_key = row["api_key_encrypted"] or ""

    provider_type = ProviderType(row["provider_type"])
    pool = AIProviderPool()
    account = ProviderAccount(
        provider_type=provider_type,
        name=row["name"],
        api_key=api_key,
        model=body.model,
        base_url=DEFAULT_BASE_URLS.get(provider_type, ""),
    )
    pool.add_account(account)

    try:
        response = await pool.complete(body.message, account.id, system="You are a helpful assistant. Keep responses brief.")
        await pool.close()
        return {"response": response}
    except Exception as exc:
        await pool.close()
        err_str = str(exc)
        if "404" in err_str or "Not Found" in err_str:
            return {"error": f"Model '{body.model}' is not available. Try a different model."}
        raise HTTPException(500, f"Test failed: {exc}")
