from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, Sequence, cast

from engineeringagent.application.feature_iteration import (
    FeatureIterationInputs,
    FeatureIterationRuntimeDependencies,
    IterationOutcome,
    IterationReport,
    IterationTelemetryInputs,
    IterationPipelineDependencies,
    PhaseTiming,
    commit_feature_completion,
    persist_iteration_report,
)
from engineeringagent.application import (
    FeatureIterationRequest,
    FeatureIterationService,
)
from engineeringagent.bootstrap.iteration_reporting import DefaultObserverDependencies
from engineeringagent.domain.audit import ProgressEvent
from engineeringagent.ports import CommitRequest, CommitResult, DiffSummary, WorktreeStatus


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

    def _fake_build_iteration_report_observers(dependencies: object) -> object:
        observed["default_observer_dependencies"] = dependencies
        return ("observer",)

    def _fake_publish_iteration_report(report: str, observers: object) -> object:
        observed["report"] = report
        observed["observers"] = observers
        return publish_outcome

    def _fake_write_iteration_telemetry(
        telemetry_inputs: object,
        **kwargs: object,
    ) -> str:
        observed["telemetry_call"] = {
            "telemetry_inputs": telemetry_inputs,
            **kwargs,
        }
        return "progress/run-feature-FEAT-001.txt"

    describe_action = lambda project_root, action, structured: (  # noqa: E731
        f"{project_root}:{action}:{structured}"
    )
    run_implement_step = lambda *args, **kwargs: None  # noqa: E731
    git_head_short = lambda _project_root: "abc1234"  # noqa: E731
    print_summary = lambda _summary: None  # noqa: E731
    collect_changed_paths = lambda _project_root: None  # noqa: E731
    evaluate_initial_feature_load = lambda _feature_path: None  # noqa: E731
    ready_for_active_iteration = lambda _result, _feature: True  # noqa: E731
    touch_active_feature_for_iteration = lambda _feature, _path: None  # noqa: E731
    refresh_feature_after_implement = lambda _project_root, _feature_path: None  # noqa: E731
    should_archive_selected_feature = lambda _result, _feature: False  # noqa: E731
    archive_completed_feature = lambda _project_root, _feature_path: (False, None, None)  # noqa: E731
    restore_archived_feature = lambda _archived_path, _feature_path: (True, None)  # noqa: E731
    run_gate_phase = lambda *args, **kwargs: None  # noqa: E731
    run_verification_phase = lambda *args, **kwargs: None  # noqa: E731
    run_reviewer_phase = lambda *args, **kwargs: None  # noqa: E731
    run_completion_commit_phase = lambda *args, **kwargs: None  # noqa: E731
    runtime_dependencies = FeatureIterationRuntimeDependencies(
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
        git_head_short=git_head_short,
        print_summary=print_summary,
        observer_dependencies_type=DefaultObserverDependencies,
        write_iteration_telemetry=_fake_write_iteration_telemetry,
        build_iteration_report_observers=_fake_build_iteration_report_observers,
        publish_iteration_report=_fake_publish_iteration_report,
    )

    version_control_gateway = _FakeVersionControlGateway(observed, commit_result)
    service = FeatureIterationService(
        version_control_gateway=version_control_gateway,
        progress_journal=_FakeProgressJournal(observed),
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
    completion_dependencies = observed["completion_dependencies"]
    assert isinstance(completion_dependencies, dict)
    commit_outcome = completion_dependencies["commit_feature_completion"](
        Path("/tmp/project"),
        {"expected_commit_subject": "feat: complete FEAT-001"},
    )
    assert commit_outcome == (False, "git_commit", "commit stdout\ncommit stderr\n")
    assert observed["commit_requests"] == [
        CommitRequest(
            workspace_path=Path("/tmp/project"),
            message="feat: complete FEAT-001",
            stage_all=True,
            allow_empty=False,
        )
    ]
    observer_dependencies = cast(
        DefaultObserverDependencies,
        observed["default_observer_dependencies"],
    )
    dependencies = cast(IterationPipelineDependencies, observed["dependencies"])
    runtime_dependencies = service._runtime_dependencies
    assert dependencies.describe_action is runtime_dependencies.describe_action
    assert dependencies.run_implement_step is runtime_dependencies.run_implement_step
    assert (
        observer_dependencies.git_head_resolver
        is runtime_dependencies.git_head_short
    )
    assert observer_dependencies.print_summary is runtime_dependencies.print_summary
    observer_dependencies.write_iteration_telemetry(cast(Any, "telemetry-inputs"))
    observer_dependencies.persist_iteration_report(
        cast(
            Any,
            SimpleNamespace(
                telemetry_inputs=SimpleNamespace(
                    iteration_inputs=SimpleNamespace(project_root=Path("/tmp/project"))
                ),
                feature_id="FEAT-001",
                model_dump=lambda mode="json": {"result": "failed", "mode": mode},
            ),
        )
    )
    assert observed["iteration_reports"] == [
        {
            "project_root": Path("/tmp/project"),
            "feature_id": "FEAT-001",
            "payload": {"result": "failed", "mode": "json"},
        }
    ]
    assert observed["telemetry_call"] == {
        "telemetry_inputs": "telemetry-inputs",
        "git_head_resolver": runtime_dependencies.git_head_short,
    }


def test_feature_iteration_service_reports_commit_success() -> None:
    """Successful completion commits should preserve the canonical tuple shape."""
    observed: dict[str, object] = {}
    service, _ = _build_service(
        observed,
        commit_result=CommitResult(
            stdout="ok\n",
            stderr="",
            commit_created=True,
            commit_sha="abc1234",
            failure_stage=None,
        ),
        publish_outcome=SimpleNamespace(
            completed=True,
            result="passed",
            failed_gate=None,
            next_action="select_next_feature",
            feedback=None,
            log_path=None,
            verification_status="passed",
            verification_failed_command=None,
            reviewer_status="passed",
            reviewer_decision="approved",
            failed_reviewer_id=None,
        ),
    )

    service.run(_build_request())

    completion_dependencies = observed["completion_dependencies"]
    assert isinstance(completion_dependencies, dict)
    assert completion_dependencies["commit_feature_completion"](
        Path("/tmp/project"),
        {"expected_commit_subject": "feat: complete FEAT-001"},
    ) == (True, None, "ok\n")


def test_commit_feature_completion_returns_failure_tuple_shape() -> None:
    """Internal commit wiring should preserve the pipeline callback contract."""
    observed: dict[str, object] = {}
    gateway = _FakeVersionControlGateway(
        observed,
        CommitResult(
            stdout="commit stdout\n",
            stderr="commit stderr\n",
            commit_created=False,
            commit_sha=None,
            failure_stage="git_commit",
        ),
    )

    outcome = commit_feature_completion(
        gateway,
        project_root=Path("/tmp/project"),
        feature={"expected_commit_subject": "feat: complete FEAT-001"},
    )

    assert outcome == (False, "git_commit", "commit stdout\ncommit stderr\n")
    assert observed["commit_requests"] == [
        CommitRequest(
            workspace_path=Path("/tmp/project"),
            message="feat: complete FEAT-001",
            stage_all=True,
            allow_empty=False,
        )
    ]


def test_persist_iteration_report_writes_json_payload_to_journal() -> None:
    """Internal report persistence should stay on the journal port boundary."""
    observed: dict[str, object] = {}
    journal = _FakeProgressJournal(observed)
    report = cast(
        IterationReport,
        SimpleNamespace(
            telemetry_inputs=SimpleNamespace(
                iteration_inputs=SimpleNamespace(project_root=Path("/tmp/project"))
            ),
            feature_id="FEAT-001",
            model_dump=lambda mode="json": {"result": "failed", "mode": mode},
        ),
    )

    persist_iteration_report(journal, report)

    assert observed["iteration_reports"] == [
        {
            "project_root": Path("/tmp/project"),
            "feature_id": "FEAT-001",
            "payload": {"result": "failed", "mode": "json"},
        }
    ]


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
