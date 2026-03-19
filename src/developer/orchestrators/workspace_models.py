"""Workspace orchestration domain models."""

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class WorkspaceStatus(str, Enum):
    """Lifecycle states for a provisioned workspace."""

    PENDING = "pending"
    READY = "ready"
    FAILED = "failed"
    DESTROYED = "destroyed"


class RunStatus(str, Enum):
    """Lifecycle states for a workspace-backed run."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ExecutionTarget(BaseModel):
    """Concrete execution location for an agent workflow."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["local_path"]
    location: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class WorkspaceSpec(BaseModel):
    """Input used to provision a new workspace."""

    model_config = ConfigDict(extra="forbid")

    provider: str
    repo_path: str
    base_branch: str = "main"
    task_id: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class WorkspaceSession(BaseModel):
    """Persisted workspace session state."""

    model_config = ConfigDict(extra="forbid")

    id: str
    provider: str
    status: WorkspaceStatus
    execution_target: ExecutionTarget
    created_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)


class RunRequest(BaseModel):
    """Generic request to execute an agent workflow in a workspace."""

    model_config = ConfigDict(extra="forbid")

    agent_kind: str
    context: dict[str, Any] = Field(default_factory=dict)


class RunHandle(BaseModel):
    """Persisted handle describing the state of a workspace run."""

    model_config = ConfigDict(extra="forbid")

    id: str
    workspace_id: str
    status: RunStatus
    agent_kind: str
    started_at: datetime | None = None
    finished_at: datetime | None = None
    latest_message: str | None = None
    result_summary: str | None = None


class WorkspaceRunnableResult(BaseModel):
    """Terminal result returned by a workspace-runnable workflow."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["succeeded", "failed"]
    message: str
    summary: str | None = None
