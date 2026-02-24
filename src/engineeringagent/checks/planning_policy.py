from __future__ import annotations

from typing import Any, Callable, Sequence

from engineeringagent.changed_paths import (
    ChangedPathsResult,
    FALLBACK_CHANGE_DISCOVERY_REASON,
)
from engineeringagent.specs import (
    HarnessCheckPhase,
    HarnessCheckWhenDefinition,
    HarnessChecksDocument,
)

from .on_change_matcher import path_matches_any_glob

ALWAYS_RUN_NO_ON_CHANGE_REASON = "always_run_no_on_change"
MATCHED_ON_CHANGE_REASON = "matched_on_change"
NO_ON_CHANGE_MATCH_REASON = "no_on_change_match"
MANUAL_SKIP_REASON = "manual"


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
    path_matcher: Callable[[str, Sequence[str]], bool] = path_matches_any_glob,
) -> tuple[str, str]:
    """Return deterministic run/skip decision and reason for phase/on_change policy."""
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
    phase: HarnessCheckPhase,
    check_when: HarnessCheckWhenDefinition | None,
    changed_paths: ChangedPathsResult,
    path_matcher: Callable[[str, Sequence[str]], bool] = path_matches_any_glob,
) -> tuple[str, str] | None:
    """Return a check decision for phase/on_change or None when phase mismatches."""
    if effective_check_phase(doc=doc, check_when=check_when) != phase:
        return None
    return plan_run_skip_decision(
        phase=phase,
        on_change=check_when.on_change if check_when is not None else None,
        changed_paths=changed_paths,
        path_matcher=path_matcher,
    )
