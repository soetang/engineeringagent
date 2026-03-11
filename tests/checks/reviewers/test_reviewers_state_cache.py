from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from engineeringagent.checks.changed_paths import ChangedPathsResult
from engineeringagent.adapters.progress import paths as progress_paths
from engineeringagent.checks.reviewers.engine import (
    DECISION_APPROVE,
    FIRST_FEATURE_APPROVAL_INVALIDATED_REASON,
    FIRST_FEATURE_APPROVAL_INVALIDATED_RUN_ALL_REASON,
    FIRST_FEATURE_APPROVAL_NOT_CACHED_REASON,
    FIRST_FEATURE_APPROVAL_REUSED_REASON,
    evaluate_cached_reviewer_approval,
    load_reviewers_state,
    record_reviewer_approval,
    save_reviewers_state,
)


def test_load_reviewers_state_returns_default_when_missing(tmp_path: Path) -> None:
    state = load_reviewers_state(tmp_path)
    assert state["version"] == "1"
    assert state["features"] == {}


def test_load_reviewers_state_returns_default_on_invalid_json(tmp_path: Path) -> None:
    state_path = progress_paths.reviewers_state_path(tmp_path)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text("not-json\n", encoding="utf-8")

    state = load_reviewers_state(tmp_path)
    assert state["version"] == "1"
    assert state["features"] == {}


def test_save_reviewers_state_round_trips_json(tmp_path: Path) -> None:
    payload: dict[str, Any] = {
        "version": "1",
        "features": {"FEAT-001": {"reviewers": {"doc_review": {"approved": True}}}},
    }
    save_reviewers_state(tmp_path, payload)

    state_path = progress_paths.reviewers_state_path(tmp_path)
    loaded = json.loads(state_path.read_text(encoding="utf-8"))
    assert loaded["version"] == "1"
    assert loaded["features"]["FEAT-001"]["reviewers"]["doc_review"]["approved"] is True


def test_record_reviewer_approval_sets_approved_state(tmp_path: Path) -> None:
    state = load_reviewers_state(tmp_path)
    record_reviewer_approval(
        state,
        feature_id="FEAT-002",
        reviewer_id="doc_review",
        decision=DECISION_APPROVE,
    )
    reviewer_state = state["features"]["FEAT-002"]["reviewers"]["doc_review"]
    assert reviewer_state["approved"] is True
    assert reviewer_state["approved_at"]


def test_evaluate_cached_reviewer_approval_not_cached_returns_reason() -> None:
    state: dict[str, Any] = {"version": "1", "features": {}}
    reuse, reason = evaluate_cached_reviewer_approval(
        state,
        feature_id="FEAT-003",
        reviewer_id="doc_review",
        reviewer={"trigger": {}},
        changed_paths=ChangedPathsResult(paths=(), run_all=False, reason=None),
    )
    assert reuse is False
    assert reason == FIRST_FEATURE_APPROVAL_NOT_CACHED_REASON


def test_evaluate_cached_reviewer_approval_reuses_when_no_on_change_and_no_changes() -> (
    None
):
    state: dict[str, Any] = {"version": "1", "features": {}}
    record_reviewer_approval(
        state,
        feature_id="FEAT-004",
        reviewer_id="doc_review",
        decision=DECISION_APPROVE,
    )

    reuse, reason = evaluate_cached_reviewer_approval(
        state,
        feature_id="FEAT-004",
        reviewer_id="doc_review",
        reviewer={"trigger": {}},
        changed_paths=ChangedPathsResult(paths=(), run_all=False, reason=None),
    )
    assert reuse is True
    assert reason == FIRST_FEATURE_APPROVAL_REUSED_REASON


def test_evaluate_cached_reviewer_approval_invalidates_on_run_all() -> None:
    state: dict[str, Any] = {"version": "1", "features": {}}
    record_reviewer_approval(
        state,
        feature_id="FEAT-005",
        reviewer_id="doc_review",
        decision=DECISION_APPROVE,
    )

    reuse, reason = evaluate_cached_reviewer_approval(
        state,
        feature_id="FEAT-005",
        reviewer_id="doc_review",
        reviewer={"trigger": {"on_change": ["README.md"]}},
        changed_paths=ChangedPathsResult(
            paths=(),
            run_all=True,
            reason="fallback_run_all_change_discovery_failed",
        ),
    )
    assert reuse is False
    assert reason == FIRST_FEATURE_APPROVAL_INVALIDATED_RUN_ALL_REASON


def test_evaluate_cached_reviewer_approval_invalidates_when_on_change_matches() -> None:
    state: dict[str, Any] = {"version": "1", "features": {}}
    record_reviewer_approval(
        state,
        feature_id="FEAT-006",
        reviewer_id="doc_review",
        decision=DECISION_APPROVE,
    )

    reuse, reason = evaluate_cached_reviewer_approval(
        state,
        feature_id="FEAT-006",
        reviewer_id="doc_review",
        reviewer={"trigger": {"on_change": ["docs/**/*.md"]}},
        changed_paths=ChangedPathsResult(
            paths=("docs/references/workflow.md",),
            run_all=False,
            reason=None,
        ),
    )
    assert reuse is False
    assert reason == FIRST_FEATURE_APPROVAL_INVALIDATED_REASON
