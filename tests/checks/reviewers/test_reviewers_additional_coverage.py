from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from engineeringagent.agents import AgentBackendError
from engineeringagent.domain.quality import ChangedPathsResult
from engineeringagent.checks.reviewers.engine import (
    DECISION_REQUEST_CHANGES,
    FEATURE_DONE_PHASE,
    PARSER_FAILURE_SUMMARY_PREFIX,
    ReviewerDecisionEnvelope,
    ReviewerRunRequest,
    evaluate_cached_reviewer_approval,
    increment_blocking_reviewer_retry_count,
    invalidate_reviewer_approval,
    record_reviewer_approval,
    run_reviewer,
)


def test_reviewer_decision_envelope_requires_non_empty_summary() -> None:
    with pytest.raises(ValidationError):
        ReviewerDecisionEnvelope.model_validate(
            {
                "decision": "approve",
                "summary": "   ",
                "required_actions": [],
            }
        )


def test_reviewer_decision_envelope_rejects_warning_decision() -> None:
    with pytest.raises(ValidationError):
        ReviewerDecisionEnvelope.model_validate(
            {
                "decision": "warning",
                "summary": "not allowed",
                "required_actions": [],
            }
        )


def test_record_reviewer_approval_accepts_non_dict_existing_state() -> None:
    state: dict[str, Any] = {
        "features": {
            "FEAT-1": {
                "reviewers": {
                    "rev": "not-a-dict",
                }
            }
        }
    }

    record_reviewer_approval(
        state,
        feature_id="FEAT-1",
        reviewer_id="rev",
        decision="approve",
    )
    reviewer_state = state["features"]["FEAT-1"]["reviewers"]["rev"]
    if isinstance(reviewer_state, dict):
        reviewer_state_dict: dict[str, Any] = reviewer_state
    else:
        raise AssertionError("expected reviewer state dict")

    # Pylint inference doesn't track the mutation performed by record_reviewer_approval.
    assert reviewer_state_dict["approved"] is True  # pylint: disable=invalid-sequence-index


def test_record_reviewer_approval_updates_non_approve_decision() -> None:
    state: dict[str, Any] = {"features": {"FEAT-1": {"reviewers": {"rev": {}}}}}

    record_reviewer_approval(
        state,
        feature_id="FEAT-1",
        reviewer_id="rev",
        decision=DECISION_REQUEST_CHANGES,
    )
    reviewer_state = state["features"]["FEAT-1"]["reviewers"]["rev"]
    assert reviewer_state["approved"] is False
    assert "updated_at" in reviewer_state


def test_increment_blocking_reviewer_retry_count_initializes_reviewer_state() -> None:
    state: dict[str, Any] = {"features": {}}

    count = increment_blocking_reviewer_retry_count(
        state,
        feature_id="FEAT-1",
        reviewer_id="rev",
    )

    assert count == 1
    reviewer_state = state["features"]["FEAT-1"]["reviewers"]["rev"]
    assert reviewer_state["approved"] is False
    assert reviewer_state["blocking_request_changes_count"] == 1


def test_invalidate_reviewer_approval_is_defensive() -> None:
    # Wrong shapes should be no-ops.
    invalidate_reviewer_approval({"features": "nope"}, feature_id="f", reviewer_id="r")
    invalidate_reviewer_approval({"features": {}}, feature_id="f", reviewer_id="r")
    invalidate_reviewer_approval(
        {"features": {"f": {"reviewers": "nope"}}},
        feature_id="f",
        reviewer_id="r",
    )
    invalidate_reviewer_approval(
        {"features": {"f": {"reviewers": {"r": "nope"}}}},
        feature_id="f",
        reviewer_id="r",
    )


