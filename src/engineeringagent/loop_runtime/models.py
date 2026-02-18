"""Loop runtime data models used by the loop facade."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class IterationOutcome(BaseModel):
    """Outcome of a single feature iteration run."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    completed: bool
    result: str
    failed_gate: str | None
    next_action: str
    hook_feedback: str | None
    log_path: str | None
    verification_status: str = "not_run"
    verification_failed_command: str | None = None
    reviewer_status: str = "not_run"
    reviewer_decision: str | None = None
    failed_reviewer_id: str | None = None


class InitialFeatureLoadOutcome(BaseModel):
    """Outcome of loading the selected feature YAML (optionally from archive)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    feature: dict[str, Any] | None
    loaded_from_archive: bool
    result: str
    failed_gate: str | None
    hook_feedback: str | None


class PostImplementFeatureOutcome(BaseModel):
    """Outcome from post-implementation bookkeeping (e.g. archive decisions)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    feature: dict[str, Any] | None
    loaded_from_archive: bool
    archived_in_iteration: bool
    archived_path: Path | None
    result: str
    failed_gate: str | None
    hook_feedback: str | None


class ImplementStepInputs(BaseModel):
    """Inputs for a single implementation step of the loop."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    project_root: Path
    feature: dict[str, Any]
    feature_path: Path
    hook_feedback: str | None
    verbose_output: bool


class FeatureIterationInputs(BaseModel):
    """Inputs for running a full feature iteration."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    project_root: Path
    feature_path: Path
    run_all: bool = False
    attempt: int
    hook_feedback: str | None
    verbose_output: bool


class PhaseTiming(BaseModel):
    """Timing metadata for a loop phase."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    phase: str
    started_at: str
    ended_at: str
    duration_sec: int


class CommandTiming(BaseModel):
    """Timing metadata for a single command (or reviewer) invocation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    phase: str
    command: str
    started_at: str
    ended_at: str
    duration_sec: int
    gate: str | None = None
    reviewer_id: str | None = None


class GatePhaseOutcome(BaseModel):
    """Outcome of running deterministic repo gates for a phase."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    result: str
    failed_gate: str | None
    gate_status: str
    gate_output: str
    command_timings: list[CommandTiming] = Field(default_factory=list)
    hook_feedback: str | None


class VerificationPhaseOutcome(BaseModel):
    """Outcome of running verification commands for a phase."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    result: str
    verification_status: str
    verification_failed_command: str | None
    verification_output: str
    command_timings: list[CommandTiming] = Field(default_factory=list)
    hook_feedback: str | None


class ReviewerPhaseOutcome(BaseModel):
    """Outcome of running automated reviewer checks for a phase."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    result: str
    failed_gate: str | None
    reviewer_status: str
    reviewer_decision: str | None = None
    failed_reviewer_id: str | None = None
    reviewer_output: str
    command_timings: list[CommandTiming] = Field(default_factory=list)
    hook_feedback: str | None


class CompletionCommitOutcome(BaseModel):
    """Outcome of creating a completion commit after a successful feature."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    completed: bool
    completion_commit_succeeded: bool
    result: str
    failed_gate: str | None
    next_action: str
    hook_feedback: str | None
    completion_output: str = ""


class IterationTelemetryInputs(BaseModel):
    """Structured telemetry captured for a feature iteration."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    iteration_inputs: FeatureIterationInputs
    started: float
    phase_timings: list[PhaseTiming] = Field(default_factory=list)
    command_timings: list[CommandTiming] = Field(default_factory=list)
    feature_id: str
    result: str
    failed_gate: str | None
    next_action: str
    implement_status: str
    gate_status: str
    verification_status: str
    verification_failed_command: str | None
    reviewer_status: str = "not_run"
    reviewer_decision: str | None = None
    failed_reviewer_id: str | None = None
    implement_output: str
    gate_output: str
    verification_output: str
    reviewer_output: str = ""
    reviewer_feedback_forwarded: str | None = None
    hook_feedback: str | None
    completion_output: str = ""
