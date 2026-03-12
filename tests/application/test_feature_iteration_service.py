from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, Sequence, cast

from engineeringagent.application import FeatureIterationRequest, FeatureIterationService
from engineeringagent.application.feature_iteration import (
    FeatureIterationInputs,
    FeatureIterationRuntimeDependencies,
    IterationOutcome,
    IterationPipelineDependencies,
    IterationReport,
    IterationTelemetryInputs,
    PhaseTiming,
)
from engineeringagent.domain.audit import fallback_implement_progress_envelope, ProgressEvent
from engineeringagent.domain.specification import (
    InitialFeatureLoadOutcome,
    PostImplementFeatureOutcome,
)
from engineeringagent.ports import CommitRequest, CommitResult, DiffSummary, WorktreeStatus


class _FakeClock:
    def now_epoch_seconds(self) -> float:
        return 0.0


class _FakeGatePhaseDependencies:
    def __init__(self, observed: dict[str, object], **kwargs: object) -> None:
        observed["gate_dependencies"] = kwargs


class _FakeReviewerPhaseDependencies:
    def __init__(self, observed: dict[str, object], **kwargs: object) -> None:
        observed["reviewer_dependencies"] = kwargs


class _FakeCompletionPhaseDependencies:
    def __init__(self, observed: dict[str, object], **kwargs: object) -> None:
        observed["completion_dependencies"] = kwargs


class _FakeVersionControlGateway:
    def __init__(self, observed: dict[str, object], commit_result: CommitResult) -> None:
        self._observed = observed
        self._commit_result = commit_result

    def diff_against_base(
        self,
        workspace_path: Path,
        *,
        base_ref: str | None = None,
        head_ref: str | None = None,
    ) -> DiffSummary:
        raise AssertionError("unexpected diff_against_base call")

    def head_commit(self, workspace_path: Path) -> str | None:
        raise AssertionError("unexpected head_commit call")

    def worktree_status(self, workspace_path: Path) -> WorktreeStatus:
        raise AssertionError("unexpected worktree_status call")

    def commit(self, request: CommitRequest) -> CommitResult:
        commit_requests = self._observed.setdefault("commit_requests", [])
        assert isinstance(commit_requests, list)
        commit_requests.append(request)
        return self._commit_result


class _FakeProgressJournal:
    def __init__(self, observed: dict[str, object]) -> None:
        self._observed = observed

    def append(self, *, project_root: Path, event: ProgressEvent) -> None:
        raise AssertionError("unexpected append call")

    def append_feature_log(
        self,
        *,
        project_root: Path,
        feature_id: str,
        lines: Sequence[str],
    ) -> None:
        raise AssertionError("unexpected append_feature_log call")

    def write_iteration_report(
        self,
        *,
        project_root: Path,
        feature_id: str,
        payload: dict[str, Any],
    ) -> None:
        iteration_reports = self._observed.setdefault("iteration_reports", [])
        assert isinstance(iteration_reports, list)
        iteration_reports.append(
            {
                "project_root": project_root,
                "feature_id": feature_id,
                "payload": payload,
            }
        )

    def write_handoff(
        self,
        *,
        project_root: Path,
        feature_id: str,
        lines: Sequence[str],
    ) -> None:
        raise AssertionError("unexpected write_handoff call")

    def latest_handoff_path(
        self, *, project_root: Path, feature_id: str
    ) -> Path | None:
        raise AssertionError("unexpected latest_handoff_path call")


def _build_request(**overrides: object) -> FeatureIterationRequest:
    fields: dict[str, object] = {
        "project_root": Path("/tmp/project"),
        "feature_path": Path("docs/specifications/features/FEAT-001/specification.yaml"),
        "run_all": False,
        "attempt": 3,
        "feedback": "fix the failing check",
        "verbose_output": True,
    }
    fields.update(overrides)
    return FeatureIterationRequest.model_validate(fields)


