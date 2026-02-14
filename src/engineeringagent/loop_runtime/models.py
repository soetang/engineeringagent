"""Loop runtime data models used by the loop facade."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict


class IterationOutcome(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    completed: bool
    result: str
    failed_gate: str | None
    next_action: str
    hook_feedback: str | None
    log_path: str | None
    verification_status: str = "not_run"
    verification_failed_command: str | None = None


class InitialFeatureLoadOutcome(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    feature: dict[str, Any] | None
    loaded_from_archive: bool
    result: str
    failed_gate: str | None
    hook_feedback: str | None


class PostImplementFeatureOutcome(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    feature: dict[str, Any] | None
    loaded_from_archive: bool
    archived_in_iteration: bool
    archived_path: Path | None
    result: str
    failed_gate: str | None
    hook_feedback: str | None


class ImplementStepInputs(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    project_root: Path
    feature: dict[str, Any]
    feature_path: Path
    implement_command: str | None
    opencode_prompt: str | None
    skip_implement: bool
    hook_feedback: str | None
    verbose_output: bool


class FeatureIterationInputs(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    project_root: Path
    feature_path: Path
    gate_profile: str
    implement_command: str | None
    opencode_prompt: str | None
    skip_implement: bool
    attempt: int
    hook_feedback: str | None
    verbose_output: bool


class GatePhaseOutcome(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    result: str
    failed_gate: str | None
    gate_status: str
    gate_output: str
    hook_feedback: str | None


class VerificationPhaseOutcome(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    result: str
    verification_status: str
    verification_failed_command: str | None
    verification_output: str
    hook_feedback: str | None


class ReviewerPhaseOutcome(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    result: str
    failed_gate: str | None
    reviewer_status: str
    reviewer_output: str
    hook_feedback: str | None


class CompletionCommitOutcome(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    completed: bool
    completion_commit_succeeded: bool
    result: str
    failed_gate: str | None
    next_action: str
    hook_feedback: str | None


class IterationTelemetryInputs(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    iteration_inputs: FeatureIterationInputs
    started: float
    feature_id: str
    result: str
    failed_gate: str | None
    next_action: str
    implement_status: str
    gate_status: str
    verification_status: str
    verification_failed_command: str | None
    implement_output: str
    gate_output: str
    verification_output: str
    hook_feedback: str | None
