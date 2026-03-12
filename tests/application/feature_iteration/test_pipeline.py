from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, Callable

import pytest
from pydantic import BaseModel, ConfigDict

from engineeringagent.application.feature_iteration import (
    CompletionCommitOutcome,
    FeatureIterationInputs,
    GatePhaseOutcome,
    ImplementStepResult,
    IterationReport,
    IterationTelemetryInputs,
    ReviewerPhaseOutcome,
    VerificationPhaseOutcome,
)
from engineeringagent.domain.audit import fallback_implement_progress_envelope
from engineeringagent.domain.quality import ChangedPathsResult
from engineeringagent.domain.specification import (
    InitialFeatureLoadOutcome,
    PostImplementFeatureOutcome,
)
from engineeringagent.application.feature_iteration import IterationPipelineDependencies
from engineeringagent.application.feature_iteration.pipeline import (
    _timed_phase,
    run_feature_iteration_pipeline,
)
from tests.loop.feature_iteration_support import (
    base_feature,
    make_bundled_project_root,
)


class _FakeClock:
    def __init__(self, *timestamps: float) -> None:
        self._timestamps = list(timestamps) or [0.0]
        self._index = 0

    def now_epoch_seconds(self) -> float:
        value = self._timestamps[min(self._index, len(self._timestamps) - 1)]
        self._index += 1
        return value


