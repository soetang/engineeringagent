from __future__ import annotations

from pathlib import Path
from typing import Any

from engineeringagent.gates import ChangedPathsResult
from engineeringagent.loop_runtime.iteration import (
    IterationPipelineDependencies,
    run_feature_iteration_pipeline,
)
from engineeringagent.loop_runtime.models import (
    FeatureIterationInputs,
    CompletionCommitOutcome,
    GatePhaseOutcome,
    InitialFeatureLoadOutcome,
    PostImplementFeatureOutcome,
    ReviewerPhaseOutcome,
    VerificationPhaseOutcome,
)
from engineeringagent.loop_runtime.phases import (
    CompletionPhaseDependencies,
    GatePhaseDependencies,
    ReviewerPhaseDependencies,
    VerificationPhaseDependencies,
    run_reviewer_phase,
)
from engineeringagent.reviewers import plan_reviewers


def _iteration_inputs(tmp_path: Path) -> FeatureIterationInputs:
    return FeatureIterationInputs(
        project_root=tmp_path,
        feature_path=tmp_path / "docs" / "spec" / "features" / "FEAT-050.yaml",
        gate_profile="loop_fast",
        attempt=1,
        hook_feedback=None,
        verbose_output=False,
    )


def _base_config() -> dict[str, Any]:
    return {
        "profiles": {"loop_fast": ["code_reviewer"]},
        "reviewers": {
            "code_reviewer": {
                "prompt_file": "harness/reviewers/prompts/code_reviewer.md",
                "trigger": {"phase": "iteration_end"},
            }
        },
    }


def _deps(
    config: dict[str, Any],
    *,
    decision: str,
    summary: str,
    required_actions: list[str] | None = None,
    changed_paths: tuple[str, ...] = ("src/engineeringagent/loop.py",),
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
            paths=changed_paths,
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
            "required_actions": required_actions or [],
        },
        record_reviewer_approval=lambda *_args, **_kwargs: None,
        restore_archived_feature=_restore,
        start_agent=lambda *_args, **_kwargs: None,
    )


def test_feature_done_reviewer_request_changes_blocks_completion_and_sets_feedback(
    tmp_path: Path,
) -> None:
    config = _base_config()
    config["reviewers"]["code_reviewer"]["trigger"]["phase"] = "feature_done"
    config["reviewers"]["code_reviewer"]["feedback_context"] = (
        "This reviewer runs with constrained context and may not see the full repo."
    )
    outcome = run_reviewer_phase(
        _iteration_inputs(tmp_path),
        {"id": "FEAT-050"},
        archived_in_iteration=True,
        archived_path=tmp_path / "docs" / "spec" / "features_done" / "FEAT-050.yaml",
        dependencies=_deps(
            config,
            decision="request_changes",
            summary="Refactor reviewer planner branch.",
        ),
    )

    assert outcome.result == "failed"
    assert outcome.failed_gate == "reviewer_request_changes"
    assert "requested changes" in str(outcome.hook_feedback)
    assert "feedback_context:" in str(outcome.hook_feedback)
    assert "may not see the full repo" in str(outcome.hook_feedback)


def test_iteration_end_reviewer_does_not_run_when_feature_not_archived(
    tmp_path: Path,
) -> None:
    outcome = run_reviewer_phase(
        _iteration_inputs(tmp_path),
        {"id": "FEAT-050"},
        archived_in_iteration=False,
        archived_path=None,
        dependencies=_deps(
            _base_config(),
            decision="approve",
            summary="Optional readability cleanup.",
        ),
    )

    assert outcome.result == "passed"
    assert outcome.failed_gate is None
    assert outcome.reviewer_status == "not_run"
    assert outcome.hook_feedback is None


