from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import engineeringagent.loop_runtime.iteration as iteration_module
from engineeringagent.loop_runtime.iteration import (
    IterationPipelineDependencies,
    run_feature_iteration_pipeline,
)
from engineeringagent.loop_runtime.controller import run_loop_controller
from engineeringagent.loop_runtime.models import (
    CompletionCommitOutcome,
    FeatureIterationInputs,
    GatePhaseOutcome,
    ImplementStepResult,
    InitialFeatureLoadOutcome,
    IterationReport,
    IterationTelemetryInputs,
    PostImplementFeatureOutcome,
    ReviewerPhaseOutcome,
    VerificationPhaseOutcome,
)
from engineeringagent.loop_runtime.run_context import LoopRun, RunConfig, RunServices
from engineeringagent.loop_runtime.phases import (
    CompletionPhaseDependencies,
    GatePhaseDependencies,
    ReviewerPhaseDependencies,
)
from engineeringagent.changed_paths import ChangedPathsResult
from engineeringagent.progress.handoff import fallback_implement_progress_envelope


def _passing_implement_result(output: str = "") -> ImplementStepResult:
    return (True, None, output, fallback_implement_progress_envelope(), True)


def test_iteration_report_model_captures_pipeline_observer_contract(
    tmp_path: Path,
) -> None:
    iteration_inputs = FeatureIterationInputs(
        project_root=tmp_path,
        feature_path=tmp_path / "docs" / "spec" / "features" / "FEAT-116.yaml",
        attempt=3,
        hook_feedback=None,
        verbose_output=False,
    )
    telemetry_inputs = IterationTelemetryInputs(
        iteration_inputs=iteration_inputs,
        started=1000.0,
        feature_id="FEAT-116",
        result="passed",
        failed_gate=None,
        next_action="continue_same_feature",
        implement_status="passed",
        gate_status="passed",
        verification_status="passed",
        verification_failed_command=None,
        implement_output="",
        gate_output="",
        verification_output="",
        hook_feedback=None,
    )

    report = IterationReport(
        completed=False,
        result="passed",
        failed_gate=None,
        next_action="continue_same_feature",
        hook_feedback=None,
        feature_id="FEAT-116",
        attempt=3,
        selected_feature_path=str(iteration_inputs.feature_path),
        implement_step="engineeringagent implement",
        archived_selection_path=None,
        verification_status="passed",
        verification_failed_command=None,
        reviewer_status="not_run",
        reviewer_decision=None,
        failed_reviewer_id=None,
        telemetry_inputs=telemetry_inputs,
    )

    assert report.telemetry_inputs.feature_id == "FEAT-116"
    assert report.log_path is None
    assert report.reviewer_status == "not_run"


def test_iteration_pipeline_carries_passed_reviewer_feedback_to_continue(
    tmp_path: Path,
) -> None:
    reviewer_feedback = json.dumps(
        {
            "kind": "reviewer_feedback",
            "phase": "reviewers",
            "reviewer_id": "code_reviewer",
            "reviewer_phase": "feature_done",
            "decision": {
                "decision": "warning",
                "summary": "Minor nits.",
                "required_actions": [],
                "scope_notes": "Reviewed src changes only.",
            },
            "message": "Reviewer provided non-blocking feedback.",
        },
        sort_keys=True,
        ensure_ascii=True,
        separators=(",", ":"),
    )
    iteration_inputs = FeatureIterationInputs(
        project_root=tmp_path,
        feature_path=tmp_path / "docs" / "spec" / "features" / "FEAT-065.yaml",
        attempt=1,
        hook_feedback=None,
        verbose_output=False,
    )

    report = run_feature_iteration_pipeline(
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
            run_implement_step=lambda *_args, **_kwargs: _passing_implement_result(),
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
                restore_archived_feature=lambda *_args, **_kwargs: (True, None),
                collect_changed_paths=lambda *_args, **_kwargs: ChangedPathsResult(
                    paths=(),
                    run_all=True,
                    reason=None,
                ),
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
                collect_changed_paths=lambda *_args, **_kwargs: None,
                restore_archived_feature=lambda *_args, **_kwargs: (True, None),
                run_agent_fn=lambda *_args, **_kwargs: None,
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
        ),
    )

    assert report.result == "passed"
    assert report.completed is False
    assert report.next_action == "continue_same_feature"
    assert report.hook_feedback == reviewer_feedback


