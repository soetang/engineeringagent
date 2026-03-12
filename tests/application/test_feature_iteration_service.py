from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence

from engineeringagent.application import FeatureIterationRequest, FeatureIterationService
from engineeringagent.application.feature_iteration import (
    FeatureIterationInputs,
    IterationOutcome,
    IterationReport,
    IterationTelemetryInputs,
    PhaseTiming,
)
from engineeringagent.domain.audit import ProgressEvent
from engineeringagent.ports import (
    CommitRequest,
    CommitResult,
    DiffSummary,
    FeatureIterationExecutionRequest,
    FeatureIterationExecutionResult,
    WorktreeStatus,
)


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
    execution_result: FeatureIterationExecutionResult,
) -> FeatureIterationService:
    class _FakeFeatureIterationExecutor:
        def run(
            self,
            request: FeatureIterationExecutionRequest,
        ) -> FeatureIterationExecutionResult:
            observed["execution_request"] = request
            return execution_result

    return FeatureIterationService(executor=_FakeFeatureIterationExecutor())


def test_feature_iteration_service_executes_runtime_pipeline() -> None:
    """The application service should delegate feature execution through its port."""
    observed: dict[str, object] = {}
    service = _build_service(
        observed,
        execution_result=FeatureIterationExecutionResult(
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
    assert observed["execution_request"] == FeatureIterationExecutionRequest(
        project_root=Path("/tmp/project"),
        feature_path=Path("docs/specifications/features/FEAT-001/specification.yaml"),
        run_all=False,
        attempt=3,
        feedback="fix the failing check",
        verbose_output=True,
    )
    assert result.failed_gate == "tests"
    assert result.next_action == "retry_same_feature"
    assert (
        result.log_path
        == ".engineeringagent/progress/FEAT-001/iteration-report.json"
    )


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
