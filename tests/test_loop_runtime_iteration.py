from __future__ import annotations

from pathlib import Path
from typing import Any

from engineeringagent.loop_runtime.iteration import (
    IterationPipelineDependencies,
    run_feature_iteration_pipeline,
)
from engineeringagent.loop_runtime.models import (
    CompletionCommitOutcome,
    FeatureIterationInputs,
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
)


def test_iteration_pipeline_carries_passed_reviewer_feedback_to_retry(
    tmp_path: Path,
) -> None:
    reviewer_feedback = "reviewer follow-up summary for next implement pass"
    iteration_inputs = FeatureIterationInputs(
        project_root=tmp_path,
        feature_path=tmp_path / "docs" / "spec" / "features" / "FEAT-065.yaml",
        gate_profile="loop_fast",
        implement_command=None,
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
                    feature={"id": "FEAT-065", "status": "in_progress"},
                    loaded_from_archive=False,
                    result="passed",
                    failed_gate=None,
                    hook_feedback=None,
                )
            ),
            ready_for_active_iteration=lambda *_args, **_kwargs: True,
            touch_active_feature_for_iteration=lambda *_args, **_kwargs: None,
            run_implement_step=lambda *_args, **_kwargs: (True, None, ""),
            refresh_feature_after_implement=(
                lambda _root, _path, _started: PostImplementFeatureOutcome(
                    feature={"id": "FEAT-065", "status": "in_progress"},
                    loaded_from_archive=False,
                    archived_in_iteration=False,
                    archived_path=None,
                    result="passed",
                    failed_gate=None,
                    hook_feedback=None,
                )
            ),
            should_archive_selected_feature=lambda *_args, **_kwargs: False,
            archive_completed_feature=lambda *_args, **_kwargs: (True, None, None),
            run_gate_phase=(
                lambda *_args, **_kwargs: GatePhaseOutcome(
                    result="passed",
                    failed_gate=None,
                    gate_status="passed",
                    gate_output="",
                    hook_feedback=None,
                )
            ),
            gate_phase_dependencies=GatePhaseDependencies(
                load_gate_config=lambda _path: {},
                run_profile=lambda *_args, **_kwargs: (True, None, ""),
                restore_archived_feature=lambda *_args, **_kwargs: (True, None),
            ),
            run_verification_phase=(
                lambda *_args, **_kwargs: VerificationPhaseOutcome(
                    result="passed",
                    verification_status="not_run",
                    verification_failed_command=None,
                    verification_output="",
                    hook_feedback=None,
                )
            ),
            verification_phase_dependencies=VerificationPhaseDependencies(
                run_shell_command=lambda *_args, **_kwargs: None,
            ),
            run_reviewer_phase=(
                lambda *_args, **_kwargs: ReviewerPhaseOutcome(
                    result="passed",
                    failed_gate=None,
                    reviewer_status="passed",
                    reviewer_decision="approve",
                    failed_reviewer_id=None,
                    reviewer_output="[reviewer:code_reviewer] decision=approve",
                    hook_feedback=reviewer_feedback,
                )
            ),
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
            run_completion_commit_phase=(
                lambda *_args, **_kwargs: CompletionCommitOutcome(
                    completed=False,
                    completion_commit_succeeded=False,
                    result="passed",
                    failed_gate=None,
                    next_action="retry_same_feature",
                    hook_feedback=None,
                )
            ),
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
    assert outcome.completed is False
    assert outcome.hook_feedback == reviewer_feedback


