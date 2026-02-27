from __future__ import annotations

from typing import Iterable

from pydantic import BaseModel, ConfigDict

from engineeringagent.changed_paths import ChangedPathsResult
from engineeringagent.checks.strategy_contracts import PlannedCheck, make_planned_check
from engineeringagent.specs import (
    HarnessCheckCommandDefinition,
    HarnessCheckPhase,
    HarnessChecksDocument,
)

from ..planning_policy import (
    ALWAYS_RUN_NO_ON_CHANGE_REASON as _ALWAYS_RUN_NO_ON_CHANGE_REASON,
)
from ..planning_policy import (
    MATCHED_ON_CHANGE_REASON as _MATCHED_ON_CHANGE_REASON,
)
from ..planning_policy import (
    NO_ON_CHANGE_MATCH_REASON as _NO_ON_CHANGE_MATCH_REASON,
)
from ..planning_policy import (
    plan_checks_for_definition_type,
)

ALWAYS_RUN_NO_ON_CHANGE_REASON = _ALWAYS_RUN_NO_ON_CHANGE_REASON
MATCHED_ON_CHANGE_REASON = _MATCHED_ON_CHANGE_REASON
NO_ON_CHANGE_MATCH_REASON = _NO_ON_CHANGE_MATCH_REASON


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
        make_record=make_planned_check,
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
