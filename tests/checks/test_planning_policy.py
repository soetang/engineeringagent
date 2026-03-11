from __future__ import annotations

from engineeringagent.changed_paths import ChangedPathsResult
from engineeringagent.checks.planning_policy import plan_run_skip_decision
from engineeringagent.domain.quality import HarnessCheckPhase


def test_plan_run_skip_decision_phase_only_policy_overrides_manual_on_change() -> None:
    changed_paths = ChangedPathsResult(paths=(), run_all=False, reason=None)

    assert plan_run_skip_decision(
        phase=HarnessCheckPhase.MANUAL,
        on_change=("docs/**",),
        changed_paths=changed_paths,
        phase_only_policy=False,
    ) == ("skip", "manual")

    assert plan_run_skip_decision(
        phase=HarnessCheckPhase.MANUAL,
        on_change=("docs/**",),
        changed_paths=changed_paths,
        phase_only_policy=True,
    ) == ("run", "phase_only_policy")