class _GatePhaseDependencies(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    restore_archived_feature: Callable[[Path, Path], tuple[bool, str | None]]
    collect_changed_paths: Callable[[Path], ChangedPathsResult]


class _ReviewerPhaseDependencies(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    collect_changed_paths: Callable[..., Any]
    restore_archived_feature: Callable[[Path, Path], tuple[bool, str | None]]
    run_agent_fn: Callable[..., Any] | None = None


class _CompletionPhaseDependencies(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    commit_feature_completion: Callable[
        [Path, dict[str, Any]], tuple[bool, str | None, str]
    ]
    restore_archived_feature: Callable[[Path, Path], tuple[bool, str | None]]


def _passing_implement_result(output: str = "") -> ImplementStepResult:
    return (True, None, output, fallback_implement_progress_envelope(), True)


def archive_completed_feature(
    _project_root: Path,
    feature_path: Path,
) -> tuple[bool, Path | None, str]:
    """Archive a bundled feature package without reaching into adapters."""
    if not feature_path.exists():
        return (False, None, f"completed feature spec not found: {feature_path}")

    archive_path = _remap_feature_path(feature_path, source="features", dest="features_done")
    if archive_path is None:
        return (False, None, f"unsupported feature archive path: {feature_path}")
    if archive_path.parent.exists():
        return (False, None, f"archive destination already exists: {archive_path}")

    archive_path.parent.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(feature_path.parent), str(archive_path.parent))
    return (True, archive_path, "")


def restore_archived_feature(
    archived_path: Path,
    original_feature_path: Path,
) -> tuple[bool, str | None]:
    """Restore a bundled archived feature package for rollback tests."""
    if not archived_path.exists():
        return (True, "")

    restored_path = _remap_feature_path(
        archived_path,
        source="features_done",
        dest="features",
    )
    if restored_path is None:
        return (False, f"unsupported feature restore path: {archived_path}")
    if restored_path.parent.exists():
        return (
            False,
            "cannot restore archived feature path because source already exists",
        )

    restored_path.parent.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(archived_path.parent), str(restored_path.parent))
    return (True, "")


def _remap_feature_path(
    feature_path: Path,
    *,
    source: str,
    dest: str,
) -> Path | None:
    parts = list(feature_path.parts)
    if source not in parts:
        return None
    source_index = parts.index(source)
    remapped_parts = parts[:]
    remapped_parts[source_index] = dest
    return Path(*remapped_parts)


def test_iteration_report_model_captures_pipeline_observer_contract(
    tmp_path: Path,
) -> None:
    """Capture the observer-facing iteration report contract."""
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
    """Forward reviewer approval feedback into continuation guidance."""
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
            clock=_FakeClock(),
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
            gate_phase_dependencies=_GatePhaseDependencies(
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
            reviewer_phase_dependencies=_ReviewerPhaseDependencies(
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
            completion_phase_dependencies=_CompletionPhaseDependencies(
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
    """Prefer bundled plan phase metadata when reporting progress."""
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
            clock=_FakeClock(),
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
            gate_phase_dependencies=_GatePhaseDependencies(
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
            reviewer_phase_dependencies=_ReviewerPhaseDependencies(
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
            completion_phase_dependencies=_CompletionPhaseDependencies(
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
    """Keep phase progress reporting when the bundled plan is invalid."""
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
            clock=_FakeClock(),
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
            gate_phase_dependencies=_GatePhaseDependencies(
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
            reviewer_phase_dependencies=_ReviewerPhaseDependencies(
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
            completion_phase_dependencies=_CompletionPhaseDependencies(
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
    """Report direct bundled feature progress when no plan exists."""
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
            clock=_FakeClock(),
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
            gate_phase_dependencies=_GatePhaseDependencies(
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
            reviewer_phase_dependencies=_ReviewerPhaseDependencies(
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
            completion_phase_dependencies=_CompletionPhaseDependencies(
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
    """Fall back to feature progress when there is no active plan unit."""
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
            clock=_FakeClock(),
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
            gate_phase_dependencies=_GatePhaseDependencies(
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
            reviewer_phase_dependencies=_ReviewerPhaseDependencies(
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
            completion_phase_dependencies=_CompletionPhaseDependencies(
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
    """Recover phase metadata from invalid-but-parseable plan contracts."""
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
            clock=_FakeClock(),
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
            gate_phase_dependencies=_GatePhaseDependencies(
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
            reviewer_phase_dependencies=_ReviewerPhaseDependencies(
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
            completion_phase_dependencies=_CompletionPhaseDependencies(
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
    """Preserve phase metadata when the feature is archived in-iteration."""
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
        _deps: Any,
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
            clock=_FakeClock(),
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
            gate_phase_dependencies=_GatePhaseDependencies(
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
            reviewer_phase_dependencies=_ReviewerPhaseDependencies(
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
            completion_phase_dependencies=_CompletionPhaseDependencies(
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
        / "specifications"
        / "features_done"
        / "FEAT-900-bundled-smoke-test"
        / "spec.yaml"
    ).exists()


def test_iteration_pipeline_clears_archived_selection_after_reviewer_rollback(
    tmp_path: Path,
) -> None:
    """Clear archived selection state after a reviewer rollback."""
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
        _deps: Any,
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
            clock=_FakeClock(),
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
            gate_phase_dependencies=_GatePhaseDependencies(
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
            reviewer_phase_dependencies=_ReviewerPhaseDependencies(
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
            completion_phase_dependencies=_CompletionPhaseDependencies(
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
    """Clear archived selection state after a completion rollback."""
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
            clock=_FakeClock(),
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
            gate_phase_dependencies=_GatePhaseDependencies(
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
            reviewer_phase_dependencies=_ReviewerPhaseDependencies(
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
            completion_phase_dependencies=_CompletionPhaseDependencies(
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
    """Run done-transition verification against the archived feature path."""
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
            clock=_FakeClock(),
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
            gate_phase_dependencies=_GatePhaseDependencies(
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
            reviewer_phase_dependencies=_ReviewerPhaseDependencies(
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
            completion_phase_dependencies=_CompletionPhaseDependencies(
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
    """Keep gate execution active after verification failures for feedback."""
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
            clock=_FakeClock(),
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
            gate_phase_dependencies=_GatePhaseDependencies(
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
            reviewer_phase_dependencies=_ReviewerPhaseDependencies(
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
            completion_phase_dependencies=_CompletionPhaseDependencies(
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
    """Collect changed paths once across gate and reviewer phases."""
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
        deps: Any,
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
        deps: Any,
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
            clock=_FakeClock(),
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
            gate_phase_dependencies=_GatePhaseDependencies(
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
            reviewer_phase_dependencies=_ReviewerPhaseDependencies(
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
            completion_phase_dependencies=_CompletionPhaseDependencies(
                commit_feature_completion=lambda *_args, **_kwargs: (True, None, ""),
                restore_archived_feature=lambda *_args, **_kwargs: (True, None),
            ),
        ),
    )

    assert report.result == "passed"
    assert calls["count"] == 1


def test_iteration_pipeline_records_phase_timings(
    tmp_path: Path,
) -> None:
    """Record timing metadata for each pipeline phase."""
    clock = _FakeClock(
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
            clock=clock,
            evaluate_initial_feature_load=(
                lambda _path: InitialFeatureLoadOutcome(
                    feature={"id": "FEAT-065", "status": "in_progress"},
                    result="passed",
                    failed_gate=None,
                    feedback=None,
                )
            ),
            describe_action=lambda _project_root, action, structured: (
                "backend implement label"
                if (action, structured) == ("implement", False)
                else "unexpected"
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
            gate_phase_dependencies=_GatePhaseDependencies(
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
            reviewer_phase_dependencies=_ReviewerPhaseDependencies(
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
            completion_phase_dependencies=_CompletionPhaseDependencies(
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
) -> None:
    """Clamp phase timing when the clock moves backwards."""
    phase_timings: list[Any] = []
    result = _timed_phase(
        _FakeClock(10.0, 9.0),
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