def _build_service(
    observed: dict[str, object],
    *,
    commit_result: CommitResult,
    publish_outcome: object,
) -> tuple[FeatureIterationService, _FakeVersionControlGateway]:
    def _fake_run_feature_iteration_pipeline(inputs: object, dependencies: object) -> str:
        observed["inputs"] = inputs
        observed["dependencies"] = dependencies
        return "iteration-report"

    def _fake_build_iteration_pipeline_dependencies(
        runtime_dependencies: object,
        version_control_gateway: object,
    ) -> IterationPipelineDependencies:
        observed["pipeline_builder_runtime_dependencies"] = runtime_dependencies
        observed["pipeline_builder_version_control_gateway"] = version_control_gateway
        return IterationPipelineDependencies(
            clock=_FakeClock(),
            evaluate_initial_feature_load=evaluate_initial_feature_load,
            describe_action=describe_action,
            ready_for_active_iteration=ready_for_active_iteration,
            touch_active_feature_for_iteration=touch_active_feature_for_iteration,
            run_implement_step=run_implement_step,
            refresh_feature_after_implement=refresh_feature_after_implement,
            should_archive_selected_feature=should_archive_selected_feature,
            archive_completed_feature=archive_completed_feature,
            run_gate_phase=run_gate_phase,
            gate_phase_dependencies=_FakeGatePhaseDependencies(observed),
            run_verification_phase=run_verification_phase,
            run_reviewer_phase=run_reviewer_phase,
            reviewer_phase_dependencies=_FakeReviewerPhaseDependencies(observed),
            run_completion_commit_phase=run_completion_commit_phase,
            completion_phase_dependencies=_FakeCompletionPhaseDependencies(observed),
        )

    class _FakeIterationReportPublisher:
        def __call__(self, report: IterationReport) -> IterationOutcome:
            observed["report"] = report
            return cast(IterationOutcome, publish_outcome)

    describe_action = lambda project_root, action, structured: (  # noqa: E731
        f"{project_root}:{action}:{structured}"
    )
    run_implement_step = lambda *args, **kwargs: (  # noqa: E731
        True,
        None,
        "",
        fallback_implement_progress_envelope(),
        False,
    )
    collect_changed_paths = lambda _project_root: None  # noqa: E731
    evaluate_initial_feature_load = lambda _feature_path: InitialFeatureLoadOutcome(  # noqa: E731
        feature=None,
        result="failed",
        failed_gate="load",
        feedback=None,
    )
    ready_for_active_iteration = lambda _result, _feature: True  # noqa: E731
    touch_active_feature_for_iteration = lambda _feature, _path: None  # noqa: E731
    refresh_feature_after_implement = lambda _project_root, _feature_path: PostImplementFeatureOutcome(  # noqa: E731
        feature=None,
        archived_in_iteration=False,
        archived_path=None,
        result="failed",
        failed_gate="refresh",
        feedback=None,
    )
    should_archive_selected_feature = lambda _result, _feature: False  # noqa: E731
    archive_completed_feature = lambda _project_root, _feature_path: (False, None, None)  # noqa: E731
    restore_archived_feature = lambda _archived_path, _feature_path: (True, None)  # noqa: E731
    run_gate_phase = cast(Any, lambda *args, **kwargs: None)  # noqa: E731
    run_verification_phase = cast(Any, lambda *args, **kwargs: None)  # noqa: E731
    run_reviewer_phase = cast(Any, lambda *args, **kwargs: None)  # noqa: E731
    run_completion_commit_phase = cast(Any, lambda *args, **kwargs: None)  # noqa: E731
    runtime_dependencies = FeatureIterationRuntimeDependencies(
        clock=_FakeClock(),
        evaluate_initial_feature_load=evaluate_initial_feature_load,
        describe_action=describe_action,
        ready_for_active_iteration=ready_for_active_iteration,
        touch_active_feature_for_iteration=touch_active_feature_for_iteration,
        run_implement_step=run_implement_step,
        refresh_feature_after_implement=refresh_feature_after_implement,
        should_archive_selected_feature=should_archive_selected_feature,
        archive_completed_feature=archive_completed_feature,
        collect_changed_paths=collect_changed_paths,
        restore_archived_feature=restore_archived_feature,
        run_feature_iteration_pipeline=_fake_run_feature_iteration_pipeline,
        run_gate_phase=run_gate_phase,
        build_gate_phase_dependencies=lambda **kwargs: _FakeGatePhaseDependencies(
            observed, **kwargs
        ),
        run_verification_phase=run_verification_phase,
        run_reviewer_phase=run_reviewer_phase,
        build_reviewer_phase_dependencies=(
            lambda **kwargs: _FakeReviewerPhaseDependencies(observed, **kwargs)
        ),
        run_completion_commit_phase=run_completion_commit_phase,
        build_completion_phase_dependencies=(
            lambda **kwargs: _FakeCompletionPhaseDependencies(observed, **kwargs)
        ),
        build_iteration_pipeline_dependencies=_fake_build_iteration_pipeline_dependencies,
    )
    version_control_gateway = _FakeVersionControlGateway(observed, commit_result)
    service = FeatureIterationService(
        version_control_gateway=version_control_gateway,
        iteration_report_publisher=_FakeIterationReportPublisher(),
        runtime_dependencies=runtime_dependencies,
    )
    return service, version_control_gateway


