"""
Summary: Python logic module 'Github'.

What it does: Provides backend utility operations and core logical helper interfaces for 'Github'.

How it fits in: Imported and utilized by surrounding backend structures.
"""



from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel


class CheckStatus(StrEnum):
    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class CheckConclusion(StrEnum):
    SUCCESS = "success"
    FAILURE = "failure"
    NEUTRAL = "neutral"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"
    ACTION_REQUIRED = "action_required"
    SKIPPED = "skipped"


class PullRequest(BaseModel):
    number: int
    title: str = ""
    state: str = ""
    html_url: str = ""
    head_ref: str = ""
    base_ref: str = ""
    mergeable: bool | None = None
    merged: bool = False
    created_at: datetime | None = None
    updated_at: datetime | None = None


class CheckRun(BaseModel):
    id: int
    name: str = ""
    status: CheckStatus = CheckStatus.QUEUED
    conclusion: CheckConclusion | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


class MergeResult(BaseModel):
    sha: str = ""
    merged: bool = False
    message: str = ""