def test_evaluate_cached_reviewer_approval_invalidates_when_unscoped_changes_present() -> (
    None
):
    state: dict[str, Any] = {
        "features": {"FEAT-1": {"reviewers": {"rev": {"approved": True}}}}
    }

    reviewer_config = {
        "trigger": {"phase": FEATURE_DONE_PHASE},
        "approval": {"first_feature_approval": True},
    }
    changed = ChangedPathsResult(paths=("src/app.py",), run_all=False, reason=None)

    reused, reason = evaluate_cached_reviewer_approval(
        state,
        feature_id="FEAT-1",
        reviewer_id="rev",
        reviewer=reviewer_config,
        changed_paths=changed,
    )
    assert reused is False
    assert "invalidated" in reason


def test_run_reviewer_returns_parser_failure_for_missing_prompt_file(
    tmp_path: Path,
) -> None:
    def run_agent_fn(*_a: Any, **_k: Any) -> Any:
        raise AssertionError("run_agent_fn should not be called")

    request = ReviewerRunRequest(
        feature_id="FEAT-1",
        feature_path=tmp_path,
        changed_paths=ChangedPathsResult(paths=(), run_all=False, reason=None),
        feedback=None,
        run_agent_fn=run_agent_fn,
    )
    decision = run_reviewer(tmp_path, "rev", {"prompt_file": ""}, request=request)
    assert decision["decision"] == DECISION_REQUEST_CHANGES
    assert decision["summary"].startswith(f"{PARSER_FAILURE_SUMMARY_PREFIX}:")


def test_run_reviewer_returns_parser_failure_when_prompt_file_missing_on_disk(
    tmp_path: Path,
) -> None:
    def run_agent_fn(*_a: Any, **_k: Any) -> Any:
        raise AssertionError("run_agent_fn should not be called")

    request = ReviewerRunRequest(
        feature_id="FEAT-1",
        feature_path=tmp_path,
        changed_paths=ChangedPathsResult(paths=(), run_all=False, reason=None),
        feedback=None,
        run_agent_fn=run_agent_fn,
    )
    decision = run_reviewer(
        tmp_path,
        "rev",
        {"prompt_file": "missing.txt"},
        request=request,
    )
    assert decision["decision"] == DECISION_REQUEST_CHANGES
    assert decision["summary"].startswith(f"{PARSER_FAILURE_SUMMARY_PREFIX}:")


def test_run_reviewer_returns_parser_failure_when_opencode_is_missing(
    tmp_path: Path,
) -> None:
    prompt_path = tmp_path / "prompt.txt"
    prompt_path.write_text("Do the thing. $responseformat\n", encoding="utf-8")

    def fake_run_agent(*_args: Any, **_kwargs: Any) -> Any:
        raise FileNotFoundError("opencode")

    request = ReviewerRunRequest(
        feature_id="FEAT-1",
        feature_path=tmp_path,
        changed_paths=ChangedPathsResult(paths=(), run_all=False, reason=None),
        feedback=None,
        run_agent_fn=fake_run_agent,
    )
    decision = run_reviewer(
        tmp_path,
        "rev",
        {"prompt_file": "prompt.txt"},
        request=request,
    )
    assert decision["decision"] == DECISION_REQUEST_CHANGES
    assert "opencode executable missing" in decision["summary"]


def test_run_reviewer_returns_parser_failure_when_agent_backend_errors(
    tmp_path: Path,
) -> None:
    prompt_path = tmp_path / "prompt.txt"
    prompt_path.write_text("Do the thing. $responseformat\n", encoding="utf-8")

    def fake_run_agent(*_args: Any, **_kwargs: Any) -> Any:
        raise AgentBackendError(backend="fake", message="run failed")

    request = ReviewerRunRequest(
        feature_id="FEAT-1",
        feature_path=tmp_path,
        changed_paths=ChangedPathsResult(paths=(), run_all=False, reason=None),
        feedback=None,
        run_agent_fn=fake_run_agent,
    )

    decision = run_reviewer(
        tmp_path,
        "rev",
        {"prompt_file": "prompt.txt"},
        request=request,
    )
    assert decision["decision"] == DECISION_REQUEST_CHANGES
    assert decision["summary"].startswith(f"{PARSER_FAILURE_SUMMARY_PREFIX}:")
    assert "fake: run failed" in decision["summary"]
