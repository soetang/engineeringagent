from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

import engineeringagent.loop_runtime.iteration as iteration_module
from engineeringagent.adapters.progress.handoff import (
    fallback_implement_progress_envelope,
)
from engineeringagent.adapters.runtime.run_loop_context import (
    LoopRun,
    RunConfig,
    RunServices,
)
from engineeringagent.application.feature_iteration_models import (
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
from engineeringagent.bootstrap.runtime_execution import run_loop_controller
from engineeringagent.domain.quality import ChangedPathsResult
from engineeringagent.loop_runtime.feature_state import (
    archive_completed_feature,
    restore_archived_feature,
)
from engineeringagent.loop_runtime.iteration import (
    IterationPipelineDependencies,
    _timed_phase,
    run_feature_iteration_pipeline,
)
from engineeringagent.loop_runtime.phases import (
    CompletionPhaseDependencies,
    GatePhaseDependencies,
    ReviewerPhaseDependencies,
)
from tests.loop.feature_iteration_support import (
    base_feature,
    make_bundled_project_root,
)


def _passing_implement_result(output: str = "") -> ImplementStepResult:
    return (True, None, output, fallback_implement_progress_envelope(), True)


def test_iteration_report_model_captures_pipeline_observer_contract(
    tmp_path: Path,
) -> None:
    iteration_inputs = FeatureIterationInputs(
        project_root=tmp_path,
        feature_path=tmp_path / "docs" / "spec" / "features" / "FEAT-116.yaml",
        attempt=3,
        feedback=None,
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
        feedback=None,
    )

    report = IterationReport(
        completed=False,
        result="passed",
        failed_gate=None,
        next_action="continue_same_feature",
        feedback=None,
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
                "decision": "approve",
                "summary": "Looks good.",
                "required_actions": [],
                "scope_notes": "Reviewed src changes only.",
            },
            "message": "Reviewer approved the changes.",
        },
        sort_keys=True,
        ensure_ascii=True,
        separators=(",", ":"),
    )
    iteration_inputs = FeatureIterationInputs(
        project_root=tmp_path,
        feature_path=tmp_path / "docs" / "spec" / "features" / "FEAT-065.yaml",
        attempt=1,
        feedback=None,
        verbose_output=False,
    )

    report = run_feature_iteration_pipeline(
        iteration_inputs,
        IterationPipelineDependencies(
            evaluate_initial_feature_load=(
                lambda _path: InitialFeatureLoadOutcome(
                    feature={"id": "FEAT-065", "status": "in_progress"},
                    result="passed",
                    failed_gate=None,
                    feedback=None,
                )
            ),
            ready_for_active_iteration=lambda *_args, **_kwargs: True,
            touch_active_feature_for_iteration=lambda *_args, **_kwargs: None,
            run_implement_step=lambda *_args, **_kwargs: _passing_implement_result(),
            refresh_feature_after_implement=(
                lambda _project_root, _feature_path: PostImplementFeatureOutcome(
                    feature={"id": "FEAT-065", "status": "in_progress"},
                    archived_in_iteration=False,
                    archived_path=None,
                    result="passed",
                    failed_gate=None,
                    feedback=None,
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
                    feedback=None,
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
                    feedback=None,
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
                    feedback=reviewer_feedback,
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
                    feedback=None,
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
    assert report.feedback == reviewer_feedback


def test_iteration_pipeline_tracks_bundled_plan_phase_progress_metadata(
    tmp_path: Path,
) -> None:
    feature_data = {
        **base_feature(status="in_progress"),
        "planning_tier": "planned",
        "artifacts": {"plan": "plan.md"},
    }
    feature_data.pop("subtasks", None)
    project_root, feature_path, _plan_path = make_bundled_project_root(
        tmp_path,
        feature_data=feature_data,
        plan_frontmatter={
            "plan_id": "FEAT-900",
            "feature_id": "FEAT-900",
            "status": "in_progress",
            "source_spec": "spec.yaml",
            "planning_tier": "planned",
            "phases": [
                {
                    "id": "P1",
                    "title": "Completed setup",
                    "status": "done",
                },
                {
                    "id": "P2",
                    "title": "Track bundled phase progress",
                    "status": "in_progress",
                },
            ],
        },
    )
    iteration_inputs = FeatureIterationInputs(
        project_root=project_root,
        feature_path=feature_path,
        attempt=1,
        feedback=None,
        verbose_output=False,
    )

    report = run_feature_iteration_pipeline(
        iteration_inputs,
        IterationPipelineDependencies(
            evaluate_initial_feature_load=(
                lambda _path: InitialFeatureLoadOutcome(
                    feature=feature_data,
                    result="passed",
                    failed_gate=None,
                    feedback=None,
                )
            ),
            ready_for_active_iteration=lambda *_args, **_kwargs: False,
            touch_active_feature_for_iteration=lambda *_args, **_kwargs: None,
            run_implement_step=lambda *_args, **_kwargs: _passing_implement_result(),
            refresh_feature_after_implement=(
                lambda _project_root, _feature_path: PostImplementFeatureOutcome(
                    feature=feature_data,
                    archived_in_iteration=False,
                    archived_path=None,
                    result="passed",
                    failed_gate=None,
                    feedback=None,
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
                    feedback=None,
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
                    feedback=None,
                )
            ),
            run_reviewer_phase=(
                lambda *_args, **_kwargs: ReviewerPhaseOutcome(
                    result="passed",
                    failed_gate=None,
                    reviewer_status="not_run",
                    reviewer_decision=None,
                    failed_reviewer_id=None,
                    reviewer_output="",
                    feedback=None,
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
                    feedback=None,
                )
            ),
            completion_phase_dependencies=CompletionPhaseDependencies(
                commit_feature_completion=lambda *_args, **_kwargs: (True, None, ""),
                restore_archived_feature=lambda *_args, **_kwargs: (True, None),
            ),
        ),
    )

    assert report.telemetry_inputs.progress_kind == "phase"
    assert report.telemetry_inputs.progress_id == "P2"
    assert report.telemetry_inputs.progress_title == "Track bundled phase progress"


def test_iteration_pipeline_keeps_phase_progress_kind_when_bundled_plan_is_invalid(
    tmp_path: Path,
) -> None:
    feature_data = {
        **base_feature(status="in_progress"),
        "planning_tier": "planned",
        "artifacts": {"plan": "plan.md"},
    }
    feature_data.pop("subtasks", None)
    project_root, feature_path, plan_path = make_bundled_project_root(
        tmp_path,
        feature_data=feature_data,
        plan_frontmatter={
            "plan_id": "FEAT-900",
            "feature_id": "FEAT-900",
            "status": "in_progress",
            "source_spec": "spec.yaml",
            "planning_tier": "planned",
            "phases": [
                {
                    "id": "P1",
                    "title": "Track bundled phase progress",
                    "status": "in_progress",
                }
            ],
        },
    )
    plan_path.write_text("---\ninvalid: [\n---\n# Plan\n", encoding="utf-8")
    iteration_inputs = FeatureIterationInputs(
        project_root=project_root,
        feature_path=feature_path,
        attempt=1,
        feedback=None,
        verbose_output=False,
    )

    report = run_feature_iteration_pipeline(
        iteration_inputs,
        IterationPipelineDependencies(
            evaluate_initial_feature_load=(
                lambda _path: InitialFeatureLoadOutcome(
                    feature=feature_data,
                    result="passed",
                    failed_gate=None,
                    feedback=None,
                )
            ),
            ready_for_active_iteration=lambda *_args, **_kwargs: False,
            touch_active_feature_for_iteration=lambda *_args, **_kwargs: None,
            run_implement_step=lambda *_args, **_kwargs: _passing_implement_result(),
            refresh_feature_after_implement=(
                lambda _project_root, _feature_path: PostImplementFeatureOutcome(
                    feature=feature_data,
                    archived_in_iteration=False,
                    archived_path=None,
                    result="passed",
                    failed_gate=None,
                    feedback=None,
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
                    feedback=None,
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
                    feedback=None,
                )
            ),
            run_reviewer_phase=(
                lambda *_args, **_kwargs: ReviewerPhaseOutcome(
                    result="passed",
                    failed_gate=None,
                    reviewer_status="not_run",
                    reviewer_decision=None,
                    failed_reviewer_id=None,
                    reviewer_output="",
                    feedback=None,
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
                    feedback=None,
                )
            ),
            completion_phase_dependencies=CompletionPhaseDependencies(
                commit_feature_completion=lambda *_args, **_kwargs: (True, None, ""),
                restore_archived_feature=lambda *_args, **_kwargs: (True, None),
            ),
        ),
    )

    assert report.telemetry_inputs.progress_kind == "phase"
    assert report.telemetry_inputs.progress_id is None
    assert report.telemetry_inputs.progress_title is None


def test_iteration_pipeline_tracks_direct_bundle_feature_progress_metadata(
    tmp_path: Path,
) -> None:
    project_root = tmp_path
    feature_path = (
        project_root / "docs" / "spec" / "features" / "FEAT-901-direct-bundle" / "spec.yaml"
    )
    feature_path.parent.mkdir(parents=True, exist_ok=True)
    feature_data = {
        "id": "FEAT-901",
        "title": "Track direct bundled feature progress",
        "type": "spec",
        "expected_commit_subject": "spec: track direct bundled feature progress",
        "planning_tier": "direct",
        "status": "in_progress",
        "priority": "high",
        "objective": "Ensure telemetry stays on the bundled feature surface.",
        "acceptance": ["Direct bundled features keep feature-level progress wording."],
        "artifacts": {},
    }
    feature_path.write_text(json.dumps(feature_data), encoding="utf-8")
    iteration_inputs = FeatureIterationInputs(
        project_root=project_root,
        feature_path=feature_path,
        attempt=1,
        feedback=None,
        verbose_output=False,
    )

    report = run_feature_iteration_pipeline(
        iteration_inputs,
        IterationPipelineDependencies(
            evaluate_initial_feature_load=(
                lambda _path: InitialFeatureLoadOutcome(
                    feature=feature_data,
                    result="passed",
                    failed_gate=None,
                    feedback=None,
                )
            ),
            ready_for_active_iteration=lambda *_args, **_kwargs: False,
            touch_active_feature_for_iteration=lambda *_args, **_kwargs: None,
            run_implement_step=lambda *_args, **_kwargs: _passing_implement_result(),
            refresh_feature_after_implement=(
                lambda _project_root, _feature_path: PostImplementFeatureOutcome(
                    feature=feature_data,
                    archived_in_iteration=False,
                    archived_path=None,
                    result="passed",
                    failed_gate=None,
                    feedback=None,
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
                    feedback=None,
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
                    feedback=None,
                )
            ),
            run_reviewer_phase=(
                lambda *_args, **_kwargs: ReviewerPhaseOutcome(
                    result="passed",
                    failed_gate=None,
                    reviewer_status="not_run",
                    reviewer_decision=None,
                    failed_reviewer_id=None,
                    reviewer_output="",
                    feedback=None,
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
                    feedback=None,
                )
            ),
            completion_phase_dependencies=CompletionPhaseDependencies(
                commit_feature_completion=lambda *_args, **_kwargs: (True, None, ""),
                restore_archived_feature=lambda *_args, **_kwargs: (True, None),
            ),
        ),
    )

    assert report.telemetry_inputs.progress_kind == "feature"
    assert report.telemetry_inputs.progress_id == "FEAT-901"
    assert report.telemetry_inputs.progress_title == "Track direct bundled feature progress"


def test_iteration_pipeline_uses_feature_progress_kind_without_plan_unit(
    tmp_path: Path,
) -> None:
    feature_data = base_feature(status="in_progress")
    feature_data["subtasks"] = []
    iteration_inputs = FeatureIterationInputs(
        project_root=tmp_path,
        feature_path=tmp_path / "docs" / "spec" / "features" / "FEAT-900" / "spec.yaml",
        attempt=1,
        feedback=None,
        verbose_output=False,
    )

    report = run_feature_iteration_pipeline(
        iteration_inputs,
        IterationPipelineDependencies(
            evaluate_initial_feature_load=(
                lambda _path: InitialFeatureLoadOutcome(
                    feature=feature_data,
                    result="passed",
                    failed_gate=None,
                    feedback=None,
                )
            ),
            ready_for_active_iteration=lambda *_args, **_kwargs: False,
            touch_active_feature_for_iteration=lambda *_args, **_kwargs: None,
            run_implement_step=lambda *_args, **_kwargs: _passing_implement_result(),
            refresh_feature_after_implement=(
                lambda _project_root, _feature_path: PostImplementFeatureOutcome(
                    feature=feature_data,
                    archived_in_iteration=False,
                    archived_path=None,
                    result="passed",
                    failed_gate=None,
                    feedback=None,
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
                    feedback=None,
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
                    feedback=None,
                )
            ),
            run_reviewer_phase=(
                lambda *_args, **_kwargs: ReviewerPhaseOutcome(
                    result="passed",
                    failed_gate=None,
                    reviewer_status="not_run",
                    reviewer_decision=None,
                    failed_reviewer_id=None,
                    reviewer_output="",
                    feedback=None,
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
                    feedback=None,
                )
            ),
            completion_phase_dependencies=CompletionPhaseDependencies(
                commit_feature_completion=lambda *_args, **_kwargs: (True, None, ""),
                restore_archived_feature=lambda *_args, **_kwargs: (True, None),
            ),
        ),
    )

    assert report.telemetry_inputs.progress_kind == "feature"
    assert report.telemetry_inputs.progress_id == "FEAT-900"
    assert report.telemetry_inputs.progress_title == "Feature iteration smoke test"


def test_iteration_pipeline_recovers_phase_metadata_from_parseable_invalid_plan_contract(
    tmp_path: Path,
) -> None:
    feature_data = {
        **base_feature(status="in_progress"),
        "planning_tier": "planned",
        "artifacts": {"plan": "plan.md"},
    }
    feature_data.pop("subtasks", None)
    project_root, feature_path, _plan_path = make_bundled_project_root(
        tmp_path,
        feature_data=feature_data,
        plan_frontmatter={
            "plan_id": "FEAT-900",
            "status": "in_progress",
            "source_spec": "spec.yaml",
            "planning_tier": "planned",
            "phases": [
                {
                    "id": "P1",
                    "title": "Recover phase metadata from invalid plan contract",
                    "status": "in_progress",
                }
            ],
        },
    )
    iteration_inputs = FeatureIterationInputs(
        project_root=project_root,
        feature_path=feature_path,
        attempt=1,
        feedback=None,
        verbose_output=False,
    )

    report = run_feature_iteration_pipeline(
        iteration_inputs,
        IterationPipelineDependencies(
            evaluate_initial_feature_load=(
                lambda _path: InitialFeatureLoadOutcome(
                    feature=feature_data,
                    result="passed",
                    failed_gate=None,
                    feedback=None,
                )
            ),
            ready_for_active_iteration=lambda *_args, **_kwargs: False,
            touch_active_feature_for_iteration=lambda *_args, **_kwargs: None,
            run_implement_step=lambda *_args, **_kwargs: _passing_implement_result(),
            refresh_feature_after_implement=(
                lambda _project_root, _feature_path: PostImplementFeatureOutcome(
                    feature=feature_data,
                    archived_in_iteration=False,
                    archived_path=None,
                    result="passed",
                    failed_gate=None,
                    feedback=None,
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
                    feedback=None,
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
                    feedback=None,
                )
            ),
            run_reviewer_phase=(
                lambda *_args, **_kwargs: ReviewerPhaseOutcome(
                    result="passed",
                    failed_gate=None,
                    reviewer_status="not_run",
                    reviewer_decision=None,
                    failed_reviewer_id=None,
                    reviewer_output="",
                    feedback=None,
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
                    feedback=None,
                )
            ),
            completion_phase_dependencies=CompletionPhaseDependencies(
                commit_feature_completion=lambda *_args, **_kwargs: (True, None, ""),
                restore_archived_feature=lambda *_args, **_kwargs: (True, None),
            ),
        ),
    )

    assert report.telemetry_inputs.progress_kind == "phase"
    assert report.telemetry_inputs.progress_id == "P1"
    assert (
        report.telemetry_inputs.progress_title
        == "Recover phase metadata from invalid plan contract"
    )


def test_iteration_pipeline_preserves_phase_metadata_after_bundled_archive(
    tmp_path: Path,
) -> None:
    feature_data = {
        **base_feature(status="in_progress"),
        "planning_tier": "planned",
        "artifacts": {"plan": "plan.md"},
    }
    feature_data.pop("subtasks", None)
    project_root, feature_path, _plan_path = make_bundled_project_root(
        tmp_path,
        feature_data=feature_data,
        plan_frontmatter={
            "plan_id": "FEAT-900",
            "feature_id": "FEAT-900",
            "status": "in_progress",
            "source_spec": "spec.yaml",
            "planning_tier": "planned",
            "phases": [
                {
                    "id": "P1",
                    "title": "Preserve archived bundled phase metadata",
                    "status": "in_progress",
                }
            ],
        },
    )
    iteration_inputs = FeatureIterationInputs(
        project_root=project_root,
        feature_path=feature_path,
        attempt=1,
        feedback=None,
        verbose_output=False,
    )

    def _refresh_feature_after_implement(
        _project_root: Path,
        selected_feature_path: Path,
    ) -> PostImplementFeatureOutcome:
        refreshed_feature = base_feature(status="done")
        refreshed_feature["planning_tier"] = "planned"
        refreshed_feature["artifacts"] = {"plan": "plan.md"}
        refreshed_feature.pop("subtasks", None)
        selected_feature_path.write_text(
            json.dumps(refreshed_feature),
            encoding="utf-8",
        )
        return PostImplementFeatureOutcome(
            feature=refreshed_feature,
            archived_in_iteration=False,
            archived_path=None,
            result="passed",
            failed_gate=None,
            feedback=None,
        )

    def _run_reviewer_phase(
        _inputs: FeatureIterationInputs,
        _feature: dict[str, Any] | None,
        _archived_in_iteration: bool,
        archived_path: Path | None,
        _deps: ReviewerPhaseDependencies,
    ) -> ReviewerPhaseOutcome:
        if archived_path is not None:
            restore_archived_feature(archived_path, feature_path)
        return ReviewerPhaseOutcome(
            result="failed",
            failed_gate="request_changes",
            reviewer_status="failed:request_changes",
            reviewer_decision="request_changes",
            failed_reviewer_id="reviewer_1",
            reviewer_output="request changes",
            feedback="request changes",
            archived_rolled_back=True,
        )

    report = run_feature_iteration_pipeline(
        iteration_inputs,
        IterationPipelineDependencies(
            evaluate_initial_feature_load=(
                lambda _path: InitialFeatureLoadOutcome(
                    feature=feature_data,
                    result="passed",
                    failed_gate=None,
                    feedback=None,
                )
            ),
            ready_for_active_iteration=lambda *_args, **_kwargs: True,
            touch_active_feature_for_iteration=lambda *_args, **_kwargs: None,
            run_implement_step=lambda *_args, **_kwargs: _passing_implement_result(),
            refresh_feature_after_implement=_refresh_feature_after_implement,
            should_archive_selected_feature=lambda *_args, **_kwargs: True,
            archive_completed_feature=archive_completed_feature,
            run_gate_phase=(
                lambda *_args, **_kwargs: GatePhaseOutcome(
                    result="passed",
                    failed_gate=None,
                    gate_status="passed",
                    gate_output="",
                    feedback=None,
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
                    feedback=None,
                )
            ),
            run_reviewer_phase=(
                lambda *_args, **_kwargs: ReviewerPhaseOutcome(
                    result="passed",
                    failed_gate=None,
                    reviewer_status="not_run",
                    reviewer_decision=None,
                    failed_reviewer_id=None,
                    reviewer_output="",
                    feedback=None,
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
                    feedback=None,
                )
            ),
            completion_phase_dependencies=CompletionPhaseDependencies(
                commit_feature_completion=lambda *_args, **_kwargs: (True, None, ""),
                restore_archived_feature=lambda *_args, **_kwargs: (True, None),
            ),
        ),
    )

    assert report.telemetry_inputs.progress_kind == "phase"
    assert report.telemetry_inputs.progress_id == "P1"
    assert (
        report.telemetry_inputs.progress_title
        == "Preserve archived bundled phase metadata"
    )
    assert (
        project_root
        / "docs"
        / "spec"
        / "features_done"
        / "FEAT-900-bundled-smoke-test"
        / "spec.yaml"
    ).exists()


def test_iteration_pipeline_clears_archived_selection_after_reviewer_rollback(
    tmp_path: Path,
) -> None:
    feature_data = {
        **base_feature(status="in_progress"),
        "planning_tier": "planned",
        "artifacts": {"plan": "plan.md"},
    }
    feature_data.pop("subtasks", None)
    project_root, feature_path, _plan_path = make_bundled_project_root(
        tmp_path,
        feature_data=feature_data,
        plan_frontmatter={
            "plan_id": "FEAT-900",
            "feature_id": "FEAT-900",
            "status": "in_progress",
            "source_spec": "spec.yaml",
            "planning_tier": "planned",
            "phases": [
                {
                    "id": "P1",
                    "title": "Rollback reviewer archive state",
                    "status": "in_progress",
                }
            ],
        },
    )
    iteration_inputs = FeatureIterationInputs(
        project_root=project_root,
        feature_path=feature_path,
        attempt=1,
        feedback=None,
        verbose_output=False,
    )

    def _refresh_feature_after_implement(
        _project_root: Path,
        selected_feature_path: Path,
    ) -> PostImplementFeatureOutcome:
        refreshed_feature = base_feature(status="done")
        refreshed_feature["planning_tier"] = "planned"
        refreshed_feature["artifacts"] = {"plan": "plan.md"}
        refreshed_feature.pop("subtasks", None)
        selected_feature_path.write_text(
            json.dumps(refreshed_feature),
            encoding="utf-8",
        )
        return PostImplementFeatureOutcome(
            feature=refreshed_feature,
            archived_in_iteration=False,
            archived_path=None,
            result="passed",
            failed_gate=None,
            feedback=None,
        )

    def _run_reviewer_phase(
        _inputs: FeatureIterationInputs,
        _feature: dict[str, Any] | None,
        _archived_in_iteration: bool,
        archived_path: Path | None,
        _deps: ReviewerPhaseDependencies,
    ) -> ReviewerPhaseOutcome:
        if archived_path is not None:
            restore_archived_feature(archived_path, feature_path)
        return ReviewerPhaseOutcome(
            result="failed",
            failed_gate="request_changes",
            reviewer_status="failed:request_changes",
            reviewer_decision="request_changes",
            failed_reviewer_id="reviewer_1",
            reviewer_output="request changes",
            feedback="request changes",
            archived_rolled_back=True,
        )

    report = run_feature_iteration_pipeline(
        iteration_inputs,
        IterationPipelineDependencies(
            evaluate_initial_feature_load=(
                lambda _path: InitialFeatureLoadOutcome(
                    feature=feature_data,
                    result="passed",
                    failed_gate=None,
                    feedback=None,
                )
            ),
            ready_for_active_iteration=lambda *_args, **_kwargs: True,
            touch_active_feature_for_iteration=lambda *_args, **_kwargs: None,
            run_implement_step=lambda *_args, **_kwargs: _passing_implement_result(),
            refresh_feature_after_implement=_refresh_feature_after_implement,
            should_archive_selected_feature=lambda *_args, **_kwargs: True,
            archive_completed_feature=archive_completed_feature,
            run_gate_phase=(
                lambda *_args, **_kwargs: GatePhaseOutcome(
                    result="passed",
                    failed_gate=None,
                    gate_status="passed",
                    gate_output="",
                    feedback=None,
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
                    feedback=None,
                )
            ),
            run_reviewer_phase=_run_reviewer_phase,
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
                    feedback=None,
                )
            ),
            completion_phase_dependencies=CompletionPhaseDependencies(
                commit_feature_completion=lambda *_args, **_kwargs: (True, None, ""),
                restore_archived_feature=lambda *_args, **_kwargs: (True, None),
            ),
        ),
    )

    assert report.result == "failed"
    assert report.archived_selection_path is None
    assert report.telemetry_inputs.progress_kind == "phase"
    assert report.telemetry_inputs.progress_id == "P1"


def test_iteration_pipeline_clears_archived_selection_after_completion_rollback(
    tmp_path: Path,
) -> None:
    iteration_inputs = FeatureIterationInputs(
        project_root=tmp_path,
        feature_path=tmp_path / "docs" / "spec" / "features" / "FEAT-999.yaml",
        attempt=1,
        feedback=None,
        verbose_output=False,
    )

    report = run_feature_iteration_pipeline(
        iteration_inputs,
        IterationPipelineDependencies(
            evaluate_initial_feature_load=(
                lambda _path: InitialFeatureLoadOutcome(
                    feature={"id": "FEAT-999", "status": "in_progress"},
                    result="passed",
                    failed_gate=None,
                    feedback=None,
                )
            ),
            ready_for_active_iteration=lambda *_args, **_kwargs: True,
            touch_active_feature_for_iteration=lambda *_args, **_kwargs: None,
            run_implement_step=lambda *_args, **_kwargs: _passing_implement_result(),
            refresh_feature_after_implement=(
                lambda _project_root, _feature_path: PostImplementFeatureOutcome(
                    feature={"id": "FEAT-999", "status": "done"},
                    archived_in_iteration=False,
                    archived_path=None,
                    result="passed",
                    failed_gate=None,
                    feedback=None,
                )
            ),
            should_archive_selected_feature=lambda *_args, **_kwargs: True,
            archive_completed_feature=(
                lambda *_args, **_kwargs: (
                    True,
                    tmp_path / "docs" / "spec" / "features_done" / "FEAT-999.yaml",
                    "",
                )
            ),
            run_gate_phase=(
                lambda *_args, **_kwargs: GatePhaseOutcome(
                    result="passed",
                    failed_gate=None,
                    gate_status="passed",
                    gate_output="",
                    feedback=None,
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
                    feedback=None,
                )
            ),
            run_reviewer_phase=(
                lambda *_args, **_kwargs: ReviewerPhaseOutcome(
                    result="passed",
                    failed_gate=None,
                    reviewer_status="not_run",
                    reviewer_decision=None,
                    failed_reviewer_id=None,
                    reviewer_output="",
                    feedback=None,
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
                    result="failed",
                    failed_gate="git_commit",
                    next_action="retry_same_feature",
                    feedback="commit failed",
                    archived_rolled_back=True,
                )
            ),
            completion_phase_dependencies=CompletionPhaseDependencies(
                commit_feature_completion=lambda *_args, **_kwargs: (True, None, ""),
                restore_archived_feature=lambda *_args, **_kwargs: (True, None),
            ),
        ),
    )

    assert report.result == "failed"
    assert report.completed is False
    assert report.archived_selection_path is None


def test_iteration_pipeline_archives_before_running_done_transition_verification(
    tmp_path: Path,
) -> None:
    iteration_inputs = FeatureIterationInputs(
        project_root=tmp_path,
        feature_path=tmp_path / "docs" / "spec" / "features" / "FEAT-078.yaml",
        attempt=1,
        feedback=None,
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
                feedback="done feature still active",
            )
        return VerificationPhaseOutcome(
            result="passed",
            verification_status="passed",
            verification_failed_command=None,
            verification_output="",
            feedback=None,
        )

    report = run_feature_iteration_pipeline(
        iteration_inputs,
        IterationPipelineDependencies(
            evaluate_initial_feature_load=(
                lambda _path: InitialFeatureLoadOutcome(
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
                    result="passed",
                    failed_gate=None,
                    feedback=None,
                )
            ),
            ready_for_active_iteration=lambda *_args, **_kwargs: True,
            touch_active_feature_for_iteration=lambda *_args, **_kwargs: None,
            run_implement_step=lambda *_args, **_kwargs: _passing_implement_result(),
            refresh_feature_after_implement=(
                lambda _project_root, _feature_path: PostImplementFeatureOutcome(
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
                    archived_in_iteration=False,
                    archived_path=None,
                    result="passed",
                    failed_gate=None,
                    feedback=None,
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
                    feedback=None,
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
                    feedback=None,
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
                    feedback=None,
                )
            ),
            completion_phase_dependencies=CompletionPhaseDependencies(
                commit_feature_completion=lambda *_args, **_kwargs: (True, None, ""),
                restore_archived_feature=lambda *_args, **_kwargs: (True, None),
            ),
        ),
    )

    assert report.result == "passed"


@pytest.mark.parametrize(
    ("verification_status", "failed_command", "pre_subtask", "post_subtask"),
    [
        pytest.param(
            "failed:uv run pytest -q tests/loop",
            "uv run pytest -q tests/loop",
            {
                "id": "ST-001",
                "status": "in_progress",
                "verification": ["uv run pytest -q tests/loop"],
            },
            {
                "id": "ST-001",
                "status": "done",
                "verification": ["uv run pytest -q tests/loop"],
            },
            id="with-failed-command",
        ),
        pytest.param(
            "failed:unknown",
            None,
            {"id": "ST-001", "status": "in_progress"},
            {"id": "ST-001", "status": "done"},
            id="without-failed-command",
        ),
    ],
)
def test_iteration_pipeline_runs_gate_phase_after_verification_failure_cases(
    tmp_path: Path,
    verification_status: str,
    failed_command: str | None,
    pre_subtask: dict[str, Any],
    post_subtask: dict[str, Any],
) -> None:
    iteration_inputs = FeatureIterationInputs(
        project_root=tmp_path,
        feature_path=tmp_path / "docs" / "spec" / "features" / "FEAT-137.yaml",
        attempt=1,
        feedback=None,
        verbose_output=False,
    )

    gate_phase_called = False

    def _run_gate_phase(*_args: Any, **_kwargs: Any) -> GatePhaseOutcome:
        nonlocal gate_phase_called
        gate_phase_called = True
        return GatePhaseOutcome(
            result="passed",
            failed_gate=None,
            gate_status="passed",
            gate_output="",
            feedback=None,
        )

    report = run_feature_iteration_pipeline(
        iteration_inputs,
        IterationPipelineDependencies(
            evaluate_initial_feature_load=(
                lambda _path: InitialFeatureLoadOutcome(
                    feature={
                        "id": "FEAT-137",
                        "status": "in_progress",
                        "subtasks": [pre_subtask],
                    },
                    result="passed",
                    failed_gate=None,
                    feedback=None,
                )
            ),
            ready_for_active_iteration=lambda *_args, **_kwargs: True,
            touch_active_feature_for_iteration=lambda *_args, **_kwargs: None,
            run_implement_step=lambda *_args, **_kwargs: _passing_implement_result(),
            refresh_feature_after_implement=(
                lambda _project_root, _feature_path: PostImplementFeatureOutcome(
                    feature={
                        "id": "FEAT-137",
                        "status": "in_progress",
                        "subtasks": [post_subtask],
                    },
                    archived_in_iteration=False,
                    archived_path=None,
                    result="passed",
                    failed_gate=None,
                    feedback=None,
                )
            ),
            should_archive_selected_feature=lambda *_args, **_kwargs: False,
            archive_completed_feature=lambda *_args, **_kwargs: (True, None, None),
            run_gate_phase=_run_gate_phase,
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
                    result="failed",
                    verification_status=verification_status,
                    verification_failed_command=failed_command,
                    verification_output="verification failed",
                    feedback="verification failed",
                )
            ),
            run_reviewer_phase=(
                lambda *_args, **_kwargs: ReviewerPhaseOutcome(
                    result="passed",
                    failed_gate=None,
                    reviewer_status="passed",
                    reviewer_decision="approve",
                    failed_reviewer_id=None,
                    reviewer_output="",
                    feedback=None,
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
                    result="failed",
                    failed_gate=None,
                    next_action="retry_same_feature",
                    feedback="verification failed",
                )
            ),
            completion_phase_dependencies=CompletionPhaseDependencies(
                commit_feature_completion=lambda *_args, **_kwargs: (True, None, ""),
                restore_archived_feature=lambda *_args, **_kwargs: (True, None),
            ),
        ),
    )

    assert gate_phase_called is True
    assert report.result == "failed"
    assert report.verification_status == verification_status