def test_feature_iteration_service_executes_runtime_pipeline() -> None:
    """The application service should own runtime pipeline composition."""
    observed: dict[str, object] = {}
    service, _ = _build_service(
        observed,
        commit_result=CommitResult(
            stdout="commit stdout\n",
            stderr="commit stderr\n",
            commit_created=False,
            commit_sha=None,
            failure_stage="git_commit",
        ),
        publish_outcome=SimpleNamespace(
            completed=False,
            result="failed",
            failed_gate="tests",
            next_action="retry_same_feature",
            feedback="rerun focused tests",
            log_path=".engineeringagent/progress/FEAT-001/iteration-report.json",
            verification_status="failed:tests",
            verification_failed_command="uv run pytest tests/application",
            reviewer_status="not_run",
            reviewer_decision=None,
            failed_reviewer_id=None,
        ),
    )

    result = service.run(_build_request())

    assert result.result == "failed"
    assert observed["inputs"] == FeatureIterationInputs(
        project_root=Path("/tmp/project"),
        feature_path=Path("docs/specifications/features/FEAT-001/specification.yaml"),
        run_all=False,
        attempt=3,
        feedback="fix the failing check",
        verbose_output=True,
    )
    dependencies = cast(IterationPipelineDependencies, observed["dependencies"])
    runtime_dependencies = service._runtime_dependencies
    assert observed["pipeline_builder_runtime_dependencies"] is runtime_dependencies
    assert (
        observed["pipeline_builder_version_control_gateway"]
        is service._version_control_gateway
    )
    assert dependencies.describe_action is runtime_dependencies.describe_action
    assert dependencies.run_implement_step is runtime_dependencies.run_implement_step
    assert observed["report"] == "iteration-report"


def test_iteration_outcome_from_report_copies_report_status_fields() -> None:
    """Feature-iteration contracts should expose a stable summary view."""

    telemetry_inputs = IterationTelemetryInputs(
        iteration_inputs=FeatureIterationInputs(
            project_root=Path("/tmp/project"),
            feature_path=Path(
                "docs/specifications/features/FEAT-001/specification.yaml"
            ),
            run_all=False,
            attempt=1,
            feedback="ship it",
            verbose_output=True,
        ),
        started=1.0,
        phase_timings=[
            PhaseTiming(
                phase="implement",
                started_at="2026-03-12T00:00:00Z",
                ended_at="2026-03-12T00:00:01Z",
                duration_sec=1,
            )
        ],
        command_timings=[],
        feature_id="FEAT-001",
        result="completed",
        failed_gate=None,
        next_action="archive_feature",
        implement_status="ok",
        gate_status="ok",
        verification_status="passed",
        verification_failed_command=None,
        implement_output="implemented",
        gate_output="gates ok",
        verification_output="verification ok",
        feedback="ship it",
    )
    report = IterationReport(
        completed=True,
        result="completed",
        failed_gate=None,
        next_action="archive_feature",
        feedback="ship it",
        feature_id="FEAT-001",
        attempt=1,
        selected_feature_path="docs/specifications/features/FEAT-001/specification.yaml",
        implement_step="implement",
        verification_status="passed",
        verification_failed_command=None,
        reviewer_status="approved",
        reviewer_decision="approve",
        failed_reviewer_id=None,
        telemetry_inputs=telemetry_inputs,
        log_path=".engineeringagent/progress/FEAT-001/iteration-report.json",
    )

    outcome = IterationOutcome.from_report(report)

    assert outcome == IterationOutcome(
        completed=True,
        result="completed",
        failed_gate=None,
        next_action="archive_feature",
        feedback="ship it",
        log_path=".engineeringagent/progress/FEAT-001/iteration-report.json",
        verification_status="passed",
        verification_failed_command=None,
        reviewer_status="approved",
        reviewer_decision="approve",
        failed_reviewer_id=None,
    )
