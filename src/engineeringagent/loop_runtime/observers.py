"""Iteration report observers for telemetry and console output."""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Sequence

from pydantic import BaseModel, ConfigDict

from .models import IterationReport, IterationTelemetryInputs

PrintSummaryFn = Callable[
    [
        str | None,
        str,
        str | None,
        int | None,
        str,
        str | None,
        str | None,
        str | None,
        str | None,
        str | None,
        str | None,
        str | None,
        str | None,
        str | None,
    ],
    None,
]


class TelemetryObserverDependencies(BaseModel):
    """Dependencies for telemetry observer behavior."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    write_iteration_telemetry: Callable[
        [IterationTelemetryInputs, Callable[[Path], str | None]],
        str,
    ]
    git_head_resolver: Callable[[Path], str | None]


class ConsoleObserverDependencies(BaseModel):
    """Dependencies for console observer behavior."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    print_summary: PrintSummaryFn
    print_line: Callable[[str], None]


class DefaultObserverDependencies(BaseModel):
    """Dependencies for building the default iteration observer chain."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    write_iteration_telemetry: Callable[
        [IterationTelemetryInputs, Callable[[Path], str | None]],
        str,
    ]
    git_head_resolver: Callable[[Path], str | None]
    print_summary: PrintSummaryFn
    print_line: Callable[[str], None]


IterationReportObserver = Callable[[IterationReport], IterationReport]


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
            report.telemetry_inputs,
            dependencies.git_head_resolver,
        )
        return report.model_copy(update={"log_path": feature_progress_log_reference})

    return _observe


def build_console_observer(
    dependencies: ConsoleObserverDependencies,
) -> IterationReportObserver:
    """Build observer that renders run summary and failure log pointer."""

    def _observe(report: IterationReport) -> IterationReport:
        dependencies.print_summary(
            report.feature_id,
            report.result,
            report.failed_gate,
            report.attempt,
            report.next_action,
            report.selected_feature_path,
            report.implement_step,
            report.log_path if report.result != "passed" else None,
            report.archived_selection_path,
            report.verification_status,
            report.verification_failed_command,
            report.reviewer_status,
            report.reviewer_decision,
            report.failed_reviewer_id,
        )
        if report.result != "passed" and report.log_path:
            dependencies.print_line(f"Detailed log: {report.log_path}")
        return report

    return _observe


def build_default_iteration_report_observers(
    dependencies: DefaultObserverDependencies,
) -> tuple[IterationReportObserver, IterationReportObserver]:
    """Build the default observer chain (telemetry first, then console)."""

    telemetry_observer = build_telemetry_observer(
        TelemetryObserverDependencies(
            write_iteration_telemetry=dependencies.write_iteration_telemetry,
            git_head_resolver=dependencies.git_head_resolver,
        )
    )
    console_observer = build_console_observer(
        ConsoleObserverDependencies(
            print_summary=dependencies.print_summary,
            print_line=dependencies.print_line,
        )
    )
    return (telemetry_observer, console_observer)
