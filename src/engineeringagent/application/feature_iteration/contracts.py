"""Application-owned feature-iteration internal contracts."""

from __future__ import annotations

from pathlib import Path
from typing import Any, TypeAlias

from pydantic import BaseModel, ConfigDict, Field

from engineeringagent.domain.audit.handoff import ImplementProgressEnvelope

ImplementStepResult: TypeAlias = tuple[
    bool,
    str | None,
    str,
    ImplementProgressEnvelope,
    bool,
]


class IterationOutcome(BaseModel):
    """Outcome of a single feature iteration run."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    completed: bool
    result: str
    failed_gate: str | None
    next_action: str
    feedback: str | None
    log_path: str | None
    verification_status: str = "not_run"
    verification_failed_command: str | None = None
    reviewer_status: str = "not_run"
    reviewer_decision: str | None = None
    failed_reviewer_id: str | None = None

    @classmethod
    def from_report(cls, report: "IterationReport") -> "IterationOutcome":
        """Build an outcome view from an iteration report."""

        return cls(
            completed=report.completed,
            result=report.result,
            failed_gate=report.failed_gate,
            next_action=report.next_action,
            feedback=report.feedback,
            log_path=report.log_path,
            verification_status=report.verification_status,
            verification_failed_command=report.verification_failed_command,
            reviewer_status=report.reviewer_status,
            reviewer_decision=report.reviewer_decision,
            failed_reviewer_id=report.failed_reviewer_id,
        )


class ImplementStepInputs(BaseModel):
    """Inputs for a single implementation step of the loop."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    project_root: Path
    feature: dict[str, Any]
    feature_path: Path
    feedback: str | None
    verbose_output: bool


class FeatureIterationInputs(BaseModel):
    """Inputs for running a full feature iteration."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    project_root: Path
    feature_path: Path
    run_all: bool = False
    attempt: int
    feedback: str | None
    verbose_output: bool


class PhaseTiming(BaseModel):
    """Timing metadata for a loop phase."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    phase: str
    started_at: str
    ended_at: str
    duration_sec: int


class CommandTiming(BaseModel):
    """Timing metadata for a single command or reviewer invocation."""

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
    feedback: str | None


class VerificationPhaseOutcome(BaseModel):
    """Outcome of running verification commands for a phase."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    result: str
    verification_status: str
    verification_failed_command: str | None
    verification_output: str
    command_timings: list[CommandTiming] = Field(default_factory=list)
    feedback: str | None


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
    feedback: str | None
    archived_rolled_back: bool = False


class CompletionCommitOutcome(BaseModel):
    """Outcome of creating a completion commit after a successful feature."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    completed: bool
    completion_commit_succeeded: bool
    result: str
    failed_gate: str | None
    next_action: str
    feedback: str | None
    completion_output: str = ""
    archived_rolled_back: bool = False


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
    progress_kind: str | None = None
    progress_id: str | None = None
    progress_title: str | None = None
    implement_output: str
    implement_handoff_envelope: ImplementProgressEnvelope | None = None
    implement_handoff_used_fallback: bool = False
    gate_output: str
    verification_output: str
    reviewer_output: str = ""
    reviewer_feedback_forwarded: str | None = None
    feedback: str | None
    completion_output: str = ""


class IterationReport(BaseModel):
    """Typed iteration report consumed by post-pipeline observers."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    completed: bool
    result: str
    failed_gate: str | None
    next_action: str
    feedback: str | None
    feature_id: str
    attempt: int
    selected_feature_path: str
    implement_step: str
    archived_selection_path: str | None = None
    verification_status: str = "not_run"
    verification_failed_command: str | None = None
    reviewer_status: str = "not_run"
    reviewer_decision: str | None = None
    failed_reviewer_id: str | None = None
    telemetry_inputs: IterationTelemetryInputs
    log_path: str | None = None


class IterationSummaryInputs(BaseModel):
    """Structured console-summary payload for a loop iteration."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    feature_id: str | None
    result: str
    failed_gate: str | None
    attempt: int | None
    next_action: str
    selected_path: str | None = None
    implement_step: str | None = None
    log_path: str | None = None
    archived_selection_path: str | None = None
    verification_status: str | None = None
    verification_failed_command: str | None = None
    reviewer_status: str | None = None
    reviewer_decision: str | None = None
    failed_reviewer_id: str | None = None
    progress_kind: str | None = None
    progress_id: str | None = None
    progress_title: str | None = None
