from __future__ import annotations

from pathlib import Path

from engineeringagent.loop_runtime.models import (
    FeatureIterationInputs,
    IterationReport,
    IterationTelemetryInputs,
)
from engineeringagent.loop_runtime.observers import (
    ConsoleObserverDependencies,
    DefaultObserverDependencies,
    TelemetryObserverDependencies,
    build_default_iteration_report_observers,
    build_console_observer,
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
        hook_feedback=None,
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
        hook_feedback=None,
    )
    return IterationReport(
        completed=False,
        result=result,
        failed_gate=telemetry_inputs.failed_gate,
        next_action=telemetry_inputs.next_action,
        hook_feedback=None,
        feature_id="FEAT-116",
        attempt=2,
        selected_feature_path=str(iteration_inputs.feature_path),
        implement_step="engineeringagent implement",
        telemetry_inputs=telemetry_inputs,
    )


def test_publish_iteration_report_applies_observers_in_order(tmp_path: Path) -> None:
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
    captured: list[IterationTelemetryInputs] = []
    report = _build_iteration_report(tmp_path)
    observer = build_telemetry_observer(
        TelemetryObserverDependencies(
            write_iteration_telemetry=(
                lambda telemetry_inputs, git_head_resolver: (
                    captured.append(telemetry_inputs),
                    git_head_resolver(telemetry_inputs.iteration_inputs.project_root),
                    "progress/run-feature-FEAT-116.txt",
                )[-1]
            ),
            git_head_resolver=lambda _project_root: "abc1234",
        )
    )

    published_report = observer(report)

    assert captured == [report.telemetry_inputs]
    assert published_report.log_path == "progress/run-feature-FEAT-116.txt"


def test_console_observer_prints_summary_and_failed_log_pointer(tmp_path: Path) -> None:
    calls: list[tuple[str, ...]] = []
    printed: list[str] = []
    report = _build_iteration_report(tmp_path, result="failed").model_copy(
        update={"log_path": "progress/run-feature-FEAT-116.txt"}
    )
    observer = build_console_observer(
        ConsoleObserverDependencies(
            print_summary=(
                lambda feature_id, result, failed_gate, attempt, next_action, selected_path, implement_step, log_path, archived_selection_path, verification_status, verification_failed_command, reviewer_status, reviewer_decision, failed_reviewer_id: (
                    calls.append(
                        (
                            str(feature_id),
                            result,
                            str(failed_gate),
                            str(attempt),
                            next_action,
                            str(selected_path),
                            str(implement_step),
                            str(log_path),
                            str(archived_selection_path),
                            str(verification_status),
                            str(verification_failed_command),
                            str(reviewer_status),
                            str(reviewer_decision),
                            str(failed_reviewer_id),
                        )
                    )
                )
            ),
            print_line=printed.append,
        )
    )

    published_report = observer(report)

    assert len(calls) == 1
    assert calls[0][0] == "FEAT-116"
    assert calls[0][1] == "failed"
    assert calls[0][7] == "progress/run-feature-FEAT-116.txt"
    assert printed == ["Detailed log: progress/run-feature-FEAT-116.txt"]
    assert published_report is report


def test_default_observers_publish_telemetry_before_console(tmp_path: Path) -> None:
    calls: list[tuple[str, str]] = []
    summary_log_paths: list[str | None] = []
    report = _build_iteration_report(tmp_path, result="failed")

    def _record_summary(
        _feature_id: str | None,
        _result: str,
        _failed_gate: str | None,
        _attempt: int | None,
        _next_action: str,
        _selected_path: str | None,
        _implement_step: str | None,
        log_path: str | None,
        _archived_selection_path: str | None,
        _verification_status: str | None,
        _verification_failed_command: str | None,
        _reviewer_status: str | None,
        _reviewer_decision: str | None,
        _failed_reviewer_id: str | None,
    ) -> None:
        calls.append(("console", "summary"))
        summary_log_paths.append(log_path)

    observers = build_default_iteration_report_observers(
        DefaultObserverDependencies(
            write_iteration_telemetry=(
                lambda telemetry_inputs, _git_head_resolver: (
                    calls.append(("telemetry", telemetry_inputs.feature_id)),
                    "progress/run-feature-FEAT-116.txt",
                )[-1]
            ),
            git_head_resolver=lambda _project_root: "abc1234",
            print_summary=_record_summary,
            print_line=lambda _message: None,
        )
    )

    published_report = publish_iteration_report(report, observers)

    assert calls == [("telemetry", "FEAT-116"), ("console", "summary")]
    assert summary_log_paths == ["progress/run-feature-FEAT-116.txt"]
    assert published_report.log_path == "progress/run-feature-FEAT-116.txt"