def test_reviewer_phase_skips_when_feature_payload_missing(tmp_path: Path) -> None:
    outcome = run_reviewer_phase(
        _iteration_inputs(tmp_path),
        None,
        archived_in_iteration=True,
        archived_path=tmp_path / "docs" / "spec" / "features_done" / "FEAT-050.yaml",
        dependencies=_deps(
            _base_config(),
            decision="approve",
            summary="unused",
        ),
    )

    assert outcome.result == "passed"
    assert outcome.reviewer_status == "not_run"


def test_reviewer_phase_returns_not_run_when_planner_selects_no_reviewers(
    tmp_path: Path,
) -> None:
    config = _base_config()
    config["reviewers"]["code_reviewer"]["trigger"]["phase"] = "feature_done"

    deps = ReviewerPhaseDependencies(
        load_reviewer_config=lambda _path: config,
        collect_changed_paths=lambda _root: ChangedPathsResult(
            paths=("src/engineeringagent/loop.py",),
            run_all=False,
            reason=None,
        ),
        load_reviewers_state=lambda _root: {"version": "1", "features": {}},
        save_reviewers_state=lambda *_args, **_kwargs: None,
        plan_reviewers=lambda *_args, **_kwargs: [],
        evaluate_cached_reviewer_approval=lambda *_args, **_kwargs: (False, ""),
        run_reviewer=lambda *_args, **_kwargs: {},
        record_reviewer_approval=lambda *_args, **_kwargs: None,
        restore_archived_feature=lambda *_args, **_kwargs: (True, None),
        start_agent=lambda *_args, **_kwargs: None,
    )

    outcome = run_reviewer_phase(
        _iteration_inputs(tmp_path),
        {"id": "FEAT-050"},
        archived_in_iteration=True,
        archived_path=tmp_path / "docs" / "spec" / "features_done" / "FEAT-050.yaml",
        dependencies=deps,
    )

    assert outcome.result == "passed"
    assert outcome.reviewer_status == "not_run"


def test_reviewer_phase_passes_when_all_planned_entries_are_skips(
    tmp_path: Path,
) -> None:
    config = _base_config()
    config["reviewers"]["code_reviewer"]["trigger"]["phase"] = "feature_done"

    deps = ReviewerPhaseDependencies(
        load_reviewer_config=lambda _path: config,
        collect_changed_paths=lambda _root: ChangedPathsResult(
            paths=("src/engineeringagent/loop.py",),
            run_all=False,
            reason=None,
        ),
        load_reviewers_state=lambda _root: {"version": "1", "features": {}},
        save_reviewers_state=lambda *_args, **_kwargs: None,
        plan_reviewers=lambda *_args, **_kwargs: [
            {
                "reviewer": "code_reviewer",
                "decision": "skip",
                "reason": "phase_mismatch",
            }
        ],
        evaluate_cached_reviewer_approval=lambda *_args, **_kwargs: (False, ""),
        run_reviewer=lambda *_args, **_kwargs: {},
        record_reviewer_approval=lambda *_args, **_kwargs: None,
        restore_archived_feature=lambda *_args, **_kwargs: (True, None),
        start_agent=lambda *_args, **_kwargs: None,
    )

    outcome = run_reviewer_phase(
        _iteration_inputs(tmp_path),
        {"id": "FEAT-050"},
        archived_in_iteration=True,
        archived_path=tmp_path / "docs" / "spec" / "features_done" / "FEAT-050.yaml",
        dependencies=deps,
    )

    assert outcome.result == "passed"
    assert outcome.reviewer_status == "passed"
    assert "skip reason=phase_mismatch" in outcome.reviewer_output


