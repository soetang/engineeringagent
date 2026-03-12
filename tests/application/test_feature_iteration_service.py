from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence

from engineeringagent.application import (
    FeatureIterationService,
)
from engineeringagent.application.feature_iteration.contracts import (
    CompletionCommitOutcome,
    FeatureIterationInputs,
    GatePhaseOutcome,
    IterationOutcome,
    IterationReport,
    IterationTelemetryInputs,
    PhaseTiming,
    ReviewerPhaseOutcome,
    VerificationPhaseOutcome,
)
from engineeringagent.application.feature_iteration.runtime_dependencies import (
    FeatureIterationDependencies,
)
from engineeringagent.application.feature_iteration_service import (
    FeatureIterationRequest,
)
from engineeringagent.domain.audit import ProgressEvent
from engineeringagent.domain.specification import (
    InitialFeatureLoadOutcome,
    PostImplementFeatureOutcome,
)
from engineeringagent.ports import (
    CommitRequest,
    CommitResult,
    DiffSummary,
    WorktreeStatus,
)


class _FakeClock:
    def now_epoch_seconds(self) -> float:
        return 0.0


class _FakeGatePhaseDependencies:
    def __init__(self, observed: dict[str, object], **kwargs: object) -> None:
        observed["gate_dependencies"] = kwargs
        for key, value in kwargs.items():
            setattr(self, key, value)

    def model_copy(self, *, update: dict[str, object]) -> "_FakeGatePhaseDependencies":
        return _FakeGatePhaseDependencies({}, **update)


class _FakeReviewerPhaseDependencies:
    def __init__(self, observed: dict[str, object], **kwargs: object) -> None:
        observed["reviewer_dependencies"] = kwargs
        for key, value in kwargs.items():
            setattr(self, key, value)

    def model_copy(
        self, *, update: dict[str, object]
    ) -> "_FakeReviewerPhaseDependencies":
        return _FakeReviewerPhaseDependencies({}, **update)


class _FakeCompletionPhaseDependencies:
    def __init__(self, observed: dict[str, object], **kwargs: object) -> None:
        observed["completion_dependencies"] = kwargs
        for key, value in kwargs.items():
            setattr(self, key, value)


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


def _build_runtime_dependencies(
    observed: dict[str, object],
) -> FeatureIterationDependencies:
    return FeatureIterationDependencies(
        clock=_FakeClock(),
        evaluate_initial_feature_load=lambda _feature_path: InitialFeatureLoadOutcome(
            feature={
                "id": "FEAT-001",
                "title": "Refactor iteration workflow",
                "status": "active",
            },
            result="passed",
            failed_gate=None,
            feedback=None,
        ),
        describe_action=lambda project_root, action, structured: (
            f"{project_root}:{action}:{structured}"
        ),
        ready_for_active_iteration=lambda _result, _feature: True,
        touch_active_feature_for_iteration=lambda feature, path: observed.update(
            {"touched_active_feature": (feature["id"], path)}
        ),
        run_implement_step=lambda *_args, **_kwargs: (
            True,
            None,
            "implemented",
            None,
            False,
        ),
        refresh_feature_after_implement=lambda _project_root, _feature_path: (
            PostImplementFeatureOutcome(
                feature={
                    "id": "FEAT-001",
                    "title": "Refactor iteration workflow",
                    "status": "done",
                },
                archived_in_iteration=False,
                archived_path=None,
                result="passed",
                failed_gate=None,
                feedback="rerun focused tests",
            )
        ),
        should_archive_selected_feature=lambda _result, _feature: False,
        archive_completed_feature=lambda _project_root, _feature_path: (False, None, None),
        collect_changed_paths=lambda _project_root: [],
        restore_archived_feature=lambda _archived_path, _feature_path: (True, None),
        run_gate_phase=lambda _inputs, _archived, _archived_path, _deps: GatePhaseOutcome(
            result="failed",
            failed_gate="tests",
            gate_status="failed:tests",
            gate_output="tests failed",
            command_timings=[],
            feedback="rerun focused tests",
        ),
        build_gate_phase_dependencies=lambda **kwargs: _FakeGatePhaseDependencies(
            observed, **kwargs
        ),
        run_verification_phase=lambda _inputs, _commands: VerificationPhaseOutcome(
            result="passed",
            verification_status="passed",
            verification_failed_command=None,
            verification_output="verification ok",
            command_timings=[],
            feedback=None,
        ),
        run_reviewer_phase=lambda _inputs, _feature, _archived, _archived_path, _deps: ReviewerPhaseOutcome(
            result="passed",
            failed_gate=None,
            reviewer_status="not_run",
            reviewer_decision=None,
            failed_reviewer_id=None,
            reviewer_output="",
            command_timings=[],
            feedback=None,
            archived_rolled_back=False,
        ),
        build_reviewer_phase_dependencies=lambda **kwargs: _FakeReviewerPhaseDependencies(
            observed, **kwargs
        ),
        run_completion_commit_phase=lambda _inputs, _feature, _archived, _archived_path, _deps: CompletionCommitOutcome(
            completed=False,
            completion_commit_succeeded=False,
            result="passed",
            failed_gate=None,
            next_action="continue_same_feature",
            feedback=None,
            completion_output="",
            archived_rolled_back=False,
        ),
        build_completion_phase_dependencies=lambda **kwargs: _FakeCompletionPhaseDependencies(
            observed, **kwargs
        ),
    )


def _build_service(observed: dict[str, object]) -> FeatureIterationService:
    def _publish_iteration_report(report: IterationReport) -> IterationOutcome:
        observed["published_report"] = report
        return IterationOutcome.from_report(
            report.model_copy(
                update={
                    "log_path": ".engineeringagent/progress/FEAT-001/iteration-report.json"
                }
            )
        )

    return FeatureIterationService(
        version_control_gateway=_FakeVersionControlGateway(
            observed,
            CommitResult(
                stdout="",
                stderr="",
                commit_created=True,
                commit_sha="abc1234",
                failure_stage=None,
            ),
        ),
        iteration_report_publisher=_publish_iteration_report,
        dependencies=_build_runtime_dependencies(observed),
    )


def test_feature_iteration_service_executes_application_owned_pipeline() -> None:
    """The application service should execute the pipeline and publish its report."""
    observed: dict[str, object] = {}
    service = _build_service(observed)

    result = service.run(_build_request())

    assert result.result == "failed"
    assert result.failed_gate == "tests"
    assert result.next_action == "retry_same_feature"
    assert (
        result.log_path
        == ".engineeringagent/progress/FEAT-001/iteration-report.json"
    )
    published_report = observed["published_report"]
    assert isinstance(published_report, IterationReport)
    assert published_report.feature_id == "FEAT-001"
    assert published_report.attempt == 3
    assert published_report.telemetry_inputs.gate_status == "failed:tests"


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
