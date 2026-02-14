from __future__ import annotations

from pathlib import Path
from typing import Any

from engineeringagent.gates import ChangedPathsResult
from engineeringagent.loop_runtime.models import FeatureIterationInputs
from engineeringagent.loop_runtime.phases import (
    ReviewerPhaseDependencies,
    run_reviewer_phase,
)
from engineeringagent.reviewers import (
    advisory_followup_required,
    clear_advisory_followup_required,
    plan_reviewers,
    set_advisory_followup_required,
)


def _iteration_inputs(tmp_path: Path) -> FeatureIterationInputs:
    return FeatureIterationInputs(
        project_root=tmp_path,
        feature_path=tmp_path / "docs" / "spec" / "features" / "FEAT-050.yaml",
        gate_profile="loop_fast",
        implement_command=None,
        opencode_prompt=None,
        skip_implement=False,
        attempt=1,
        hook_feedback=None,
        verbose_output=False,
    )


def _base_config(mode: str) -> dict[str, Any]:
    return {
        "profiles": {"loop_fast": ["code_reviewer"]},
        "reviewers": {
            "code_reviewer": {
                "prompt_file": "harness/reviewers/prompts/code_reviewer.md",
                "trigger": {"phase": "iteration_end"},
                "approval": {"mode": mode},
            }
        },
    }


def _deps(
    config: dict[str, Any],
    *,
    decision: str,
    summary: str,
    state_box: dict[str, dict[str, Any]] | None = None,
    restore_calls: list[tuple[Path, Path]] | None = None,
) -> ReviewerPhaseDependencies:
    state_ref = (
        state_box
        if state_box is not None
        else {"state": {"version": "1", "features": {}}}
    )

    def _restore(archived: Path, active: Path) -> tuple[bool, str | None]:
        if restore_calls is not None:
            restore_calls.append((archived, active))
        return True, None

    return ReviewerPhaseDependencies(
        load_reviewer_config=lambda _path: config,
        collect_changed_paths=lambda _root: ChangedPathsResult(
            paths=("src/engineeringagent/loop.py",),
            run_all=False,
            reason=None,
        ),
        load_reviewers_state=lambda _root: state_ref["state"],
        save_reviewers_state=lambda _root, state: state_ref.__setitem__("state", state),
        plan_reviewers=plan_reviewers,
        evaluate_cached_reviewer_approval=(
            lambda *_args, **_kwargs: (False, "first_feature_approval_not_cached")
        ),
        run_reviewer=lambda *_args, **_kwargs: {
            "decision": decision,
            "summary": summary,
            "required_actions": [],
        },
        record_reviewer_approval=lambda *_args, **_kwargs: None,
        advisory_followup_required=(
            lambda state, feature_id: advisory_followup_required(
                state, feature_id=feature_id
            )
        ),
        set_advisory_followup_required=(
            lambda state, feature_id: set_advisory_followup_required(
                state,
                feature_id=feature_id,
            )
        ),
        clear_advisory_followup_required=(
            lambda state, feature_id: clear_advisory_followup_required(
                state,
                feature_id=feature_id,
            )
        ),
        restore_archived_feature=_restore,
        start_agent=lambda *_args, **_kwargs: None,
    )


def test_blocking_reviewer_requests_retry_and_sets_feedback(tmp_path: Path) -> None:
    outcome = run_reviewer_phase(
        _iteration_inputs(tmp_path),
        {"id": "FEAT-050"},
        archived_in_iteration=False,
        archived_path=None,
        dependencies=_deps(
            _base_config("blocking"),
            decision="request_changes",
            summary="Refactor reviewer planner branch.",
        ),
    )

    assert outcome.result == "failed"
    assert outcome.failed_gate == "reviewer_blocking"
    assert "requested changes" in str(outcome.hook_feedback)


