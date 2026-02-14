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


def test_code_simplifier_advisory_requires_one_followup_implement_pass(
    tmp_path: Path,
) -> None:
    config = {
        "profiles": {"loop_fast": ["code_simplifier"]},
        "reviewers": {
            "code_simplifier": {
                "prompt_file": "harness/reviewers/prompts/code_simplifier.md",
                "trigger": {
                    "phase": "feature_done",
                    "on_change": ["src/**/*.py", "tests/**/*.py"],
                },
                "approval": {"mode": "advisory"},
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

    first = run_reviewer_phase(
        _iteration_inputs(tmp_path),
        {"id": "FEAT-054"},
        archived_in_iteration=True,
        archived_path=archived_path,
        dependencies=deps,
    )
    second = run_reviewer_phase(
        _iteration_inputs(tmp_path),
        {"id": "FEAT-054"},
        archived_in_iteration=True,
        archived_path=archived_path,
        dependencies=deps,
    )

    assert first.result == "failed"
    assert first.failed_gate == "reviewer_advisory_followup"
    assert second.result == "passed"
    assert second.failed_gate is None
    assert len(restore_calls) == 1


def test_code_simplifier_advisory_does_not_hard_block_by_default(
    tmp_path: Path,
) -> None:
    config = {
        "profiles": {"loop_fast": ["code_simplifier"]},
        "reviewers": {
            "code_simplifier": {
                "prompt_file": "harness/reviewers/prompts/code_simplifier.md",
                "trigger": {
                    "phase": "iteration_end",
                    "on_change": ["src/**/*.py", "tests/**/*.py"],
                },
                "approval": {"mode": "advisory"},
            }
        },
    }
    outcome = run_reviewer_phase(
        _iteration_inputs(tmp_path),
        {"id": "FEAT-054"},
        archived_in_iteration=False,
        archived_path=None,
        dependencies=_deps(
            config,
            decision="warning",
            summary="Advisory simplification suggestions only.",
            changed_paths=("src/engineeringagent/phases.py",),
        ),
    )

    assert outcome.result == "passed"
    assert outcome.failed_gate is None
    assert outcome.reviewer_status == "passed:advisory"
    assert outcome.reviewer_decision == "warning"
    assert "reviewer 'code_simplifier' advisory feedback" in str(outcome.hook_feedback)


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


def test_readme_process_request_changes_blocks_until_retry_or_exhaustion(
    tmp_path: Path,
) -> None:
    config = {
        "profiles": {"loop_fast": ["readme_process"]},
        "reviewers": {
            "readme_process": {
                "prompt_file": "harness/reviewers/prompts/readme_process.md",
                "trigger": {
                    "phase": "feature_done",
                    "on_change": ["README.md"],
                },
                "approval": {
                    "mode": "blocking",
                    "max_retries": 1,
                    "continue_on_exhausted": False,
                },
            }
        },
    }
    state_box: dict[str, dict[str, Any]] = {"state": {"version": "1", "features": {}}}
    deps = _deps(
        config,
        decision="request_changes",
        summary="README bootstrap run fails in clean room.",
        changed_paths=("README.md",),
        state_box=state_box,
    )

    first = run_reviewer_phase(
        _iteration_inputs(tmp_path),
        {"id": "FEAT-052"},
        archived_in_iteration=True,
        archived_path=tmp_path / "docs" / "spec" / "features_done" / "FEAT-052.yaml",
        dependencies=deps,
    )
    second = run_reviewer_phase(
        _iteration_inputs(tmp_path),
        {"id": "FEAT-052"},
        archived_in_iteration=True,
        archived_path=tmp_path / "docs" / "spec" / "features_done" / "FEAT-052.yaml",
        dependencies=deps,
    )

    assert first.result == "failed"
    assert first.failed_gate == "reviewer_blocking"
    assert second.result == "failed"
    assert second.failed_gate == "reviewer_blocking_exhausted"


def test_readme_process_feedback_classifies_readme_vs_init_fix_surface(
    tmp_path: Path,
) -> None:
    config = {
        "profiles": {"loop_fast": ["readme_process"]},
        "reviewers": {
            "readme_process": {
                "prompt_file": "harness/reviewers/prompts/readme_process.md",
                "trigger": {
                    "phase": "feature_done",
                    "on_change": ["README.md"],
                },
                "approval": {"mode": "blocking"},
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
    assert outcome.failed_gate == "reviewer_blocking"
    assert "README.md: clarify the missing bootstrap prerequisite step." in str(
        outcome.hook_feedback
    )
    assert "init/scaffold command behavior" in str(outcome.hook_feedback)


def test_readme_process_exhaustion_continues_with_warning_by_default(
    tmp_path: Path,
) -> None:
    config = {
        "profiles": {"loop_fast": ["readme_process"]},
        "reviewers": {
            "readme_process": {
                "prompt_file": "harness/reviewers/prompts/readme_process.md",
                "trigger": {
                    "phase": "feature_done",
                    "on_change": ["README.md"],
                },
                "approval": {
                    "mode": "blocking",
                    "max_retries": 1,
                },
            }
        },
    }
    state_box: dict[str, dict[str, Any]] = {"state": {"version": "1", "features": {}}}
    deps = _deps(
        config,
        decision="request_changes",
        summary="README bootstrap leaves scaffold incomplete.",
        changed_paths=("README.md",),
        state_box=state_box,
    )

    first = run_reviewer_phase(
        _iteration_inputs(tmp_path),
        {"id": "FEAT-052"},
        archived_in_iteration=True,
        archived_path=tmp_path / "docs" / "spec" / "features_done" / "FEAT-052.yaml",
        dependencies=deps,
    )
    second = run_reviewer_phase(
        _iteration_inputs(tmp_path),
        {"id": "FEAT-052"},
        archived_in_iteration=True,
        archived_path=tmp_path / "docs" / "spec" / "features_done" / "FEAT-052.yaml",
        dependencies=deps,
    )

    assert first.result == "failed"
    assert first.failed_gate == "reviewer_blocking"
    assert second.result == "passed"
    assert second.failed_gate is None
    assert second.reviewer_status == "passed:blocking_exhausted_continue"
    assert "exhausted retries" in str(second.hook_feedback)


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
        implement_command=None,
        opencode_prompt=None,
        skip_implement=False,
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
                advisory_followup_required=lambda *_args, **_kwargs: False,
                set_advisory_followup_required=lambda *_args, **_kwargs: None,
                clear_advisory_followup_required=lambda *_args, **_kwargs: None,
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
