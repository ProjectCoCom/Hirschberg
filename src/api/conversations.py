"""
API router for conversation logs and history.

Responsibilities:
- Handles endpoints for creating, deleting, and fetching chat conversation models and transcripts.

Coupling:
- Communicates with local database client.
"""


from __future__ import annotations

import contextlib
import json
from datetime import UTC, datetime

from fastapi import APIRouter
from pydantic import BaseModel

from config import load_settings
from db import db

router = APIRouter()
settings = load_settings()


class ConversationCreate(BaseModel):
    title: str = "New Conversation"
    mode: str = "ask"
    repo_owner: str = ""
    repo_name: str = ""
    provider_type: str = ""
    model: str = ""


class MessageCreate(BaseModel):
    role: str
    content: str
    metadata: dict = {}


@router.get("/api/conversations")
async def list_conversations():
    try:
        rows = await db.select("conversations", columns="id, title, mode, repo_owner, repo_name, model, provider_type, status, created_at, updated_at", order_by="updated_at DESC")
    except Exception:
        try:
            rows = await db.select("conversations", order_by="updated_at DESC")
        except Exception:
            return {"conversations": []}
    return {"conversations": rows}


@router.post("/api/conversations")
async def create_conversation(body: ConversationCreate):
    row = await db.insert("conversations", {
        "title": body.title,
        "mode": body.mode,
        "repo_owner": body.repo_owner,
        "repo_name": body.repo_name,
        "model": body.model,
        "provider_type": body.provider_type,
    })
    return row


@router.get("/api/conversations/{conv_id}/messages")
async def get_messages(conv_id: str):
    try:
        rows = await db.select("conversation_messages", filters={"conversation_id": conv_id}, order_by="created_at ASC")
    except Exception:
        return {"messages": []}
    return {"messages": rows}


@router.post("/api/conversations/{conv_id}/messages")
async def add_message(conv_id: str, body: MessageCreate):
    # Ensure conversation exists (handles legacy local IDs)
    try:
        existing = await db.select("conversations", filters={"id": conv_id})
        if not existing:
            await db.insert("conversations", {"id": conv_id, "title": "Untitled", "mode": "ask"})
    except Exception:
        pass
    row = await db.insert("conversation_messages", {
        "conversation_id": conv_id,
        "role": body.role,
        "content": body.content,
        "metadata": json.dumps(body.metadata) if body.metadata else "{}",
    })
    with contextlib.suppress(Exception):
        await db.update("conversations", {"updated_at": datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")}, {"id": conv_id})
    return row


@router.patch("/api/conversations/{conv_id}")
async def update_conversation(conv_id: str, body: dict):
    allowed = {"title", "mode", "model", "status"}
    updates = {k: v for k, v in body.items() if k in allowed}
    if not updates:
        return {"ok": True}
    await db.update("conversations", updates, {"id": conv_id})
    return {"ok": True}


@router.delete("/api/conversations/{conv_id}")
async def delete_conversation(conv_id: str):
    await db.delete("conversations", {"id": conv_id})
    return {"ok": True}
