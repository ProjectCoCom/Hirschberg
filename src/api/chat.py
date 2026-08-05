"""
API router for interactive chat sessions.

Responsibilities:
- Manages chat message streams, historical message lookups, and direct user-facing AI chat completions.

Coupling:
- Uses 'src/core/conversation.py' and 'src/core/ai_interface.py'.
"""


from __future__ import annotations

import contextlib
import re

import structlog
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from config import load_settings
from core.adaptive_context import detect_referenced_chunks, get_boosted_results, record_chunk_usage
from core.context_compressor import compress_context
from core.conversation_summarizer import (
    build_ai_summarized_history,
    build_summarized_history,
    get_summarizer_config,
    should_summarize,
)
from core.rag_store import query_conversation_context, store_context, store_conversation_exchange
from db import db
from prompts.system_prompts import ASK_MODE_SYSTEM, AUTO_MODE_SYSTEM, BUILD_MODE_SYSTEM, PLAN_MODE_SYSTEM

log = structlog.get_logger()

router = APIRouter()
settings = load_settings()


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    provider_type: str
    model: str
    messages: list[ChatMessage]
    system: str = ""
    image_base64: str | None = None
    repo: str | None = None
    mode: str = "ask"
    conversation_id: str | None = None


MODE_SYSTEM_PROMPTS = {
    "ask": ASK_MODE_SYSTEM,
    "plan": PLAN_MODE_SYSTEM,
    "build": BUILD_MODE_SYSTEM,
    "auto": AUTO_MODE_SYSTEM,
}


class ChatResponse(BaseModel):
    response: str
    provider_id: str
    model: str
    tokens_used: int = 0


def _decrypt_key(stored: str) -> str:
    from core.ai_interface import KeyVault
    vault = KeyVault(settings.encryption_key)
    try:
        return vault.decrypt(stored)
    except Exception as e:
        log.error("unhandled_exception", error=str(e))
        return stored


async def _get_enabled_keys(provider_type: str) -> list[dict]:
    try:
        rows = await db.select("ai_providers", filters={"provider_type": provider_type, "enabled": True})
    except Exception as e:
        log.error("unhandled_exception", error=str(e))
        rows = []
    return rows


def _build_messages(request: ChatRequest) -> list[dict]:
    messages = []
    for msg in request.messages:
        if msg.role == "user" and request.image_base64 and msg == request.messages[-1]:
            messages.append({
                "role": "user",
                "content": [
                    {"type": "text", "text": msg.content},
                    {"type": "image_url", "image_url": {"url": request.image_base64}},
                ],
            })
        else:
            messages.append({"role": msg.role, "content": msg.content})
    return messages


async def _call_google(api_key: str, model: str, messages: list[dict], system: str) -> str:
    import httpx

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    contents = []
    for m in messages:
        parts = []
        if isinstance(m["content"], list):
            for part in m["content"]:
                if part["type"] == "text":
                    parts.append({"text": part["text"]})
                elif part["type"] == "image_url":
                    data = part["image_url"]["url"]
                    if data.startswith("data:"):
                        mime, b64 = data.split(";base64,", 1)
                        mime = mime.replace("data:", "")
                        parts.append({"inline_data": {"mime_type": mime, "data": b64}})
        else:
            parts.append({"text": m["content"]})
        role = "user" if m["role"] == "user" else "model"
        contents.append({"role": role, "parts": parts})

    body: dict = {"contents": contents}
    if system:
        body["systemInstruction"] = {"parts": [{"text": system}]}

    async with httpx.AsyncClient(timeout=60.0) as client:
        res = await client.post(url, json=body, headers={"Content-Type": "application/json"})
    if res.status_code == 429:
        raise RateLimitError("google")
    if res.status_code != 200:
        raise ProviderError(f"Google API {res.status_code}: {res.text[:200]}")
    data = res.json()
    return data["candidates"][0]["content"]["parts"][0]["text"]


