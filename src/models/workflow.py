from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class TaskStatus(StrEnum):
    PENDING = "pending"
    WAITING = "waiting"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class WorkflowStatus(StrEnum):
    CREATED = "created"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AgentTask(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    workflow_id: UUID | None = None
    parent_task_id: UUID | None = None
    account_id: UUID | None = None
    session_id: str = ""
    prompt: str = ""
    repo_owner: str = ""
    repo_name: str = ""
    branch: str = "main"
    status: TaskStatus = TaskStatus.PENDING
    depends_on: list[UUID] = []
    pr_url: str = ""
    context: dict[str, Any] = {}
    error: str = ""
    assign_to: str = ""
    prompt_id: str | None = None
    exit_criteria: str = ""
    orchestrator_session_id: str = ""
    created_at: datetime | None = None
    updated_at: datetime | None = None


class Workflow(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    name: str = ""
    description: str = ""
    status: WorkflowStatus = WorkflowStatus.CREATED
    tasks: list[AgentTask] = []
    execution_mode: str = "sequential"
    created_at: datetime | None = None
    updated_at: datetime | None = None
