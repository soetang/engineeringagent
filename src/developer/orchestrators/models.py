"""Domain models for orchestrator control flow."""

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict


class ImplementationContext(BaseModel):
    """Typed execution context shared across orchestrator callbacks."""

    model_config = ConfigDict(extra="forbid")

    workspace_id: str | None = None
    run_id: str | None = None
    repo_path: str | None = None
    workspace_path: str | None = None
    workspace_branch_name: str | None = None
    task_branch_name: str | None = None
    base_branch: str | None = None
    remote_name: str = "origin"
    task_name: str = "implementation"
    task_path: str | None = None
    latest_change_summary: str | None = None


class AgentResult(BaseModel):
    """Represents agent execution output for an orchestrator attempt."""

    model_config = ConfigDict(extra="forbid")

    summary: str


class GateResult(BaseModel):
    """Represents the result of a quality gate check."""

    model_config = ConfigDict(extra="forbid")

    passed: bool
    feedback: str | None = None


class GatePhase(str, Enum):
    """Phases used by the gate runner."""

    ITERATION_COMPLETE = "IterationComplete"
    IMPLEMENTATION_COMPLETE = "ImplementationComplete"


class CompletionResult(str, Enum):
    """Represents whether an iterative flow has reached completion."""

    COMPLETE = "COMPLETE"
    INCOMPLETE = "INCOMPLETE"


class OrchestratorOutcome(BaseModel):
    """Public orchestrator result with overall status and attempt count."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["success", "failed"]
    iterations: int
    feedback: str | None = None
    publication_message: str | None = None


class IterationArtifact(BaseModel):
    """Observer-produced artifact for a successful iteration."""

    model_config = ConfigDict(extra="forbid")

    commit_sha: str | None = None
    commit_subject: str | None = None


class RunPublicationResult(BaseModel):
    """Observer-produced publication details for a successful run."""

    model_config = ConfigDict(extra="forbid")

    branch_name: str | None = None
    pr_url: str | None = None
    message: str | None = None
