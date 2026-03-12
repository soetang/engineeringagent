from __future__ import annotations

from pathlib import Path

from engineeringagent.application.feature_iteration_service import (
    FeatureIterationInputs,
    IterationReport,
    IterationSummaryInputs,
    IterationTelemetryInputs,
)
from engineeringagent.bootstrap.iteration_reporting import (
    ConsoleObserverDependencies,
    DefaultObserverDependencies,
    DefaultIterationReportPublisher,
    TelemetryObserverDependencies,
    build_console_observer,
    build_default_iteration_report_observers,
    build_progress_artifact_observer,
    build_telemetry_observer,
    publish_iteration_report,
)


def _build_iteration_report(
    tmp_path: Path, *, result: str = "passed"
) -> IterationReport:
    iteration_inputs = FeatureIterationInputs(
        project_root=tmp_path,
        feature_path=tmp_path / "docs" / "spec" / "features" / "FEAT-116.yaml",
        attempt=2,
        feedback=None,
        verbose_output=False,
    )
    telemetry_inputs = IterationTelemetryInputs(
        iteration_inputs=iteration_inputs,
        started=1000.0,
        feature_id="FEAT-116",
        result=result,
        failed_gate="spec_validate" if result == "failed" else None,
        next_action="retry_same_feature"
        if result == "failed"
        else "continue_same_feature",
        implement_status="passed",
        gate_status="passed",
        verification_status="passed",
        verification_failed_command=None,
        reviewer_status="not_run",
        reviewer_decision=None,
        failed_reviewer_id=None,
        implement_output="",
        gate_output="",
        verification_output="",
        reviewer_output="",
        feedback=None,
    )
    return IterationReport(
        completed=False,
        result=result,
        failed_gate=telemetry_inputs.failed_gate,
        next_action=telemetry_inputs.next_action,
        feedback=None,
        feature_id="FEAT-116",
        attempt=2,
        selected_feature_path=str(iteration_inputs.feature_path),
        implement_step="engineeringagent implement",
        telemetry_inputs=telemetry_inputs,
    )


def test_publish_iteration_report_applies_observers_in_order(tmp_path: Path) -> None:
    """Apply iteration report observers in deterministic order."""
    observed: list[str] = []
    report = _build_iteration_report(tmp_path)

    def _first(input_report: IterationReport) -> IterationReport:
        observed.append("first")
        return input_report.model_copy(
            update={"log_path": "progress/run-feature-FEAT-116.txt"}
        )

    def _second(input_report: IterationReport) -> IterationReport:
        observed.append("second")
        assert input_report.log_path == "progress/run-feature-FEAT-116.txt"
        return input_report

    published_report = publish_iteration_report(report, (_first, _second))

    assert observed == ["first", "second"]
    assert published_report.log_path == "progress/run-feature-FEAT-116.txt"


def test_telemetry_observer_writes_telemetry_and_sets_log_path(tmp_path: Path) -> None:
    """Persist telemetry before returning the updated log path."""
    captured: list[IterationTelemetryInputs] = []
    report = _build_iteration_report(tmp_path)
    observer = build_telemetry_observer(
        TelemetryObserverDependencies(
            write_iteration_telemetry=(
                lambda telemetry_inputs: (
                    captured.append(telemetry_inputs),
                    "progress/run-feature-FEAT-116.txt",
                )[-1]
            )
        )
    )

    published_report = observer(report)

    assert captured == [report.telemetry_inputs]
    assert published_report.log_path == "progress/run-feature-FEAT-116.txt"


def test_console_observer_prints_summary_and_failed_log_pointer(tmp_path: Path) -> None:
    """Render failed iteration summaries with the published log path."""
    calls: list[IterationSummaryInputs] = []
    report = _build_iteration_report(tmp_path, result="failed").model_copy(
        update={
            "log_path": "progress/run-feature-FEAT-116.txt",
            "telemetry_inputs": _build_iteration_report(
                tmp_path, result="failed"
            ).telemetry_inputs.model_copy(
                update={
                    "progress_kind": "phase",
                    "progress_id": "P3",
                    "progress_title": (
                        "Move implementation sequencing from subtasks to plan phases"
                    ),
                }
            ),
        }
    )
    observer = build_console_observer(
        ConsoleObserverDependencies(print_summary=calls.append)
    )

    published_report = observer(report)

    assert len(calls) == 1
    assert calls[0].feature_id == "FEAT-116"
    assert calls[0].result == "failed"
    assert calls[0].log_path == "progress/run-feature-FEAT-116.txt"
    assert calls[0].progress_kind == "phase"
    assert calls[0].progress_id == "P3"
    assert published_report is report


def test_progress_artifact_observer_persists_finalized_report(tmp_path: Path) -> None:
    """Persist the finalized report without mutating it."""
    captured: list[IterationReport] = []
    report = _build_iteration_report(tmp_path).model_copy(
        update={"log_path": "progress/run-feature-FEAT-116.txt"}
    )

    observer = build_progress_artifact_observer(captured.append)

    published_report = observer(report)

    assert captured == [report]
    assert published_report is report


def test_default_observers_publish_telemetry_before_console(tmp_path: Path) -> None:
    """Publish telemetry and report artifacts before console rendering."""
    calls: list[tuple[str, str]] = []
    summary_log_paths: list[str | None] = []
    report = _build_iteration_report(tmp_path, result="failed")

    def _record_summary(summary: IterationSummaryInputs) -> None:
        calls.append(("console", "summary"))
        summary_log_paths.append(summary.log_path)

    observers = build_default_iteration_report_observers(
        DefaultObserverDependencies(
            write_iteration_telemetry=(
                lambda telemetry_inputs: (
                    calls.append(("telemetry", telemetry_inputs.feature_id)),
                    "progress/run-feature-FEAT-116.txt",
                )[-1]
            ),
            persist_iteration_report=(
                lambda iteration_report: calls.append(
                    ("progress", iteration_report.log_path or "-")
                )
            ),
            git_head_resolver=lambda _project_root: "abc1234",
            print_summary=_record_summary,
        )
    )

    published_report = publish_iteration_report(report, observers)

    assert calls == [
        ("telemetry", "FEAT-116"),
        ("progress", "progress/run-feature-FEAT-116.txt"),
        ("console", "summary"),
    ]
    assert summary_log_paths == ["progress/run-feature-FEAT-116.txt"]
    assert published_report.log_path == "progress/run-feature-FEAT-116.txt"


def test_default_iteration_report_publisher_returns_outcome_from_published_report(
    tmp_path: Path,
) -> None:
    """Publish the report through the default observer chain and return its outcome."""
    calls: list[tuple[str, str]] = []
    report = _build_iteration_report(tmp_path, result="failed")
    publisher = DefaultIterationReportPublisher(
        DefaultObserverDependencies(
            write_iteration_telemetry=(
                lambda telemetry_inputs: (
                    calls.append(("telemetry", telemetry_inputs.feature_id)),
                    "progress/run-feature-FEAT-116.txt",
                )[-1]
            ),
            persist_iteration_report=(
                lambda iteration_report: calls.append(
                    ("progress", iteration_report.feature_id)
                )
            ),
            git_head_resolver=lambda _project_root: "abc1234",
            print_summary=lambda summary: calls.append(("console", summary.feature_id or "")),
        )
    )

    outcome = publisher.publish(report)

    assert calls == [
        ("telemetry", "FEAT-116"),
        ("progress", "FEAT-116"),
        ("console", "FEAT-116"),
    ]
    assert outcome.result == "failed"
    assert outcome.log_path == "progress/run-feature-FEAT-116.txt"
