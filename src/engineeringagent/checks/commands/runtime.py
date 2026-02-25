from __future__ import annotations

from typing import Iterable, cast

from pydantic import BaseModel, ConfigDict

from engineeringagent.changed_paths import ChangedPathsResult
from engineeringagent.specs import (
    HarnessCheckCommandDefinition,
    HarnessCheckPhase,
    HarnessChecksDocument,
)
from engineeringagent.checks.strategy_contracts import CheckDecisionAction

from ..planning_policy import (
    ALWAYS_RUN_NO_ON_CHANGE_REASON as _ALWAYS_RUN_NO_ON_CHANGE_REASON,
    MATCHED_ON_CHANGE_REASON as _MATCHED_ON_CHANGE_REASON,
    NO_ON_CHANGE_MATCH_REASON as _NO_ON_CHANGE_MATCH_REASON,
    plan_checks_for_definition_type,
)


ALWAYS_RUN_NO_ON_CHANGE_REASON = _ALWAYS_RUN_NO_ON_CHANGE_REASON
MATCHED_ON_CHANGE_REASON = _MATCHED_ON_CHANGE_REASON
NO_ON_CHANGE_MATCH_REASON = _NO_ON_CHANGE_MATCH_REASON


class PlannedCheck(BaseModel):
    """Deterministic plan entry for a command check."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    check_id: str
    decision: CheckDecisionAction
    reason: str


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


def plan_command_checks(
    doc: HarnessChecksDocument,
    *,
    phase: HarnessCheckPhase,
    changed_paths: ChangedPathsResult,
) -> list[PlannedCheck]:
    """Plan deterministic run/skip decisions for command checks."""
    return plan_checks_for_definition_type(
        doc,
        phase=phase,
        changed_paths=changed_paths,
        definition_type=HarnessCheckCommandDefinition,
        make_record=lambda check_id, decision, reason: PlannedCheck(
            check_id=check_id,
            decision=cast(CheckDecisionAction, decision),
            reason=reason,
        ),
    )


def iter_planned_command_check_commands(
    doc: HarnessChecksDocument,
    planned: Iterable[PlannedCheck],
) -> Iterable[tuple[str, str]]:
    """Yield (check_id, command) pairs for planned command checks."""
    by_id = doc.checks
    for entry in planned:
        if entry.decision != "run":
            continue
        check = by_id.get(entry.check_id)
        if not isinstance(check, HarnessCheckCommandDefinition):
            continue
        yield entry.check_id, check.command
