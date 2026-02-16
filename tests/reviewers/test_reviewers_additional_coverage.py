from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import ValidationError

from engineeringagent.changed_paths import ChangedPathsResult
from engineeringagent.reviewers import (
    DECISION_REQUEST_CHANGES,
    FEATURE_DONE_PHASE,
    MATCHED_ON_CHANGE_REASON,
    NO_ON_CHANGE_MATCH_REASON,
    PARSER_FAILURE_SUMMARY_PREFIX,
    ReviewerDecisionEnvelope,
    evaluate_cached_reviewer_approval,
    increment_blocking_reviewer_retry_count,
    invalidate_reviewer_approval,
    load_reviewer_config,
    plan_reviewers,
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
    assert isinstance(reviewer_state, dict)
    assert reviewer_state["approved"] is True


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


def test_load_reviewer_config_returns_default_when_missing(tmp_path: Path) -> None:
    config = load_reviewer_config(tmp_path / "missing.yaml")

    assert config["contract_version"] == "1.0"
    assert config["profiles"] == {}
    assert config["reviewers"] == {}


def test_plan_reviewers_unknown_profile_raises() -> None:
    with pytest.raises(ValueError, match="unknown profile"):
        plan_reviewers(
            {"contract_version": "1.0", "profiles": {}, "reviewers": {}},
            "missing",
            phase=FEATURE_DONE_PHASE,
            changed_paths=ChangedPathsResult(paths=(), run_all=False, reason=None),
        )


def test_plan_reviewers_covers_run_and_skip_reasons() -> None:
    config = {
        "contract_version": "1.0",
        "profiles": {"default": ["phase_mismatch", "always", "match", "skip"]},
        "reviewers": {
            "phase_mismatch": {"trigger": {"phase": "some_other_phase"}},
            "always": {"trigger": {"phase": FEATURE_DONE_PHASE}},
            "match": {
                "trigger": {"phase": FEATURE_DONE_PHASE, "on_change": ["src/**"]}
            },
            "skip": {
                "trigger": {"phase": FEATURE_DONE_PHASE, "on_change": ["docs/**"]}
            },
        },
    }

    # Non-run_all path exercises phase mismatch, always-run, match, and skip.
    changed = ChangedPathsResult(paths=("src/app.py",), run_all=False, reason=None)
    decisions = plan_reviewers(
        config,
        "default",
        phase=FEATURE_DONE_PHASE,
        changed_paths=changed,
    )
    assert [item["reviewer"] for item in decisions] == [
        "phase_mismatch",
        "always",
        "match",
        "skip",
    ]
    assert decisions[1]["reason"] != MATCHED_ON_CHANGE_REASON
    assert decisions[2]["reason"] == MATCHED_ON_CHANGE_REASON
    assert decisions[3]["reason"] == NO_ON_CHANGE_MATCH_REASON

    # Run-all path forces deterministic fallback reason.
    run_all = ChangedPathsResult(paths=(), run_all=True, reason="forced")
    decisions = plan_reviewers(
        config,
        "default",
        phase=FEATURE_DONE_PHASE,
        changed_paths=run_all,
    )
    assert decisions[1]["decision"] == "run"
    assert decisions[1]["reason"] == "forced"


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
    request = {
        "feature_id": "FEAT-1",
        "feature_path": tmp_path,
        "changed_paths": ChangedPathsResult(paths=(), run_all=False, reason=None),
        "prior_feedback": None,
        "start_agent_fn": lambda *_a, **_k: SimpleNamespace(stdout="", stderr=""),
    }
    decision = run_reviewer(tmp_path, "rev", {"prompt_file": ""}, **request)
    assert decision["decision"] == DECISION_REQUEST_CHANGES
    assert decision["summary"].startswith(f"{PARSER_FAILURE_SUMMARY_PREFIX}:")


def test_run_reviewer_returns_parser_failure_when_prompt_file_missing_on_disk(
    tmp_path: Path,
) -> None:
    request = {
        "feature_id": "FEAT-1",
        "feature_path": tmp_path,
        "changed_paths": ChangedPathsResult(paths=(), run_all=False, reason=None),
        "prior_feedback": None,
        "start_agent_fn": lambda *_a, **_k: SimpleNamespace(stdout="", stderr=""),
    }
    decision = run_reviewer(tmp_path, "rev", {"prompt_file": "missing.txt"}, **request)
    assert decision["decision"] == DECISION_REQUEST_CHANGES
    assert decision["summary"].startswith(f"{PARSER_FAILURE_SUMMARY_PREFIX}:")


def test_run_reviewer_returns_parser_failure_when_opencode_is_missing(
    tmp_path: Path,
) -> None:
    prompt_path = tmp_path / "prompt.txt"
    prompt_path.write_text("Do the thing. $responseformat\n", encoding="utf-8")

    def fake_start_agent(*_args: Any, **_kwargs: Any) -> Any:
        raise FileNotFoundError("opencode")

    request = {
        "feature_id": "FEAT-1",
        "feature_path": tmp_path,
        "changed_paths": ChangedPathsResult(paths=(), run_all=False, reason=None),
        "prior_feedback": None,
        "start_agent_fn": fake_start_agent,
    }
    decision = run_reviewer(tmp_path, "rev", {"prompt_file": "prompt.txt"}, **request)
    assert decision["decision"] == DECISION_REQUEST_CHANGES
    assert "opencode executable missing" in decision["summary"]