def test_reviewer_phase_passes_when_reviewer_entry_is_not_a_mapping(
    tmp_path: Path,
) -> None:
    config = _base_config()
    config["reviewers"]["code_reviewer"] = "not-a-mapping"

    deps = ReviewerPhaseDependencies(
        load_reviewer_config=lambda _path: config,
        collect_changed_paths=lambda _root: ChangedPathsResult(
            paths=("src/engineeringagent/loop.py",),
            run_all=False,
            reason=None,
        ),
        load_reviewers_state=lambda _root: {"version": "1", "features": {}},
        save_reviewers_state=lambda *_args, **_kwargs: None,
        plan_reviewers=lambda *_args, **_kwargs: [
            {
                "reviewer": "code_reviewer",
                "decision": "run",
                "reason": "always_run_no_on_change",
            }
        ],
        evaluate_cached_reviewer_approval=lambda *_args, **_kwargs: (False, ""),
        run_reviewer=lambda *_args, **_kwargs: {},
        record_reviewer_approval=lambda *_args, **_kwargs: None,
        restore_archived_feature=lambda *_args, **_kwargs: (True, None),
        start_agent=lambda *_args, **_kwargs: None,
    )

    outcome = run_reviewer_phase(
        _iteration_inputs(tmp_path),
        {"id": "FEAT-050"},
        archived_in_iteration=True,
        archived_path=tmp_path / "docs" / "spec" / "features_done" / "FEAT-050.yaml",
        dependencies=deps,
    )

    assert outcome.result == "passed"


def test_reviewer_phase_records_reused_approvals_in_output(tmp_path: Path) -> None:
    config = _base_config()
    config["reviewers"]["code_reviewer"]["trigger"]["phase"] = "feature_done"

    deps = ReviewerPhaseDependencies(
        load_reviewer_config=lambda _path: config,
        collect_changed_paths=lambda _root: ChangedPathsResult(
            paths=("src/engineeringagent/loop.py",),
            run_all=False,
            reason=None,
        ),
        load_reviewers_state=lambda _root: {"version": "1", "features": {}},
        save_reviewers_state=lambda *_args, **_kwargs: None,
        plan_reviewers=lambda *_args, **_kwargs: [
            {
                "reviewer": "code_reviewer",
                "decision": "run",
                "reason": "always_run_no_on_change",
            }
        ],
        evaluate_cached_reviewer_approval=lambda *_args, **_kwargs: (
            True,
            "first_feature_approval_reused",
        ),
        run_reviewer=lambda *_args, **_kwargs: {},
        record_reviewer_approval=lambda *_args, **_kwargs: None,
        restore_archived_feature=lambda *_args, **_kwargs: (True, None),
        start_agent=lambda *_args, **_kwargs: None,
    )

    outcome = run_reviewer_phase(
        _iteration_inputs(tmp_path),
        {"id": "FEAT-050"},
        archived_in_iteration=True,
        archived_path=tmp_path / "docs" / "spec" / "features_done" / "FEAT-050.yaml",
        dependencies=deps,
    )

    assert outcome.result == "passed"
    assert "reused=first_feature_approval_reused" in outcome.reviewer_output


def test_reviewer_phase_treats_empty_feedback_context_as_missing(
    tmp_path: Path,
) -> None:
    config = _base_config()
    config["reviewers"]["code_reviewer"]["trigger"]["phase"] = "feature_done"
    config["reviewers"]["code_reviewer"]["feedback_context"] = "\n"

    deps = ReviewerPhaseDependencies(
        load_reviewer_config=lambda _path: config,
        collect_changed_paths=lambda _root: ChangedPathsResult(
            paths=("src/engineeringagent/loop.py",),
            run_all=False,
            reason=None,
        ),
        load_reviewers_state=lambda _root: {"version": "1", "features": {}},
        save_reviewers_state=lambda *_args, **_kwargs: None,
        plan_reviewers=lambda *_args, **_kwargs: [
            {
                "reviewer": "code_reviewer",
                "decision": "run",
                "reason": "always_run_no_on_change",
            }
        ],
        evaluate_cached_reviewer_approval=lambda *_args, **_kwargs: (False, ""),
        run_reviewer=lambda *_args, **_kwargs: {
            "decision": "approve",
            "summary": "Looks good.",
            "required_actions": [],
        },
        record_reviewer_approval=lambda *_args, **_kwargs: None,
        restore_archived_feature=lambda *_args, **_kwargs: (True, None),
        start_agent=lambda *_args, **_kwargs: None,
    )

    outcome = run_reviewer_phase(
        _iteration_inputs(tmp_path),
        {"id": "FEAT-050"},
        archived_in_iteration=True,
        archived_path=tmp_path / "docs" / "spec" / "features_done" / "FEAT-050.yaml",
        dependencies=deps,
    )

    assert outcome.result == "passed"


