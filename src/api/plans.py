"""
Summary: API router for parsing and managing agent workflow plans.

What it does: Exposes endpoints for plan generation, DAG parsing, and standing orchestrator plan approvals.

How it fits in: Connects with 'src/core/workflow_engine.py' and database.
"""



from __future__ import annotations

from datetime import UTC

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from db import db

router = APIRouter()


class PlanCreate(BaseModel):
    conversation_id: str
    title: str = ""
    plan_json: str
    status: str = "draft"


class PlanUpdate(BaseModel):
    title: str | None = None
    plan_json: str | None = None
    status: str | None = None


@router.get("/api/plans")
async def list_plans(conversation_id: str | None = None):
    filters = {"conversation_id": conversation_id} if conversation_id else None
    rows = await db.select("plans", filters=filters, order_by="updated_at DESC")
    return rows


@router.get("/api/plans/{plan_id}")
async def get_plan(plan_id: str):
    rows = await db.select("plans", filters={"id": plan_id})
    if not rows:
        raise HTTPException(404, "Plan not found")
    return rows[0]


@router.post("/api/plans")
async def create_plan(req: PlanCreate):
    data = {"conversation_id": req.conversation_id, "title": req.title, "plan_json": req.plan_json, "status": req.status}
    return await db.insert("plans", data)


@router.patch("/api/plans/{plan_id}")
async def update_plan(plan_id: str, req: PlanUpdate):
    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(400, "No fields to update")
    from datetime import datetime
    updates["updated_at"] = datetime.now(UTC).isoformat()
    rows = await db.update("plans", updates, filters={"id": plan_id})
    return rows[0] if rows else {"id": plan_id, **updates}


@router.delete("/api/plans/{plan_id}")
async def delete_plan(plan_id: str):
    await db.delete("plans", filters={"id": plan_id})
    return {"deleted": plan_id}
