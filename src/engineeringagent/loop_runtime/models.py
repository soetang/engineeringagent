"""Loop runtime data models used by the loop facade."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class IterationOutcome:
    completed: bool
    result: str
    failed_gate: str | None
    next_action: str
    hook_feedback: str | None
    log_path: str | None


@dataclass(frozen=True)
class InitialFeatureLoadOutcome:
    feature: dict[str, Any] | None
    loaded_from_archive: bool
    result: str
    failed_gate: str | None
    hook_feedback: str | None


@dataclass(frozen=True)
class PostImplementFeatureOutcome:
    feature: dict[str, Any] | None
    loaded_from_archive: bool
    archived_in_iteration: bool
    archived_path: Path | None
    result: str
    failed_gate: str | None
    hook_feedback: str | None


@dataclass(frozen=True)
class ImplementStepInputs:
    project_root: Path
    feature: dict[str, Any]
    feature_path: Path
    implement_command: str | None
    opencode_prompt: str | None
    skip_implement: bool
    hook_feedback: str | None
    verbose_output: bool


@dataclass(frozen=True)
class FeatureIterationInputs:
    project_root: Path
    feature_path: Path
    gate_profile: str
    implement_command: str | None
    opencode_prompt: str | None
    skip_implement: bool
    attempt: int
    hook_feedback: str | None
    verbose_output: bool


@dataclass(frozen=True)
class GatePhaseOutcome:
    result: str
    failed_gate: str | None
    gate_status: str
    gate_output: str
    hook_feedback: str | None


@dataclass(frozen=True)
class CompletionCommitOutcome:
    completed: bool
    completion_commit_succeeded: bool
    result: str
    failed_gate: str | None
    next_action: str
    hook_feedback: str | None


@dataclass(frozen=True)
class IterationTelemetryInputs:
    iteration_inputs: FeatureIterationInputs
    started: float
    feature_id: str
    result: str
    failed_gate: str | None
    next_action: str
    implement_status: str
    gate_status: str
    implement_output: str
    gate_output: str
    hook_feedback: str | None