async def _call_openai_compat(
    api_key: str,
    provider_type: str,
    model: str,
    messages: list[dict],
    system: str,
    custom_base_url: str = "",
) -> str:
    import httpx

    from clients.ai_providers import DEFAULT_BASE_URLS, ProviderType

    pt = ProviderType(provider_type)
    base_url = custom_base_url or DEFAULT_BASE_URLS.get(pt, "")
    if not base_url:
        raise ValueError(f"No base URL for provider: {provider_type}")

    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
    payload: dict = {"model": model, "messages": messages}
    if system:
        payload["messages"] = [{"role": "system", "content": system}] + payload["messages"]

    async with httpx.AsyncClient(timeout=60.0) as client:
        res = await client.post(f"{base_url}/chat/completions", json=payload, headers=headers)

    if res.status_code == 429:
        import asyncio
        await asyncio.sleep(3)
        async with httpx.AsyncClient(timeout=60.0) as client:
            res = await client.post(f"{base_url}/chat/completions", json=payload, headers=headers)
        if res.status_code == 429:
            raise RateLimitError(f"{provider_type}: {res.text[:100]}")
    if res.status_code == 404:
        raise ModelNotAvailableError(f"Model '{model}' is not available on {provider_type}. Try a different model.")
    if res.status_code != 200:
        raise ProviderError(f"{provider_type} API {res.status_code}: {res.text[:200]}")

    data = res.json()
    return data["choices"][0]["message"]["content"]


async def _call_provider(
    api_key: str,
    provider_type: str,
    model: str,
    messages: list[dict],
    system: str,
    custom_base_url: str = "",
) -> str:
    if provider_type == "google":
        return await _call_google(api_key, model, messages, system)
    return await _call_openai_compat(api_key, provider_type, model, messages, system, custom_base_url)


class RateLimitError(Exception):
    pass


class ProviderError(Exception):
    pass


class ModelNotAvailableError(Exception):
    pass


REPOMIX_TRIGGERS = {"rrpo", "repomix", "/repomix", "/rrpo", "rerepomix", "repomix-r", "r-repomix", "rmx"}

THINK_INSTRUCTION = """

<thinking>
You may use <think>...</think> blocks for internal reasoning.
Content inside think blocks will not be shown to the user but helps you work through complex problems step by step.
</thinking>

<context_saving>
If you discover important information worth remembering,
append [ACTION:SAVE_CONTEXT:content here] at the end of your response.
This saves the content to long-term memory for this repo.
</context_saving>"""


def _is_repomix_trigger(messages: list) -> bool:
    if not messages:
        return False
    last = messages[-1]
    content = last.content if hasattr(last, "content") else last.get("content", "")
    return content.strip().lower() in REPOMIX_TRIGGERS


async def _inject_available_skills(system: str) -> str:
    try:
        rows = await db.select("prompts")
        if not rows:
            return system
        skills_list = "\n".join(
            f"- {r['name']}: {r.get('content', '')[:80]}" for r in rows[:20]
        )
        skills_header = (
            "\n\n<available_skills>\n"
            "Assign these via prompt_id in your plan.\n"
            "The orchestrator will inject the full prompt content\n"
            "into each Jules session.\n"
        )
        return system + skills_header + skills_list + "\n</available_skills>"
    except Exception as e:
        log.error("unhandled_exception", error=str(e))
        return system


_SAVE_CONTEXT_PATTERN = re.compile(r"\[ACTION:SAVE_CONTEXT:(.*?)\]", re.DOTALL)
_PLAN_SAVE_PATTERN = re.compile(r"\[ACTION:PLAN_SAVE:(.*?)\|(.*\})\]", re.DOTALL)
_PLAN_UPDATE_PATTERN = re.compile(r"\[ACTION:PLAN_UPDATE:(.*?)\|(.*\})\]", re.DOTALL)
_PLAN_DELETE_PATTERN = re.compile(r"\[ACTION:PLAN_DELETE:(.*?)\]", re.DOTALL)