def test_iteration_pipeline_archives_before_running_done_transition_verification(
    tmp_path: Path,
) -> None:
    iteration_inputs = FeatureIterationInputs(
        project_root=tmp_path,
        feature_path=tmp_path / "docs" / "spec" / "features" / "FEAT-078.yaml",
        attempt=1,
        hook_feedback=None,
        verbose_output=False,
    )

    archived_before_verification = False

    def _archive_completed_feature(
        _project_root: Path,
        _feature_path: Path,
    ) -> tuple[bool, Path | None, str | None]:
        nonlocal archived_before_verification
        archived_before_verification = True
        return (
            True,
            tmp_path / "docs" / "spec" / "features_done" / "FEAT-078.yaml",
            None,
        )

    def _run_verification_phase(
        _iteration_inputs: FeatureIterationInputs,
        _verification_commands: list[str],
    ) -> VerificationPhaseOutcome:
        if not archived_before_verification:
            return VerificationPhaseOutcome(
                result="failed",
                verification_status="failed:uv run python -m engineeringagent.cli validate",
                verification_failed_command="uv run python -m engineeringagent.cli validate",
                verification_output="done feature still active",
                hook_feedback="done feature still active",
            )
        return VerificationPhaseOutcome(
            result="passed",
            verification_status="passed",
            verification_failed_command=None,
            verification_output="",
            hook_feedback=None,
        )

    report = run_feature_iteration_pipeline(
        iteration_inputs,
        IterationPipelineDependencies(
            evaluate_initial_feature_load=(
                lambda _root, _path: InitialFeatureLoadOutcome(
                    feature={
                        "id": "FEAT-078",
                        "status": "in_progress",
                        "subtasks": [
                            {
                                "id": "ST-001",
                                "status": "in_progress",
                                "verification": [
                                    "uv run python -m engineeringagent.cli validate"
                                ],
                            }
                        ],
                    },
                    loaded_from_archive=False,
                    result="passed",
                    failed_gate=None,
                    hook_feedback=None,
                )
            ),
            ready_for_active_iteration=lambda *_args, **_kwargs: True,
            touch_active_feature_for_iteration=lambda *_args, **_kwargs: None,
            run_implement_step=lambda *_args, **_kwargs: _passing_implement_result(),
            refresh_feature_after_implement=(
                lambda _root, _path, _started: PostImplementFeatureOutcome(
                    feature={
                        "id": "FEAT-078",
                        "status": "done",
                        "subtasks": [
                            {
                                "id": "ST-001",
                                "status": "done",
                                "verification": [
                                    "uv run python -m engineeringagent.cli validate"
                                ],
                            }
                        ],
                    },
                    loaded_from_archive=False,
                    archived_in_iteration=False,
                    archived_path=None,
                    result="passed",
                    failed_gate=None,
                    hook_feedback=None,
                )
            ),
            should_archive_selected_feature=lambda *_args, **_kwargs: True,
            archive_completed_feature=_archive_completed_feature,
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
                restore_archived_feature=lambda *_args, **_kwargs: (True, None),
                collect_changed_paths=lambda *_args, **_kwargs: ChangedPathsResult(
                    paths=(),
                    run_all=True,
                    reason=None,
                ),
            ),
            run_verification_phase=_run_verification_phase,
            run_reviewer_phase=(
                lambda *_args, **_kwargs: ReviewerPhaseOutcome(
                    result="passed",
                    failed_gate=None,
                    reviewer_status="passed",
                    reviewer_decision="approve",
                    failed_reviewer_id=None,
                    reviewer_output="",
                    hook_feedback=None,
                )
            ),
            reviewer_phase_dependencies=ReviewerPhaseDependencies(
                collect_changed_paths=lambda *_args, **_kwargs: None,
                restore_archived_feature=lambda *_args, **_kwargs: (True, None),
                run_agent_fn=lambda *_args, **_kwargs: None,
            ),
            run_completion_commit_phase=(
                lambda *_args, **_kwargs: CompletionCommitOutcome(
                    completed=True,
                    completion_commit_succeeded=True,
                    result="passed",
                    failed_gate=None,
                    next_action="select_next_feature",
                    hook_feedback=None,
                )
            ),
            completion_phase_dependencies=CompletionPhaseDependencies(
                commit_feature_completion=lambda *_args, **_kwargs: (True, None, ""),
                restore_archived_feature=lambda *_args, **_kwargs: (True, None),
            ),
        ),
    )

    assert report.result == "passed"


