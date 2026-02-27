from __future__ import annotations

from engineeringagent.changed_paths import ChangedPathsResult
from engineeringagent.checks.strategy_contracts import PlannedCheck, make_planned_check
from engineeringagent.specs import (
    HarnessCheckFitnessDefinition,
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
        make_record=make_planned_check,
    )
