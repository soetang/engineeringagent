"""Bootstrap-owned iteration report publishing helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Sequence

from pydantic import BaseModel, ConfigDict

from engineeringagent.application.feature_iteration.contracts import (
    IterationOutcome,
    IterationReport,
    IterationSummaryInputs,
    IterationTelemetryInputs,
)

PrintSummaryFn = Callable[[IterationSummaryInputs], None]
IterationReportObserver = Callable[[IterationReport], IterationReport]
IterationReportPublisher = Callable[[IterationReport], IterationOutcome]


class TelemetryObserverDependencies(BaseModel):
    """Dependencies for telemetry observer behavior."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    write_iteration_telemetry: Callable[
        [IterationTelemetryInputs],
        str,
    ]


class ConsoleObserverDependencies(BaseModel):
    """Dependencies for console observer behavior."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    print_summary: PrintSummaryFn


class DefaultObserverDependencies(BaseModel):
    """Dependencies for building the default iteration observer chain."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    write_iteration_telemetry: Callable[[IterationTelemetryInputs], str]
    persist_iteration_report: Callable[[IterationReport], None]
    git_head_resolver: Callable[[Path], str | None]
    print_summary: PrintSummaryFn


class DefaultIterationReportPublisher:
    """Publish iteration reports through the default observer chain."""

    def __init__(self, dependencies: DefaultObserverDependencies) -> None:
        self._observers = build_default_iteration_report_observers(dependencies)

    def publish(self, report: IterationReport) -> IterationOutcome:
        """Publish one report through the default observer chain."""
        published_report = publish_iteration_report(report, self._observers)
        return IterationOutcome.from_report(published_report)

    def __call__(self, report: IterationReport) -> IterationOutcome:
        """Publish one report through the default observer chain."""
        return self.publish(report)


def publish_iteration_report(
    report: IterationReport,
    observers: Sequence[IterationReportObserver],
) -> IterationReport:
    """Publish an iteration report to observers in deterministic order."""
    published_report = report
    for observer in observers:
        published_report = observer(published_report)
    return published_report


def build_telemetry_observer(
    dependencies: TelemetryObserverDependencies,
) -> IterationReportObserver:
    """Build observer that writes telemetry artifacts and records log path."""

    def _observe(report: IterationReport) -> IterationReport:
        feature_progress_log_reference = dependencies.write_iteration_telemetry(
            report.telemetry_inputs
        )
        return report.model_copy(update={"log_path": feature_progress_log_reference})

    return _observe


def build_console_observer(
    dependencies: ConsoleObserverDependencies,
) -> IterationReportObserver:
    """Build observer that renders the run summary."""

    def _observe(report: IterationReport) -> IterationReport:
        dependencies.print_summary(
            IterationSummaryInputs(
                feature_id=report.feature_id,
                result=report.result,
                failed_gate=report.failed_gate,
                attempt=report.attempt,
                next_action=report.next_action,
                selected_path=report.selected_feature_path,
                implement_step=report.implement_step,
                log_path=report.log_path if report.result != "passed" else None,
                archived_selection_path=report.archived_selection_path,
                verification_status=report.verification_status,
                verification_failed_command=report.verification_failed_command,
                reviewer_status=report.reviewer_status,
                reviewer_decision=report.reviewer_decision,
                failed_reviewer_id=report.failed_reviewer_id,
                progress_kind=report.telemetry_inputs.progress_kind,
                progress_id=report.telemetry_inputs.progress_id,
                progress_title=report.telemetry_inputs.progress_title,
            )
        )
        return report

    return _observe


def build_progress_artifact_observer(
    persist_iteration_report: Callable[[IterationReport], None],
) -> IterationReportObserver:
    """Build observer that persists the finalized iteration report artifact."""

    def _observe(report: IterationReport) -> IterationReport:
        persist_iteration_report(report)
        return report

    return _observe


def build_default_iteration_report_observers(
    dependencies: DefaultObserverDependencies,
) -> tuple[IterationReportObserver, IterationReportObserver, IterationReportObserver]:
    """Build the default observer chain (telemetry, progress artifacts, console)."""
    _ = dependencies.git_head_resolver
    telemetry_observer = build_telemetry_observer(
        TelemetryObserverDependencies(
            write_iteration_telemetry=dependencies.write_iteration_telemetry,
        )
    )
    progress_observer = build_progress_artifact_observer(
        dependencies.persist_iteration_report
    )
    console_observer = build_console_observer(
        ConsoleObserverDependencies(print_summary=dependencies.print_summary)
    )
    return (telemetry_observer, progress_observer, console_observer)