def test_feature_done_reviewer_approve_does_not_forward_non_blocking_feedback(
    tmp_path: Path,
) -> None:
    config = _base_config()
    config["reviewers"]["code_reviewer"]["trigger"]["phase"] = "feature_done"
    state_box: dict[str, dict[str, Any]] = {"state": {"version": "1", "features": {}}}
    restore_calls: list[tuple[Path, Path]] = []
    deps = _deps(
        config,
        decision="approve",
        summary="Looks good to ship after one polish pass.",
        required_actions=["Polish variable names for readability."],
        state_box=state_box,
        restore_calls=restore_calls,
    )
    archived_path = tmp_path / "docs" / "spec" / "features_done" / "FEAT-050.yaml"

    outcome = run_reviewer_phase(
        _iteration_inputs(tmp_path),
        {"id": "FEAT-050"},
        archived_in_iteration=True,
        archived_path=archived_path,
        dependencies=deps,
    )

    assert outcome.result == "passed"
    assert outcome.failed_gate is None
    assert outcome.hook_feedback is None
    assert len(restore_calls) == 0
    assert state_box["state"]["features"].get("FEAT-050") is None


def test_feature_done_reviewer_warning_is_normalized_to_request_changes(
    tmp_path: Path,
) -> None:
    config = _base_config()
    config["reviewers"]["code_reviewer"]["trigger"]["phase"] = "feature_done"
    config["reviewers"]["code_reviewer"]["feedback_context"] = (
        "Runs in a clean-room sandbox; treat failures as real but align fixes with the full codebase."
    )
    outcome = run_reviewer_phase(
        _iteration_inputs(tmp_path),
        {"id": "FEAT-050"},
        archived_in_iteration=True,
        archived_path=tmp_path / "docs" / "spec" / "features_done" / "FEAT-050.yaml",
        dependencies=_deps(
            config,
            decision="warning",
            summary="Reviewer warning should still reach implement prompt.",
        ),
    )

    assert outcome.result == "failed"
    assert outcome.failed_gate == "reviewer_request_changes"
    assert "Reviewer warning should still reach implement prompt." in str(
        outcome.hook_feedback
    )
    assert "feedback_context:" in str(outcome.hook_feedback)
    assert "clean-room sandbox" in str(outcome.hook_feedback)