def test_iteration_pipeline_records_phase_timings(
    tmp_path: Path, monkeypatch: Any
) -> None:
    import engineeringagent.loop_runtime.iteration as iteration_module

    times = iter(
        [
            1000.0,  # iteration started
            1001.0,
            1003.0,  # initial_load
            1003.0,
            1008.0,  # implement
            1008.0,
            1010.0,  # verification
            1010.0,
            1010.0,  # archive
            1010.0,
            1013.0,  # gates
            1013.0,
            1014.0,  # reviewers
            1014.0,
            1014.0,  # completion_commit
        ]
    )
    monkeypatch.setattr(iteration_module.time, "time", lambda: next(times))

    captured: dict[str, Any] = {}

    def _capture_write_iteration_telemetry(*args: Any, **kwargs: Any) -> str:
        captured["telemetry_inputs"] = args[0]
        return "progress/run-feature-FEAT-065.txt"

    iteration_inputs = FeatureIterationInputs(
        project_root=tmp_path,
        feature_path=tmp_path / "docs" / "spec" / "features" / "FEAT-065.yaml",
        gate_profile="loop_fast",
        implement_command=None,
        skip_implement=False,
        attempt=1,
        hook_feedback=None,
        verbose_output=False,
    )

    run_feature_iteration_pipeline(
        iteration_inputs,
        IterationPipelineDependencies(
            evaluate_initial_feature_load=(
                lambda _root, _path: InitialFeatureLoadOutcome(
                    feature={"id": "FEAT-065", "status": "in_progress"},
                    loaded_from_archive=False,
                    result="passed",
                    failed_gate=None,
                    hook_feedback=None,
                )
            ),
            ready_for_active_iteration=lambda *_args, **_kwargs: True,
            touch_active_feature_for_iteration=lambda *_args, **_kwargs: None,
            run_implement_step=lambda *_args, **_kwargs: (True, None, ""),
            refresh_feature_after_implement=(
                lambda _root, _path, _started: PostImplementFeatureOutcome(
                    feature={"id": "FEAT-065", "status": "in_progress"},
                    loaded_from_archive=False,
                    archived_in_iteration=False,
                    archived_path=None,
                    result="passed",
                    failed_gate=None,
                    hook_feedback=None,
                )
            ),
            should_archive_selected_feature=lambda *_args, **_kwargs: False,
            archive_completed_feature=lambda *_args, **_kwargs: (True, None, None),
            run_gate_phase=(
                lambda *_args, **_kwargs: GatePhaseOutcome(
                    result="passed",
                    failed_gate=None,
                    gate_status="passed",
                    gate_output="",
                    hook_feedback=None,
                )
            ),
            gate_phase_dependencies=GatePhaseDependencies(
                load_gate_config=lambda _path: {},
                run_profile=lambda *_args, **_kwargs: (True, None, ""),
                restore_archived_feature=lambda *_args, **_kwargs: (True, None),
            ),
            run_verification_phase=(
                lambda *_args, **_kwargs: VerificationPhaseOutcome(
                    result="passed",
                    verification_status="not_run",
                    verification_failed_command=None,
                    verification_output="",
                    hook_feedback=None,
                )
            ),
            verification_phase_dependencies=VerificationPhaseDependencies(
                run_shell_command=lambda *_args, **_kwargs: None,
            ),
            run_reviewer_phase=(
                lambda *_args, **_kwargs: ReviewerPhaseOutcome(
                    result="passed",
                    failed_gate=None,
                    reviewer_status="passed",
                    reviewer_decision="approve",
                    failed_reviewer_id=None,
                    reviewer_output="[reviewer:code_reviewer] decision=approve",
                    hook_feedback=None,
                )
            ),
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
            run_completion_commit_phase=(
                lambda *_args, **_kwargs: CompletionCommitOutcome(
                    completed=False,
                    completion_commit_succeeded=False,
                    result="passed",
                    failed_gate=None,
                    next_action="retry_same_feature",
                    hook_feedback=None,
                )
            ),
            completion_phase_dependencies=CompletionPhaseDependencies(
                commit_feature_completion=lambda *_args, **_kwargs: (True, None, ""),
                restore_archived_feature=lambda *_args, **_kwargs: (True, None),
            ),
            write_iteration_telemetry=_capture_write_iteration_telemetry,
            git_head_resolver=lambda _root: None,
            print_summary=lambda *_args, **_kwargs: None,
        ),
    )

    telemetry_inputs = captured["telemetry_inputs"]
    phases = [timing.phase for timing in telemetry_inputs.phase_timings]
    assert phases == [
        "initial_load",
        "implement",
        "verification",
        "archive",
        "gates",
        "reviewers",
        "completion_commit",
    ]
    assert len(telemetry_inputs.command_timings) == 1
    implement_command = telemetry_inputs.command_timings[0]
    assert implement_command.phase == "implement"
    assert implement_command.command.startswith("opencode run --agent")
    assert implement_command.started_at == "1970-01-01T00:16:43Z"
    assert implement_command.ended_at == "1970-01-01T00:16:48Z"
    assert implement_command.duration_sec == 5
    duration_by_phase = {
        timing.phase: timing.duration_sec for timing in telemetry_inputs.phase_timings
    }
    assert duration_by_phase["initial_load"] == 2
    assert duration_by_phase["implement"] == 5
    assert duration_by_phase["verification"] == 2
    assert duration_by_phase["archive"] == 0
    assert duration_by_phase["gates"] == 3
    assert duration_by_phase["reviewers"] == 1
    assert duration_by_phase["completion_commit"] == 0


def test_timed_phase_clamps_ended_at_when_clock_skews_backwards(
    monkeypatch: Any,
) -> None:
    import engineeringagent.loop_runtime.iteration as iteration_module

    times = iter([10.0, 9.0])
    monkeypatch.setattr(iteration_module.time, "time", lambda: next(times))

    phase_timings: list[Any] = []
    result = iteration_module._timed_phase(  # noqa: SLF001
        phase_timings,
        "initial_load",
        lambda: "ok",
    )

    assert result == "ok"
    assert len(phase_timings) == 1
    timing = phase_timings[0]
    assert timing.started_at == "1970-01-01T00:00:10Z"
    assert timing.ended_at == "1970-01-01T00:00:10Z"
    assert timing.duration_sec == 0
