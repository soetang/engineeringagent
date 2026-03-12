from __future__ import annotations

from engineeringagent.checks.strategy_contracts import PlannedCheck, make_planned_check
from engineeringagent.domain.quality import (
    ChangedPathsResult,
    HarnessCheckPhase,
    HarnessCheckFitnessDefinition,
    HarnessChecksDocument,
    PlanningPolicyContext,
    plan_checks_for_definition_type,
)


def plan_fitness_checks(
    doc: HarnessChecksDocument,
    *,
    phase: HarnessCheckPhase,
    changed_paths: ChangedPathsResult,
    phase_only_policy: bool = False,
) -> list[PlannedCheck]:
    """Plan deterministic run/skip decisions for fitness checks."""
    context = PlanningPolicyContext(
        phase=phase,
        changed_paths=changed_paths,
        phase_only_policy=phase_only_policy,
    )
    return plan_checks_for_definition_type(
        doc,
        context=context,
        definition_type=HarnessCheckFitnessDefinition,
        make_record=make_planned_check,
    )
