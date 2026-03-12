from __future__ import annotations

from typing import Iterable

from engineeringagent.domain.quality import (
    CommandInvocationRecord,
    HarnessCheckPhase,
)
from engineeringagent.domain.quality import (
    ChangedPathsResult,
    HarnessCheckCommandDefinition,
    HarnessChecksDocument,
    PlanningPolicyContext,
    PlannedCheck,
    make_planned_check,
    plan_checks_for_definition_type,
)


def plan_command_checks(
    doc: HarnessChecksDocument,
    *,
    phase: HarnessCheckPhase,
    changed_paths: ChangedPathsResult,
    phase_only_policy: bool = False,
) -> list[PlannedCheck]:
    """Plan deterministic run/skip decisions for command checks."""
    context = PlanningPolicyContext(
        phase=phase,
        changed_paths=changed_paths,
        phase_only_policy=phase_only_policy,
    )
    return plan_checks_for_definition_type(
        doc,
        context=context,
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


__all__ = [
    "CommandInvocationRecord",
    "HarnessCheckPhase",
    "PlannedCheck",
    "iter_planned_command_check_commands",
    "plan_command_checks",
]
