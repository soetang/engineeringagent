from __future__ import annotations

from typing import cast

from pydantic import BaseModel, ConfigDict

from engineeringagent.changed_paths import ChangedPathsResult
from engineeringagent.specs import (
    HarnessCheckFitnessDefinition,
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
    """A deterministic run/skip decision for a single fitness check."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    check_id: str
    decision: CheckDecisionAction
    reason: str


def plan_fitness_checks(
    doc: HarnessChecksDocument,
    *,
    phase: HarnessCheckPhase,
    changed_paths: ChangedPathsResult,
) -> list[PlannedCheck]:
    """Plan deterministic run/skip decisions for fitness checks."""
    return plan_checks_for_definition_type(
        doc,
        phase=phase,
        changed_paths=changed_paths,
        definition_type=HarnessCheckFitnessDefinition,
        make_record=lambda check_id, decision, reason: PlannedCheck(
            check_id=check_id,
            decision=cast(CheckDecisionAction, decision),
            reason=reason,
        ),
    )