def test_advisory_reviewer_records_warning_without_blocking(tmp_path: Path) -> None:
    outcome = run_reviewer_phase(
        _iteration_inputs(tmp_path),
        {"id": "FEAT-050"},
        archived_in_iteration=False,
        archived_path=None,
        dependencies=_deps(
            _base_config("advisory"),
            decision="warning",
            summary="Optional readability cleanup.",
        ),
    )

    assert outcome.result == "passed"
    assert outcome.failed_gate is None
    assert outcome.reviewer_status == "passed:advisory"
    assert "advisory feedback" in str(outcome.hook_feedback)


def test_advisory_feedback_requires_one_followup_implement_pass(tmp_path: Path) -> None:
    config = _base_config("advisory")
    config["reviewers"]["code_reviewer"]["trigger"]["phase"] = "feature_done"
    state_box: dict[str, dict[str, Any]] = {"state": {"version": "1", "features": {}}}
    restore_calls: list[tuple[Path, Path]] = []
    deps = _deps(
        config,
        decision="warning",
        summary="Run one follow-up pass before completion.",
        state_box=state_box,
        restore_calls=restore_calls,
    )
    archived_path = tmp_path / "docs" / "spec" / "features_done" / "FEAT-050.yaml"

    first = run_reviewer_phase(
        _iteration_inputs(tmp_path),
        {"id": "FEAT-050"},
        archived_in_iteration=True,
        archived_path=archived_path,
        dependencies=deps,
    )
    second = run_reviewer_phase(
        _iteration_inputs(tmp_path),
        {"id": "FEAT-050"},
        archived_in_iteration=True,
        archived_path=archived_path,
        dependencies=deps,
    )

    assert first.result == "failed"
    assert first.failed_gate == "reviewer_advisory_followup"
    assert second.result == "passed"
    assert second.failed_gate is None
    assert len(restore_calls) == 1


def test_blocking_reviewer_exhausted_continues_with_warning_by_default(
    tmp_path: Path,
) -> None:
    config = _base_config("blocking")
    config["reviewers"]["code_reviewer"]["approval"] = {
        "mode": "blocking",
        "max_retries": 1,
        "continue_on_exhausted": True,
    }
    state_box: dict[str, dict[str, Any]] = {"state": {"version": "1", "features": {}}}
    deps = _deps(
        config,
        decision="request_changes",
        summary="Address parser branch duplication.",
        state_box=state_box,
    )

    first = run_reviewer_phase(
        _iteration_inputs(tmp_path),
        {"id": "FEAT-050"},
        archived_in_iteration=False,
        archived_path=None,
        dependencies=deps,
    )
    second = run_reviewer_phase(
        _iteration_inputs(tmp_path),
        {"id": "FEAT-050"},
        archived_in_iteration=False,
        archived_path=None,
        dependencies=deps,
    )

    assert first.result == "failed"
    assert first.failed_gate == "reviewer_blocking"
    assert second.result == "passed"
    assert second.failed_gate is None
    assert second.reviewer_status == "passed:blocking_exhausted_continue"
    assert "exhausted retries" in str(second.hook_feedback)


def test_blocking_reviewer_exhausted_can_be_configured_to_fail(tmp_path: Path) -> None:
    config = _base_config("blocking")
    config["reviewers"]["code_reviewer"]["approval"] = {
        "mode": "blocking",
        "max_retries": 1,
        "continue_on_exhausted": False,
    }
    state_box: dict[str, dict[str, Any]] = {"state": {"version": "1", "features": {}}}
    deps = _deps(
        config,
        decision="request_changes",
        summary="Address parser branch duplication.",
        state_box=state_box,
    )

    first = run_reviewer_phase(
        _iteration_inputs(tmp_path),
        {"id": "FEAT-050"},
        archived_in_iteration=False,
        archived_path=None,
        dependencies=deps,
    )
    second = run_reviewer_phase(
        _iteration_inputs(tmp_path),
        {"id": "FEAT-050"},
        archived_in_iteration=False,
        archived_path=None,
        dependencies=deps,
    )

    assert first.result == "failed"
    assert first.failed_gate == "reviewer_blocking"
    assert second.result == "failed"
    assert second.failed_gate == "reviewer_blocking_exhausted"
    assert "exhausted retries" in str(second.hook_feedback)
