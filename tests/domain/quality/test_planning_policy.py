from __future__ import annotations

from engineeringagent.domain.quality import (
    ChangedPathsResult,
    HarnessCheckPhase,
    path_matches_any_glob,
    plan_run_skip_decision,
)


def test_plan_run_skip_decision_phase_only_policy_overrides_manual_on_change() -> None:
    """Phase-only selection should override manual-phase skipping."""
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


def test_path_matches_any_glob_normalizes_dot_slash_prefix() -> None:
    """Glob matching should ignore a leading ./ prefix."""
    assert path_matches_any_glob("./README.md", ["README.md"]) is True


def test_path_matches_any_glob_empty_patterns_returns_false() -> None:
    """Glob matching should short-circuit for an empty pattern set."""
    assert path_matches_any_glob("README.md", []) is False
