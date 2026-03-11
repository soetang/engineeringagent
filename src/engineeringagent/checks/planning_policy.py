from __future__ import annotations

from typing import Any, Callable, TypeVar, Sequence

from pydantic import BaseModel, ConfigDict

from engineeringagent.changed_paths import (
    ChangedPathsResult,
    FALLBACK_CHANGE_DISCOVERY_REASON,
)
from engineeringagent.checks.contracts import HarnessCheckPhase
from engineeringagent.domain.quality import (
    HarnessCheckWhenDefinition,
    HarnessChecksDocument,
)

from .on_change_matcher import path_matches_any_glob

ALWAYS_RUN_NO_ON_CHANGE_REASON = "always_run_no_on_change"
MATCHED_ON_CHANGE_REASON = "matched_on_change"
NO_ON_CHANGE_MATCH_REASON = "no_on_change_match"
MANUAL_SKIP_REASON = "manual"
PHASE_ONLY_POLICY_REASON = "phase_only_policy"


_PlannedCheckT = TypeVar("_PlannedCheckT")


class PlanningPolicyContext(BaseModel):
    """Shared deterministic policy inputs for planning decisions."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    phase: HarnessCheckPhase
    changed_paths: ChangedPathsResult
    phase_only_policy: bool = False
    path_matcher: Callable[[str, Sequence[str]], bool] = path_matches_any_glob


def effective_default_phase(doc: HarnessChecksDocument) -> HarnessCheckPhase:
    """Return the effective default phase for checks in a document."""
    defaults = doc.defaults
    if defaults is None or defaults.when is None or defaults.when.phase is None:
        return HarnessCheckPhase.ITERATION_END
    return defaults.when.phase


def effective_check_phase(
    *,
    doc: HarnessChecksDocument,
    check_when: Any,
) -> HarnessCheckPhase:
    """Return the effective phase for a check-like object with optional `phase`."""
    default_phase = effective_default_phase(doc)
    if check_when is None or getattr(check_when, "phase", None) is None:
        return default_phase
    return check_when.phase


def plan_run_skip_decision(
    *,
    phase: HarnessCheckPhase,
    on_change: Sequence[str] | None,
    changed_paths: ChangedPathsResult,
    phase_only_policy: bool = False,
    path_matcher: Callable[[str, Sequence[str]], bool] = path_matches_any_glob,
) -> tuple[str, str]:
    """Return deterministic run/skip decision and reason for phase/on_change policy."""
    if phase_only_policy:
        return "run", PHASE_ONLY_POLICY_REASON

    if phase == HarnessCheckPhase.MANUAL:
        return "skip", MANUAL_SKIP_REASON

    if on_change is None:
        return "run", ALWAYS_RUN_NO_ON_CHANGE_REASON

    if changed_paths.run_all:
        fallback_reason = changed_paths.reason or FALLBACK_CHANGE_DISCOVERY_REASON
        return "run", fallback_reason

    if any(path_matcher(path, on_change) for path in changed_paths.paths):
        return "run", MATCHED_ON_CHANGE_REASON

    return "skip", NO_ON_CHANGE_MATCH_REASON


def plan_check_when_decision(
    *,
    doc: HarnessChecksDocument,
    check_when: HarnessCheckWhenDefinition | None,
    context: PlanningPolicyContext,
) -> tuple[str, str] | None:
    """Return a check decision for phase/on_change or None when phase mismatches."""
    if effective_check_phase(doc=doc, check_when=check_when) != context.phase:
        return None
    return plan_run_skip_decision(
        phase=context.phase,
        on_change=check_when.on_change if check_when is not None else None,
        changed_paths=context.changed_paths,
        phase_only_policy=context.phase_only_policy,
        path_matcher=context.path_matcher,
    )


def plan_checks_for_definition_type(
    doc: HarnessChecksDocument,
    *,
    context: PlanningPolicyContext,
    definition_type: type[Any],
    make_record: Callable[[str, str, str], _PlannedCheckT],
) -> list[_PlannedCheckT]:
    """Plan deterministic checks for one definition type using shared policy."""

    planned: list[_PlannedCheckT] = []
    for check_id, check in doc.checks.items():
        if not isinstance(check, definition_type):
            continue
        decision = plan_check_when_decision(
            doc=doc,
            check_when=getattr(check, "when", None),
            context=context,
        )
        if decision is None:
            continue
        decision_value, reason = decision
        planned.append(make_record(check_id, decision_value, reason))

    return planned
