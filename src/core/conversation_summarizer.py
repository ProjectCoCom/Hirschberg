"""
LLM-based conversation summarization helper.

Responsibilities:
- Shrinks long chat transcripts into concise summaries to save context window tokens.

Coupling:
- Invoked by conversation manager.
"""


from __future__ import annotations

import json

try:
    import tiktoken
    _enc = tiktoken.get_encoding("cl100k_base")

    def count_tokens(text: str) -> int:
        return len(_enc.encode(text))
except ImportError:
    def count_tokens(text: str) -> int:
        # ~4 chars per token as rough approximation
        return len(text) // 4


def count_messages_tokens(messages: list[dict]) -> int:
    total = 0
    for msg in messages:
        content = msg.get("content", "")
        if isinstance(content, list):
            content = " ".join(p.get("text", "") for p in content if isinstance(p, dict))
        total += count_tokens(content) + 4  # role overhead
    return total


def should_summarize(messages: list[dict], limit: int = 10, token_limit: int = 0) -> bool:
    if token_limit > 0:
        return count_messages_tokens(messages) > token_limit
    return len(messages) > limit


def extract_summary(messages: list[dict]) -> str:
    points = []
    for msg in messages:
        role = msg.get("role", "")
        content = msg.get("content", "")
        if isinstance(content, list):
            content = " ".join(p.get("text", "") for p in content if isinstance(p, dict))
        if not content:
            continue
        if role == "user":
            points.append(f"- User asked: {content[:120]}")
        elif role == "assistant":
            first_sentence = content.split(".")[0].strip()
            if first_sentence:
                points.append(f"- AI responded: {first_sentence[:120]}")
    return "\n".join(points) if points else "No significant exchanges."


def build_summarized_history(messages: list[dict], keep_recent: int = 4) -> list[dict]:
    if len(messages) <= keep_recent:
        return messages

    older = messages[:-keep_recent]
    recent = messages[-keep_recent:]

    # Preserve messages containing plan actions — they must not be compressed
    preserved = []
    compressible = []
    for msg in older:
        content = msg.get("content", "")
        if "[ACTION:PLAN_SAVE:" in content or "[ACTION:PLAN_UPDATE:" in content:
            preserved.append(msg)
        else:
            compressible.append(msg)

    summary = extract_summary(compressible)

    summary_msg = {
        "role": "system",
        "content": f"[Conversation summary]\n{summary}",
    }
    return [summary_msg] + preserved + recent


async def build_ai_summarized_history(
    messages: list[dict],
    provider_type: str,
    model: str,
    keep_recent: int = 4,
) -> list[dict]:
    if len(messages) <= keep_recent:
        return messages

    older = messages[:-keep_recent]
    recent = messages[-keep_recent:]

    # Preserve plan action messages
    preserved = []
    compressible = []
    for msg in older:
        content = msg.get("content", "")
        if "[ACTION:PLAN_SAVE:" in content or "[ACTION:PLAN_UPDATE:" in content:
            preserved.append(msg)
        else:
            compressible.append(msg)

    conversation_text = "\n".join(
        f"{m.get('role', 'unknown').upper()}: {m.get('content', '')[:500]}"
        for m in compressible
    )

    try:
        from api.chat import _call_provider

        summary_prompt = [
            {
                "role": "system",
                "content": (
                    "Summarize this conversation into a concise paragraph capturing "
                    "key topics, decisions, and context. Be brief but preserve important details."
                ),
            },
            {"role": "user", "content": conversation_text[:8000]},
        ]

        response = await _call_provider(provider_type, model, summary_prompt)
        summary_text = response if isinstance(response, str) else str(response)
    except Exception as e:
        log.error("unhandled_exception", error=str(e))
        summary_text = extract_summary(older)

    summary_msg = {
        "role": "system",
        "content": f"[AI-generated conversation summary]\n{summary_text}",
    }
    return [summary_msg] + preserved + recent


async def get_summarizer_config() -> dict:
    try:
        from db import db
        rows = await db.select("app_settings", filters={"key": "summarizer_config"})
        if rows:
            return json.loads(rows[0].get("value", "{}"))
    except Exception as e:
        log.error("unhandled_exception", error=str(e))
        pass
    return {"mode": "free", "provider": "", "model": "", "limit": 10}
