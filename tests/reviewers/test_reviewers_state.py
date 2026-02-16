from __future__ import annotations

import json
from pathlib import Path

from engineeringagent.gates import ChangedPathsResult
import engineeringagent.progress_paths as progress_paths
from engineeringagent.reviewers import (
    FIRST_FEATURE_APPROVAL_INVALIDATED_REASON,
    FIRST_FEATURE_APPROVAL_INVALIDATED_RUN_ALL_REASON,
    FIRST_FEATURE_APPROVAL_NOT_CACHED_REASON,
    FIRST_FEATURE_APPROVAL_REUSED_REASON,
    evaluate_cached_reviewer_approval,
    invalidate_reviewer_approval,
    load_reviewers_state,
    record_reviewer_approval,
    save_reviewers_state,
)


def test_reviewers_state_path_helper(tmp_path: Path) -> None:
    assert progress_paths.reviewers_state_path(tmp_path) == (
        tmp_path / "progress" / "reviewers-state.json"
    )


def test_reviewers_state_round_trip_under_progress_directory(tmp_path) -> None:
    state = load_reviewers_state(tmp_path)

    record_reviewer_approval(
        state,
        feature_id="FEAT-050",
        reviewer_id="code_simplifier",
        decision="approve",
    )
    save_reviewers_state(tmp_path, state)

    loaded = load_reviewers_state(tmp_path)

    assert loaded["features"]["FEAT-050"]["reviewers"]["code_simplifier"]["approved"]
    state_path = tmp_path / "progress" / "reviewers-state.json"
    payload = json.loads(state_path.read_text(encoding="utf-8"))
    assert payload["version"] == "1"


def test_cached_first_approval_reused_when_scope_unchanged() -> None:
    state = {
        "version": "1",
        "features": {
            "FEAT-050": {
                "reviewers": {
                    "onboarding_review": {
                        "approved": True,
                        "approved_at": "2026-02-14T00:00:00Z",
                    }
                }
            }
        },
    }

    reuse, reason = evaluate_cached_reviewer_approval(
        state,
        feature_id="FEAT-050",
        reviewer_id="onboarding_review",
        reviewer={
            "trigger": {"phase": "feature_done", "on_change": ["README.md"]},
            "approval": {"first_feature_approval": True},
        },
        changed_paths=ChangedPathsResult(
            paths=("src/engineeringagent/reviewers.py",),
            run_all=False,
            reason=None,
        ),
    )

    assert reuse is True
    assert reason == FIRST_FEATURE_APPROVAL_REUSED_REASON


def test_cached_first_approval_invalidates_when_scoped_paths_change() -> None:
    state = {
        "version": "1",
        "features": {
            "FEAT-050": {
                "reviewers": {
                    "onboarding_review": {
                        "approved": True,
                        "approved_at": "2026-02-14T00:00:00Z",
                    }
                }
            }
        },
    }

    reuse, reason = evaluate_cached_reviewer_approval(
        state,
        feature_id="FEAT-050",
        reviewer_id="onboarding_review",
        reviewer={
            "trigger": {"phase": "feature_done", "on_change": ["README.md"]},
            "approval": {"first_feature_approval": True},
        },
        changed_paths=ChangedPathsResult(
            paths=("README.md",),
            run_all=False,
            reason=None,
        ),
    )

    assert reuse is False
    assert reason == FIRST_FEATURE_APPROVAL_INVALIDATED_REASON
    reviewer_state = state["features"]["FEAT-050"]["reviewers"]["onboarding_review"]
    assert reviewer_state["approved"] is False
    assert "invalidated_at" in reviewer_state


def test_cached_first_approval_invalidates_on_run_all_fallback() -> None:
    state = {
        "version": "1",
        "features": {
            "FEAT-050": {
                "reviewers": {
                    "code_simplifier": {
                        "approved": True,
                        "approved_at": "2026-02-14T00:00:00Z",
                    }
                }
            }
        },
    }

    reuse, reason = evaluate_cached_reviewer_approval(
        state,
        feature_id="FEAT-050",
        reviewer_id="code_simplifier",
        reviewer={
            "trigger": {"phase": "iteration_end", "on_change": ["src/**/*.py"]},
            "approval": {"first_feature_approval": True},
        },
        changed_paths=ChangedPathsResult(
            paths=(),
            run_all=True,
            reason="fallback_run_all_change_discovery_failed",
        ),
    )

    assert reuse is False
    assert reason == FIRST_FEATURE_APPROVAL_INVALIDATED_RUN_ALL_REASON
    reviewer_state = state["features"]["FEAT-050"]["reviewers"]["code_simplifier"]
    assert reviewer_state["approved"] is False
    assert "invalidated_at" in reviewer_state


def test_cached_first_approval_missing_when_not_previously_approved() -> None:
    reuse, reason = evaluate_cached_reviewer_approval(
        {"version": "1", "features": {}},
        feature_id="FEAT-050",
        reviewer_id="code_simplifier",
        reviewer={
            "trigger": {"phase": "iteration_end"},
            "approval": {"first_feature_approval": True},
        },
        changed_paths=ChangedPathsResult(paths=(), run_all=False, reason=None),
    )

    assert reuse is False
    assert reason == FIRST_FEATURE_APPROVAL_NOT_CACHED_REASON


def test_invalidate_reviewer_approval_marks_cached_approval_false() -> None:
    state = {
        "version": "1",
        "features": {
            "FEAT-050": {
                "reviewers": {
                    "code_simplifier": {
                        "approved": True,
                        "approved_at": "2026-02-14T00:00:00Z",
                    }
                }
            }
        },
    }

    invalidate_reviewer_approval(
        state,
        feature_id="FEAT-050",
        reviewer_id="code_simplifier",
    )

    assert (
        state["features"]["FEAT-050"]["reviewers"]["code_simplifier"]["approved"]
        is False
    )
    assert (
        "invalidated_at"
        in state["features"]["FEAT-050"]["reviewers"]["code_simplifier"]
    )
