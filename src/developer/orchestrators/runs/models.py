"""Domain models for implementation run orchestration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from developer.orchestrators.runs.protocols import ImplementationRunTask
else:
    ImplementationRunTask = object


class ImplementationWorkspaceRunRequest(BaseModel):
    """Caller-provided input for one workspace-backed implementation run."""

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")

    repo_path: str
    workspace_task_input: str
    task: ImplementationRunTask
    max_iterations: int | None
    remote_name: str = "origin"


class PublishedTaskBranch(BaseModel):
    """Persisted branch information reused across implementation runs."""

    model_config = ConfigDict(extra="forbid")

    branch_name: str


class ImplementationWorkspacePlan(BaseModel):
    """Resolved workspace execution plan built by the run orchestrator."""

    model_config = ConfigDict(extra="forbid")

    workspace_metadata: dict[str, object]
    run_context: dict[str, object]
    base_branch: str
    task_branch_name: str
    workspace_start_point: str


class ImplementationWorkspaceRunOutcome(BaseModel):
    """Typed outcome returned after delegating one workspace run."""

    model_config = ConfigDict(extra="forbid")

    task_name: str
    workspace_id: str
    run_id: str
    status: str
    latest_message: str | None = None
    metadata: dict[str, object] = Field(default_factory=dict)


class WorkspaceRunCommand(BaseModel):
    """Execution command passed from run orchestrator to workspace runtime."""

    model_config = ConfigDict(extra="forbid")

    repo_path: str
    base_branch: str
    task_id: str
    workspace_metadata: dict[str, object]
    run_context: dict[str, object]


class WorkspaceRunResult(BaseModel):
    """Result returned by the workspace runtime adapter."""

    model_config = ConfigDict(extra="forbid")

    workspace_id: str
    run_id: str
    status: str
    latest_message: str | None = None
    metadata: dict[str, object] = Field(default_factory=dict)