async def _handle_save_context(repo: str | None, response: str) -> None:
    if not repo:
        return
    matches = _SAVE_CONTEXT_PATTERN.findall(response)
    if not matches:
        return
    parts = repo.split("/", 1)
    if len(parts) != 2:
        return
    for content in matches:
        await store_context(parts[0], parts[1], content.strip(), metadata={"type": "ai_saved"})


async def _handle_plan_actions(conversation_id: str | None, response: str) -> None:
    if not conversation_id:
        return
    # PLAN_SAVE
    for title, plan_json in _PLAN_SAVE_PATTERN.findall(response):
        try:
            existing = await db.select("plans", filters={"conversation_id": conversation_id})
            if existing:
                await db.update(
                    "plans",
                    {"title": title.strip(), "plan_json": plan_json.strip(), "status": "draft"},
                    filters={"id": existing[0]["id"]},
                )
            else:
                await db.insert(
                    "plans",
                    {
                        "conversation_id": conversation_id,
                        "title": title.strip(),
                        "plan_json": plan_json.strip(),
                        "status": "draft",
                    },
                )
        except Exception as e:
            log.error("unhandled_exception", error=str(e))
            pass
    # PLAN_UPDATE
    for title, plan_json in _PLAN_UPDATE_PATTERN.findall(response):
        try:
            existing = await db.select("plans", filters={"conversation_id": conversation_id})
            if existing:
                await db.update(
                    "plans",
                    {"title": title.strip(), "plan_json": plan_json.strip()},
                    filters={"id": existing[0]["id"]},
                )
            else:
                await db.insert(
                    "plans",
                    {
                        "conversation_id": conversation_id,
                        "title": title.strip(),
                        "plan_json": plan_json.strip(),
                        "status": "draft",
                    },
                )
        except Exception as e:
            log.error("unhandled_exception", error=str(e))
            pass
    # PLAN_DELETE
    for _title in _PLAN_DELETE_PATTERN.findall(response):
        with contextlib.suppress(Exception):
            await db.delete("plans", filters={"conversation_id": conversation_id})