def test_iteration_pipeline_collects_changed_paths_once_per_iteration(
    tmp_path: Path,
) -> None:
    iteration_inputs = FeatureIterationInputs(
        project_root=tmp_path,
        feature_path=tmp_path / "docs" / "spec" / "features" / "FEAT-999.yaml",
        attempt=1,
        hook_feedback=None,
        verbose_output=False,
    )

    calls = {"count": 0}

    def _collect_changed_paths(_root: Path) -> ChangedPathsResult:
        calls["count"] += 1
        return ChangedPathsResult(paths=("README.md",), run_all=False, reason=None)

    def _run_gate_phase(
        iteration_inputs: FeatureIterationInputs,
        _archived_in_iteration: bool,
        _archived_path: Path | None,
        deps: GatePhaseDependencies,
    ) -> GatePhaseOutcome:
        deps.collect_changed_paths(iteration_inputs.project_root)
        return GatePhaseOutcome(
            result="passed",
            failed_gate=None,
            gate_status="passed",
            gate_output="",
            hook_feedback=None,
        )

    def _run_reviewer_phase(
        iteration_inputs: FeatureIterationInputs,
        _feature: dict[str, Any] | None,
        _archived_in_iteration: bool,
        _archived_path: Path | None,
        deps: ReviewerPhaseDependencies,
    ) -> ReviewerPhaseOutcome:
        deps.collect_changed_paths(iteration_inputs.project_root)
        return ReviewerPhaseOutcome(
            result="passed",
            failed_gate=None,
            reviewer_status="passed",
            reviewer_decision=None,
            failed_reviewer_id=None,
            reviewer_output="",
            hook_feedback=None,
        )

    report = run_feature_iteration_pipeline(
        iteration_inputs,
        IterationPipelineDependencies(
            evaluate_initial_feature_load=(
                lambda _root, _path: InitialFeatureLoadOutcome(
                    feature={
                        "id": "FEAT-999",
                        "status": "in_progress",
                        "subtasks": [{"id": "ST-001", "status": "in_progress"}],
                    },
                    loaded_from_archive=False,
                    result="passed",
                    failed_gate=None,
                    hook_feedback=None,
                )
            ),
            ready_for_active_iteration=lambda *_args, **_kwargs: True,
            touch_active_feature_for_iteration=lambda *_args, **_kwargs: None,
            run_implement_step=lambda *_args, **_kwargs: _passing_implement_result(),
            refresh_feature_after_implement=(
                lambda _root, _path, _started: PostImplementFeatureOutcome(
                    feature={
                        "id": "FEAT-999",
                        "status": "in_progress",
                        "subtasks": [{"id": "ST-001", "status": "in_progress"}],
                    },
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
            run_gate_phase=_run_gate_phase,
            gate_phase_dependencies=GatePhaseDependencies(
                restore_archived_feature=lambda *_args, **_kwargs: (True, None),
                collect_changed_paths=_collect_changed_paths,
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
            run_reviewer_phase=_run_reviewer_phase,
            reviewer_phase_dependencies=ReviewerPhaseDependencies(
                collect_changed_paths=_collect_changed_paths,
                restore_archived_feature=lambda *_args, **_kwargs: (True, None),
                run_agent_fn=lambda *_args, **_kwargs: None,
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
        ),
    )

    assert report.result == "passed"
    assert calls["count"] == 1


def test_iteration_pipeline_records_phase_timings(
    tmp_path: Path, monkeypatch: Any
) -> None:
    times = iter(
        [
            1000.0,  # iteration started
            1001.0,
            1003.0,  # initial_load
            1003.0,
            1008.0,  # implement
            1008.0,
            1010.0,  # archive
            1010.0,
            1010.0,  # verification
            1010.0,
            1013.0,  # gates
            1013.0,
            1014.0,  # reviewers
            1014.0,
            1014.0,  # completion_commit
        ]
    )
    monkeypatch.setattr(iteration_module.time, "time", lambda: next(times))
    monkeypatch.setattr(
        iteration_module,
        "describe_action",
        lambda _project_root, *, action, structured: (
            "backend implement label"
            if (action, structured) == ("implement", False)
            else "unexpected"
        ),
    )

    iteration_inputs = FeatureIterationInputs(
        project_root=tmp_path,
        feature_path=tmp_path / "docs" / "spec" / "features" / "FEAT-065.yaml",
        attempt=1,
        hook_feedback=None,
        verbose_output=False,
    )

    report = run_feature_iteration_pipeline(
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
            run_implement_step=lambda *_args, **_kwargs: _passing_implement_result(),
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
                restore_archived_feature=lambda *_args, **_kwargs: (True, None),
                collect_changed_paths=lambda *_args, **_kwargs: ChangedPathsResult(
                    paths=(),
                    run_all=True,
                    reason=None,
                ),
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
                collect_changed_paths=lambda *_args, **_kwargs: None,
                restore_archived_feature=lambda *_args, **_kwargs: (True, None),
                run_agent_fn=lambda *_args, **_kwargs: None,
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
        ),
    )

    telemetry_inputs = report.telemetry_inputs
    phases = [timing.phase for timing in telemetry_inputs.phase_timings]
    assert phases == [
        "initial_load",
        "implement",
        "archive",
        "verification",
        "gates",
        "reviewers",
        "completion_commit",
    ]
    assert len(telemetry_inputs.command_timings) == 1
    implement_timing = telemetry_inputs.command_timings[0]
    assert implement_timing.phase == "implement"
    assert implement_timing.command == "backend implement label"
    assert implement_timing.started_at == "1970-01-01T00:16:43Z"
    assert implement_timing.ended_at == "1970-01-01T00:16:48Z"
    assert implement_timing.duration_sec == 5
    duration_by_phase = {
        timing.phase: timing.duration_sec for timing in telemetry_inputs.phase_timings
    }
    assert duration_by_phase["initial_load"] == 2
    assert duration_by_phase["implement"] == 5
    assert duration_by_phase["archive"] == 2
    assert duration_by_phase["verification"] == 0
    assert duration_by_phase["gates"] == 3
    assert duration_by_phase["reviewers"] == 1
    assert duration_by_phase["completion_commit"] == 0


def test_timed_phase_clamps_ended_at_when_clock_skews_backwards(
    monkeypatch: Any,
) -> None:
    times = iter([10.0, 9.0])
    monkeypatch.setattr(iteration_module.time, "time", lambda: next(times))

    phase_timings: list[Any] = []
    result = iteration_module._timed_phase(  # noqa: SLF001  # pylint: disable=protected-access
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


def test_run_loop_controller_forwards_looprun_with_resolved_snapshot(
    tmp_path: Path,
) -> None:
    resolved_feature_path = (
        tmp_path / "docs" / "spec" / "features" / "FEAT-078-looprun.yaml"
    )
    captured: dict[str, LoopRun] = {}

    def _run_selected_feature_iterations(loop_run: LoopRun) -> int:
        captured["loop_run"] = loop_run
        return 0

    code = run_loop_controller(
        LoopRun(
            config=RunConfig(
                project_root=tmp_path,
                feature_paths=(resolved_feature_path,),
                dry_run=False,
            ),
            services=RunServices(
                resolve_run_targets=lambda *_args, **_kwargs: [resolved_feature_path],
                emit_run_all_snapshot_feedback=lambda *_args, **_kwargs: None,
                handle_dry_run=lambda *_args, **_kwargs: None,
                enforce_worktree_precondition=lambda *_args, **_kwargs: None,
                run_permission_precheck=lambda **_kwargs: True,
                run_selected_feature_iterations=_run_selected_feature_iterations,
            ),
        )
    )

    assert code == 0
    forwarded_loop_run = captured["loop_run"]
    assert forwarded_loop_run.state.resolved_feature_paths == (resolved_feature_path,)
    assert forwarded_loop_run.state.total_iterations == 0