def test_iteration_pipeline_collects_changed_paths_once_per_iteration(
    tmp_path: Path,
) -> None:
    iteration_inputs = FeatureIterationInputs(
        project_root=tmp_path,
        feature_path=tmp_path / "docs" / "spec" / "features" / "FEAT-999.yaml",
        attempt=1,
        feedback=None,
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
            feedback=None,
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
            feedback=None,
        )

    report = run_feature_iteration_pipeline(
        iteration_inputs,
        IterationPipelineDependencies(
            evaluate_initial_feature_load=(
                lambda _path: InitialFeatureLoadOutcome(
                    feature={
                        "id": "FEAT-999",
                        "status": "in_progress",
                        "subtasks": [{"id": "ST-001", "status": "in_progress"}],
                    },
                    result="passed",
                    failed_gate=None,
                    feedback=None,
                )
            ),
            ready_for_active_iteration=lambda *_args, **_kwargs: True,
            touch_active_feature_for_iteration=lambda *_args, **_kwargs: None,
            run_implement_step=lambda *_args, **_kwargs: _passing_implement_result(),
            refresh_feature_after_implement=(
                lambda _project_root, _feature_path: PostImplementFeatureOutcome(
                    feature={
                        "id": "FEAT-999",
                        "status": "in_progress",
                        "subtasks": [{"id": "ST-001", "status": "in_progress"}],
                    },
                    archived_in_iteration=False,
                    archived_path=None,
                    result="passed",
                    failed_gate=None,
                    feedback=None,
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
                    feedback=None,
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
                    feedback=None,
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
        feedback=None,
        verbose_output=False,
    )

    report = run_feature_iteration_pipeline(
        iteration_inputs,
        IterationPipelineDependencies(
            evaluate_initial_feature_load=(
                lambda _path: InitialFeatureLoadOutcome(
                    feature={"id": "FEAT-065", "status": "in_progress"},
                    result="passed",
                    failed_gate=None,
                    feedback=None,
                )
            ),
            ready_for_active_iteration=lambda *_args, **_kwargs: True,
            touch_active_feature_for_iteration=lambda *_args, **_kwargs: None,
            run_implement_step=lambda *_args, **_kwargs: _passing_implement_result(),
            refresh_feature_after_implement=(
                lambda _project_root, _feature_path: PostImplementFeatureOutcome(
                    feature={"id": "FEAT-065", "status": "in_progress"},
                    archived_in_iteration=False,
                    archived_path=None,
                    result="passed",
                    failed_gate=None,
                    feedback=None,
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
                    feedback=None,
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
                    feedback=None,
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
                    feedback=None,
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
                    feedback=None,
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
    result = _timed_phase(
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


def test_run_loop_controller_rejects_invalid_max_iterations(
    tmp_path: Path,
    capsys: Any,
) -> None:
    code = run_loop_controller(
        LoopRun(
            config=RunConfig(
                project_root=tmp_path,
                feature_paths=(
                    tmp_path / "docs" / "spec" / "features" / "FEAT-079-looprun.yaml",
                ),
                dry_run=False,
                max_iterations=0,
            ),
            services=RunServices(
                resolve_run_targets=lambda *_args, **_kwargs: [],
                emit_run_all_snapshot_feedback=lambda *_args, **_kwargs: None,
                handle_dry_run=lambda *_args, **_kwargs: None,
                enforce_worktree_precondition=lambda *_args, **_kwargs: None,
                run_permission_precheck=lambda **_kwargs: True,
                run_selected_feature_iterations=lambda *_args, **_kwargs: 0,
            ),
        )
    )

    assert code == 1
    assert "max_iterations must be >= 1" in capsys.readouterr().out