@router.post("/api/chat/send")
async def chat_send(request: ChatRequest):
    if _is_repomix_trigger(request.messages) and request.repo:
        from core.repomix import analyze_repo
        parts = request.repo.split("/", 1)
        if len(parts) == 2:
            token = settings.github_token
            try:
                xml = await analyze_repo(parts[0], parts[1], token)
                summary = f"Repo re-analyzed ({len(xml):,} chars). Fresh codebase context loaded."
                return ChatResponse(response=summary, provider_id="system", model="repomix")
            except Exception as e:
                return ChatResponse(response=f"Repomix failed: {e}", provider_id="system", model="repomix")

    keys = await _get_enabled_keys(request.provider_type)
    if not keys:
        raise HTTPException(400, f"No enabled keys for provider: {request.provider_type}")

    raw_messages = [{"role": m.role, "content": m.content} for m in request.messages]

    summarizer_cfg = await get_summarizer_config()
    limit = summarizer_cfg.get("limit", 10)
    token_limit = summarizer_cfg.get("token_limit", 0)

    if should_summarize(raw_messages, limit, token_limit):
        if summarizer_cfg.get("mode") == "ai" and summarizer_cfg.get("provider") and summarizer_cfg.get("model"):
            raw_messages = await build_ai_summarized_history(
                raw_messages, summarizer_cfg["provider"], summarizer_cfg["model"]
            )
        else:
            raw_messages = build_summarized_history(raw_messages)
        request_copy = request.model_copy()
        request_copy.messages = [ChatMessage(role=m["role"], content=m["content"]) for m in raw_messages]
        messages = _build_messages(request_copy)
    else:
        messages = _build_messages(request)

    system = request.system or MODE_SYSTEM_PROMPTS.get(request.mode, "")

    if request.mode in ("plan", "auto") and not request.system:
        system = await _inject_available_skills(system)

    # Inject stored plan if one exists for this conversation
    if request.conversation_id:
        try:
            plan_rows = await db.select("plans", filters={"conversation_id": request.conversation_id})
            if plan_rows:
                p = plan_rows[0]
                system += (
                    f"\n\n<current_plan title=\"{p['title']}\" status=\"{p['status']}\">\n"
                    f"{p['plan_json']}\n</current_plan>"
                )
        except Exception as e:
            log.error("unhandled_exception", error=str(e))
            pass

    injected_chunks: list[str] = []
    if request.repo and request.messages:
        parts = request.repo.split("/", 1)
        if len(parts) == 2:
            user_query = request.messages[-1].content
            try:
                rag_chunks = await get_boosted_results(parts[0], parts[1], user_query, n_results=5)
            except Exception as e:
                log.error("unhandled_exception", error=str(e))
                rag_chunks = []
            if rag_chunks:
                injected_chunks = rag_chunks
                compressed = [compress_context(c) for c in rag_chunks]
                rag_block = "\n---\n".join(compressed)
                system += f"\n\n<relevant_context>\n{rag_block}\n</relevant_context>"

            try:
                conv_chunks = await query_conversation_context(parts[0], parts[1], user_query, n_results=3)
            except Exception as e:
                log.error("unhandled_exception", error=str(e))
                conv_chunks = []
            if conv_chunks:
                conv_block = "\n---\n".join(conv_chunks)
                system += f"\n\n<past_conversations>\n{conv_block}\n</past_conversations>"

    system += THINK_INSTRUCTION

    last_error = ""

    for key_row in keys:
        api_key = _decrypt_key(key_row.get("api_key_encrypted", ""))
        provider_id = str(key_row["id"])
        try:
            response = await _call_provider(
                api_key=api_key,
                provider_type=request.provider_type,
                model=request.model,
                messages=messages,
                system=system,
                custom_base_url=key_row.get("base_url", ""),
            )
            await _handle_save_context(request.repo, response)
            await _handle_plan_actions(request.conversation_id, response)

            if injected_chunks and request.repo:
                try:
                    referenced = await detect_referenced_chunks(response, injected_chunks)
                    if referenced:
                        collection = request.repo.replace("/", "__")
                        chunk_ids = [f"{collection}_{hash(c[:100]) & 0xFFFFFFFF}" for c in referenced]
                        await record_chunk_usage(collection, chunk_ids)
                except Exception as e:
                    log.error("unhandled_exception", error=str(e))
                    pass

            if request.repo and request.messages:
                try:
                    parts = request.repo.split("/", 1)
                    user_content = request.messages[-1].content if request.messages else ""
                    await store_conversation_exchange(parts[0], parts[1], user_content, response[:2000])
                except Exception as e:
                    log.error("unhandled_exception", error=str(e))
                    pass

            try:
                from core.conversation_summarizer import count_tokens
                input_text = system + " ".join(m.get("content", "") for m in messages)
                input_toks = count_tokens(input_text)
                output_toks = count_tokens(response)
                await db.insert("token_usage", {
                    "provider_type": request.provider_type,
                    "model": request.model,
                    "input_tokens": input_toks,
                    "output_tokens": output_toks,
                    "conversation_id": "",
                })
            except Exception as e:
                log.error("unhandled_exception", error=str(e))
                pass

            return ChatResponse(
                response=response,
                provider_id=provider_id,
                model=request.model,
            )
        except ModelNotAvailableError as e:
            raise HTTPException(404, str(e)) from e
        except RateLimitError:
            last_error = f"Rate limited on key {key_row.get('name', provider_id)}, trying next..."
            continue
        except ProviderError as e:
            last_error = str(e)
            continue
        except Exception as e:
            last_error = f"Unexpected error: {e}"
            continue

    raise HTTPException(429, f"All keys exhausted for {request.provider_type}. Last error: {last_error}")