def test_reviewer_phase_records_reviewer_command_timing(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    import engineeringagent.loop_runtime.phases as phases_module

    time_values = [10.0, 13.0]

    def _fake_time() -> float:
        if time_values:
            return time_values.pop(0)
        return 13.0

    monkeypatch.setattr(phases_module.time, "time", _fake_time)

    config = _base_config()
    config["reviewers"]["code_reviewer"]["trigger"]["phase"] = "feature_done"

    outcome = run_reviewer_phase(
        _iteration_inputs(tmp_path),
        {"id": "FEAT-050"},
        archived_in_iteration=True,
        archived_path=tmp_path / "docs" / "spec" / "features_done" / "FEAT-050.yaml",
        dependencies=_deps(
            config,
            decision="approve",
            summary="Timing metadata should be recorded.",
        ),
    )

    assert len(outcome.command_timings) == 1
    timing = outcome.command_timings[0]
    assert timing.phase == "reviewers"
    assert timing.reviewer_id == "code_reviewer"
    assert timing.command == "run_reviewer"
    assert timing.started_at == "1970-01-01T00:00:10Z"
    assert timing.ended_at == "1970-01-01T00:00:13Z"
    assert timing.duration_sec == 3


def test_reviewer_command_timing_clamps_ended_at_when_clock_skews_backwards(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    import engineeringagent.loop_runtime.phases as phases_module

    time_values = [13.0, 10.0]

    def _fake_time() -> float:
        if time_values:
            return time_values.pop(0)
        return 10.0

    monkeypatch.setattr(phases_module.time, "time", _fake_time)

    config = _base_config()
    config["reviewers"]["code_reviewer"]["trigger"]["phase"] = "feature_done"

    outcome = run_reviewer_phase(
        _iteration_inputs(tmp_path),
        {"id": "FEAT-050"},
        archived_in_iteration=True,
        archived_path=tmp_path / "docs" / "spec" / "features_done" / "FEAT-050.yaml",
        dependencies=_deps(
            config,
            decision="approve",
            summary="Timing metadata should be clamped.",
        ),
    )

    assert len(outcome.command_timings) == 1
    timing = outcome.command_timings[0]
    assert timing.started_at == "1970-01-01T00:00:13Z"
    assert timing.ended_at == "1970-01-01T00:00:13Z"
    assert timing.duration_sec == 0


def test_feature_done_reviewer_warning_blocks_completion(tmp_path: Path) -> None:
    config = _base_config()
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

    outcome = run_reviewer_phase(
        _iteration_inputs(tmp_path),
        {"id": "FEAT-050"},
        archived_in_iteration=True,
        archived_path=archived_path,
        dependencies=deps,
    )

    assert outcome.result == "failed"
    assert outcome.failed_gate == "reviewer_request_changes"
    assert len(restore_calls) == 1


def test_code_simplifier_warning_blocks_completion(tmp_path: Path) -> None:
    config = {
        "profiles": {"loop_fast": ["code_simplifier"]},
        "reviewers": {
            "code_simplifier": {
                "prompt_file": "harness/reviewers/prompts/code_simplifier.md",
                "trigger": {
                    "phase": "feature_done",
                    "on_change": ["src/**/*.py", "tests/**/*.py"],
                },
            }
        },
    }
    state_box: dict[str, dict[str, Any]] = {"state": {"version": "1", "features": {}}}
    restore_calls: list[tuple[Path, Path]] = []
    deps = _deps(
        config,
        decision="warning",
        summary="Simplify nested branching before completion.",
        changed_paths=("src/engineeringagent/phases.py",),
        state_box=state_box,
        restore_calls=restore_calls,
    )
    archived_path = tmp_path / "docs" / "spec" / "features_done" / "FEAT-054.yaml"

    outcome = run_reviewer_phase(
        _iteration_inputs(tmp_path),
        {"id": "FEAT-054"},
        archived_in_iteration=True,
        archived_path=archived_path,
        dependencies=deps,
    )

    assert outcome.result == "failed"
    assert outcome.failed_gate == "reviewer_request_changes"
    assert len(restore_calls) == 1


def test_code_simplifier_approve_allows_completion(tmp_path: Path) -> None:
    config = {
        "profiles": {"loop_fast": ["code_simplifier"]},
        "reviewers": {
            "code_simplifier": {
                "prompt_file": "harness/reviewers/prompts/code_simplifier.md",
                "trigger": {
                    "phase": "feature_done",
                    "on_change": ["src/**/*.py", "tests/**/*.py"],
                },
            }
        },
    }
    state_box: dict[str, dict[str, Any]] = {"state": {"version": "1", "features": {}}}
    restore_calls: list[tuple[Path, Path]] = []
    deps = _deps(
        config,
        decision="approve",
        summary="Advisory reviewer approval should still forward guidance.",
        changed_paths=("src/engineeringagent/phases.py",),
        state_box=state_box,
        restore_calls=restore_calls,
    )
    archived_path = tmp_path / "docs" / "spec" / "features_done" / "FEAT-054.yaml"

    outcome = run_reviewer_phase(
        _iteration_inputs(tmp_path),
        {"id": "FEAT-054"},
        archived_in_iteration=True,
        archived_path=archived_path,
        dependencies=deps,
    )

    assert outcome.result == "passed"
    assert outcome.failed_gate is None
    assert outcome.hook_feedback is None
    assert len(restore_calls) == 0
    assert state_box["state"]["features"].get("FEAT-054") is None


def test_feature_done_reviewer_request_changes_keeps_blocking_on_repeat(
    tmp_path: Path,
) -> None:
    config = _base_config()
    config["reviewers"]["code_reviewer"]["trigger"]["phase"] = "feature_done"
    state_box: dict[str, dict[str, Any]] = {"state": {"version": "1", "features": {}}}
    deps = _deps(
        config,
        decision="request_changes",
        summary="Address parser branch duplication.",
        state_box=state_box,
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
    assert first.failed_gate == "reviewer_request_changes"
    assert second.result == "failed"
    assert second.failed_gate == "reviewer_request_changes"


def test_onboarding_review_feedback_classifies_readme_vs_init_fix_surface(
    tmp_path: Path,
) -> None:
    config = {
        "profiles": {"loop_fast": ["onboarding_review"]},
        "reviewers": {
            "onboarding_review": {
                "prompt_file": "harness/reviewers/prompts/onboarding_review.md",
                "trigger": {
                    "phase": "feature_done",
                    "on_change": ["README.md"],
                },
            }
        },
    }
    deps = _deps(
        config,
        decision="request_changes",
        summary="Bootstrap command from README fails.",
        required_actions=[
            "README.md: clarify the missing bootstrap prerequisite step.",
            "init/scaffold command behavior: ensure init succeeds in a clean temp directory.",
        ],
        changed_paths=("README.md",),
    )

    outcome = run_reviewer_phase(
        _iteration_inputs(tmp_path),
        {"id": "FEAT-052"},
        archived_in_iteration=True,
        archived_path=tmp_path / "docs" / "spec" / "features_done" / "FEAT-052.yaml",
        dependencies=deps,
    )

    assert outcome.result == "failed"
    assert outcome.failed_gate == "reviewer_request_changes"
    assert "README.md: clarify the missing bootstrap prerequisite step." in str(
        outcome.hook_feedback
    )
    assert "init/scaffold command behavior" in str(outcome.hook_feedback)


def test_reviewer_phase_runs_after_gates_before_commit(tmp_path: Path) -> None:
    call_order: list[str] = []

    def _run_implement(*_args: Any, **_kwargs: Any) -> tuple[bool, str | None, str]:
        call_order.append("implement")
        return True, None, ""

    def _run_verification(
        _inputs: FeatureIterationInputs,
        _commands: list[str],
        _deps: VerificationPhaseDependencies,
    ) -> VerificationPhaseOutcome:
        call_order.append("verification")
        return VerificationPhaseOutcome(
            result="passed",
            verification_status="passed",
            verification_failed_command=None,
            verification_output="",
            hook_feedback=None,
        )

    def _run_gates(
        _inputs: FeatureIterationInputs,
        _gates_path: Path,
        _archived_in_iteration: bool,
        _archived_path: Path | None,
        _deps: GatePhaseDependencies,
    ) -> GatePhaseOutcome:
        call_order.append("gates")
        return GatePhaseOutcome(
            result="passed",
            failed_gate=None,
            gate_status="passed",
            gate_output="",
            hook_feedback=None,
        )

    def _run_reviewer(
        _inputs: FeatureIterationInputs,
        _feature: dict[str, Any] | None,
        _archived_in_iteration: bool,
        _archived_path: Path | None,
        _deps: ReviewerPhaseDependencies,
    ) -> ReviewerPhaseOutcome:
        call_order.append("reviewer")
        return ReviewerPhaseOutcome(
            result="passed",
            failed_gate=None,
            reviewer_status="passed",
            reviewer_decision="approve",
            failed_reviewer_id=None,
            reviewer_output="",
            hook_feedback=None,
        )

    def _run_completion(
        _inputs: FeatureIterationInputs,
        _feature: dict[str, Any] | None,
        _archived_in_iteration: bool,
        _archived_path: Path | None,
        _deps: CompletionPhaseDependencies,
    ) -> CompletionCommitOutcome:
        call_order.append("completion")
        return CompletionCommitOutcome(
            completed=True,
            completion_commit_succeeded=True,
            result="passed",
            failed_gate=None,
            next_action="select_next_feature",
            hook_feedback=None,
        )

    iteration_inputs = FeatureIterationInputs(
        project_root=tmp_path,
        feature_path=tmp_path / "docs" / "spec" / "features" / "FEAT-051.yaml",
        gate_profile="loop_fast",
        attempt=1,
        hook_feedback=None,
        verbose_output=False,
    )

    outcome = run_feature_iteration_pipeline(
        iteration_inputs,
        IterationPipelineDependencies(
            evaluate_initial_feature_load=(
                lambda _root, _path: InitialFeatureLoadOutcome(
                    feature={"id": "FEAT-051", "status": "in_progress"},
                    loaded_from_archive=False,
                    result="passed",
                    failed_gate=None,
                    hook_feedback=None,
                )
            ),
            ready_for_active_iteration=lambda *_args, **_kwargs: True,
            touch_active_feature_for_iteration=lambda *_args, **_kwargs: None,
            run_implement_step=_run_implement,
            refresh_feature_after_implement=(
                lambda _root, _path, _started: PostImplementFeatureOutcome(
                    feature={"id": "FEAT-051", "status": "done"},
                    loaded_from_archive=False,
                    archived_in_iteration=True,
                    archived_path=tmp_path
                    / "docs"
                    / "spec"
                    / "features_done"
                    / "FEAT-051.yaml",
                    result="passed",
                    failed_gate=None,
                    hook_feedback=None,
                )
            ),
            should_archive_selected_feature=lambda *_args, **_kwargs: False,
            archive_completed_feature=lambda *_args, **_kwargs: (True, None, None),
            run_gate_phase=_run_gates,
            gate_phase_dependencies=GatePhaseDependencies(
                load_gate_config=lambda _path: {},
                run_profile=lambda *_args, **_kwargs: (True, None, ""),
                restore_archived_feature=lambda *_args, **_kwargs: (True, None),
            ),
            run_verification_phase=_run_verification,
            verification_phase_dependencies=VerificationPhaseDependencies(
                run_shell_command=lambda *_args, **_kwargs: None,
            ),
            run_reviewer_phase=_run_reviewer,
            reviewer_phase_dependencies=ReviewerPhaseDependencies(
                load_reviewer_config=lambda _path: {},
                collect_changed_paths=lambda *_args, **_kwargs: None,
                load_reviewers_state=lambda _root: {"version": "1", "features": {}},
                save_reviewers_state=lambda *_args, **_kwargs: None,
                plan_reviewers=lambda *_args, **_kwargs: [],
                evaluate_cached_reviewer_approval=lambda *_args, **_kwargs: (False, ""),
                run_reviewer=lambda *_args, **_kwargs: {},
                record_reviewer_approval=lambda *_args, **_kwargs: None,
                restore_archived_feature=lambda *_args, **_kwargs: (True, None),
                start_agent=lambda *_args, **_kwargs: None,
            ),
            run_completion_commit_phase=_run_completion,
            completion_phase_dependencies=CompletionPhaseDependencies(
                commit_feature_completion=lambda *_args, **_kwargs: (True, None, ""),
                restore_archived_feature=lambda *_args, **_kwargs: (True, None),
            ),
            write_iteration_telemetry=lambda *_args, **_kwargs: "progress/runs.jsonl",
            git_head_resolver=lambda _root: None,
            print_summary=lambda *_args, **_kwargs: None,
        ),
    )

    assert outcome.result == "passed"
    assert outcome.completed is True
    assert call_order == [
        "implement",
        "verification",
        "gates",
        "reviewer",
        "completion",
    ]
