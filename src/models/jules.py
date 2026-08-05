"""
Summary: Python logic module 'Jules'.

What it does: Provides backend utility operations and core logical helper interfaces for 'Jules'.

How it fits in: Imported and utilized by surrounding backend structures.
"""



from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict


def to_camel(name: str) -> str:
    parts = name.split("_")
    return parts[0] + "".join(w.capitalize() for w in parts[1:])


class SessionState(StrEnum):
    UNSPECIFIED = "STATE_UNSPECIFIED"
    QUEUED = "QUEUED"
    PLANNING = "PLANNING"
    AWAITING_PLAN_APPROVAL = "AWAITING_PLAN_APPROVAL"
    AWAITING_USER_FEEDBACK = "AWAITING_USER_FEEDBACK"
    IN_PROGRESS = "IN_PROGRESS"
    PAUSED = "PAUSED"
    FAILED = "FAILED"
    COMPLETED = "COMPLETED"


class AutomationMode(StrEnum):
    UNSPECIFIED = "AUTOMATION_MODE_UNSPECIFIED"
    AUTO_CREATE_PR = "AUTO_CREATE_PR"


CAMEL_CONFIG = ConfigDict(
    alias_generator=to_camel,
    populate_by_name=True,
    extra="allow",
)


class PlanStep(BaseModel):
    model_config = CAMEL_CONFIG
    id: str
    index: int = 0
    title: str
    description: str = ""


class Plan(BaseModel):
    model_config = CAMEL_CONFIG
    id: str
    steps: list[PlanStep] = []
    create_time: datetime | None = None


class PullRequestOutput(BaseModel):
    model_config = CAMEL_CONFIG
    url: str
    title: str
    description: str = ""


class SessionOutput(BaseModel):
    model_config = CAMEL_CONFIG
    pull_request: PullRequestOutput | None = None
    change_set: ChangeSet | None = None


class SourceContext(BaseModel):
    model_config = CAMEL_CONFIG
    source: str
    github_repo_context: GitHubRepoContext | None = None


class GitHubRepoContext(BaseModel):
    model_config = CAMEL_CONFIG
    starting_branch: str = "main"


class Session(BaseModel):
    model_config = CAMEL_CONFIG
    name: str = ""
    id: str = ""
    prompt: str = ""
    title: str = ""
    state: SessionState = SessionState.UNSPECIFIED
    url: str = ""
    source_context: SourceContext | None = None
    require_plan_approval: bool = False
    automation_mode: AutomationMode = AutomationMode.UNSPECIFIED
    outputs: list[SessionOutput] = []
    create_time: datetime | None = None
    update_time: datetime | None = None


class GitPatch(BaseModel):
    model_config = CAMEL_CONFIG
    base_commit_id: str = ""
    unidiff_patch: str = ""
    suggested_commit_message: str = ""


class ChangeSet(BaseModel):
    model_config = CAMEL_CONFIG
    source: str = ""
    git_patch: GitPatch | None = None


class BashOutput(BaseModel):
    model_config = CAMEL_CONFIG
    command: str = ""
    output: str = ""
    exit_code: int = 0


class Artifact(BaseModel):
    model_config = CAMEL_CONFIG
    change_set: ChangeSet | None = None
    bash_output: BashOutput | None = None


class Activity(BaseModel):
    model_config = CAMEL_CONFIG
    name: str = ""
    id: str = ""
    originator: str = ""
    description: str = ""
    create_time: datetime | None = None
    artifacts: list[Artifact] = []
    plan_generated: PlanGenerated | None = None
    plan_approved: PlanApproved | None = None
    user_messaged: UserMessaged | None = None
    agent_messaged: AgentMessaged | None = None
    progress_updated: ProgressUpdated | None = None
    session_completed: SessionCompleted | None = None
    session_failed: SessionFailed | None = None


class PlanGenerated(BaseModel):
    model_config = CAMEL_CONFIG
    plan: Plan | None = None


class PlanApproved(BaseModel):
    model_config = CAMEL_CONFIG
    plan_id: str = ""


class UserMessaged(BaseModel):
    model_config = CAMEL_CONFIG
    user_message: str = ""


class AgentMessaged(BaseModel):
    model_config = CAMEL_CONFIG
    agent_message: str = ""


class ProgressUpdated(BaseModel):
    model_config = CAMEL_CONFIG
    title: str = ""
    description: str = ""


class SessionCompleted(BaseModel):
    model_config = CAMEL_CONFIG


class SessionFailed(BaseModel):
    model_config = CAMEL_CONFIG
    reason: str = ""


class Source(BaseModel):
    model_config = CAMEL_CONFIG
    name: str = ""
    id: str = ""
    github_repo: GitHubRepo | None = None


class GitHubBranch(BaseModel):
    model_config = CAMEL_CONFIG
    display_name: str = ""


class GitHubRepo(BaseModel):
    model_config = CAMEL_CONFIG
    owner: str = ""
    repo: str = ""
    is_private: bool = False
    default_branch: GitHubBranch | None = None
    branches: list[GitHubBranch] = []


# Rebuild forward refs for models that reference types defined after them
SourceContext.model_rebuild()
Activity.model_rebuild()
