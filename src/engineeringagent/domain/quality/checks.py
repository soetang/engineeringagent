"""Quality-domain checks models."""

from __future__ import annotations

from typing import Any, Mapping, NamedTuple

from pydantic import BaseModel, ConfigDict
from typing_extensions import Literal, TypedDict
from engineeringagent.domain.shared import CheckPhase

HarnessCheckPhase = CheckPhase


CheckDecisionAction = Literal["run", "skip"]


class CheckDecision(TypedDict):
    """Deterministic check planning record."""

    check_id: str
    check_type: str
    phase: str
    decision: CheckDecisionAction
    reason: str


class CheckExecutionRecord(NamedTuple):
    """One side-effecting execution result emitted by a strategy."""

    check_id: str
    check_type: str
    ok: bool
    output: str
    payload: dict[str, Any] | None = None
    timing: Mapping[str, Any] | None = None


class CommandInvocationRecord(BaseModel):
    """Structured metadata for one command-check invocation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    check_id: str
    command: str
    returncode: int | None
    started_epoch_sec: int
    ended_epoch_sec: int
    started_monotonic_ns: int
    finished_monotonic_ns: int
    duration_ms: float


class ChecksRunResult(BaseModel):
    """Structured result for a checks run."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    ok: bool
    dry_run: bool = False
    failed_check_id: str | None = None
    failed_payload: dict[str, Any] | None = None
    output: str = ""
    decisions: tuple[CheckDecision, ...] = ()
    executions: tuple[CheckExecutionRecord, ...] = ()
    prompt_feedback: str | None = None
    command_invocations: tuple[CommandInvocationRecord, ...] = ()
