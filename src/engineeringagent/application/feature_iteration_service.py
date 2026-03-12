"""Application service for feature-iteration execution requests."""

from __future__ import annotations

from importlib import import_module
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from pydantic import BaseModel, ConfigDict

from engineeringagent.domain.specification import feature_completion_commit_subject
from engineeringagent.ports import CommitRequest, ProgressJournal, VersionControlGateway


class FeatureIterationRequest(BaseModel):
    """Typed input for one feature-iteration execution request."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    project_root: Path
    feature_path: Path
    run_all: bool = False
    attempt: int
    feedback: str | None
    verbose_output: bool


class FeatureIterationResult(BaseModel):
    """Stable application result for one feature-iteration execution."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    completed: bool
    result: str
    failed_gate: str | None
    next_action: str
    feedback: str | None
    log_path: str | None
    verification_status: str = "not_run"
    verification_failed_command: str | None = None
    reviewer_status: str = "not_run"
    reviewer_decision: str | None = None
    failed_reviewer_id: str | None = None


class _RuntimeModules(SimpleNamespace):
    """Imported runtime modules grouped to keep service wiring compact."""

    checks: Any
    support: Any
    feature_state: Any
    iteration: Any
    models: Any
    phases: Any


class FeatureIterationRuntimeDependencies:
    """Application-owned runtime seams for the transitional iteration pipeline."""

    def __init__(
        self,
        *,
        write_iteration_telemetry_fn: Any | None = None,
        build_iteration_report_observers_fn: Any | None = None,
        publish_iteration_report_fn: Any | None = None,
    ) -> None:
        iteration_reporting = import_module(
            "engineeringagent.bootstrap.iteration_reporting"
        )
        progress_adapter = import_module("engineeringagent.adapters.progress")
        self.write_iteration_telemetry = (
            write_iteration_telemetry_fn or progress_adapter.write_iteration_telemetry
        )
        self.build_iteration_report_observers = (
            build_iteration_report_observers_fn
            or iteration_reporting.build_default_iteration_report_observers
        )
        self.publish_iteration_report = (
            publish_iteration_report_fn or iteration_reporting.publish_iteration_report
        )
        self.observer_dependencies_type = iteration_reporting.DefaultObserverDependencies
        self.runtime = _RuntimeModules(
            checks=import_module("engineeringagent.checks"),
            support=import_module("engineeringagent.bootstrap.runtime_support"),
            feature_state=import_module("engineeringagent.loop_runtime.feature_state"),
            iteration=import_module("engineeringagent.loop_runtime.iteration"),
            models=import_module("engineeringagent.domain.audit.iteration"),
            phases=import_module("engineeringagent.adapters.runtime.iteration_phases"),
        )


class FeatureIterationService:
    """Own feature-iteration sequencing behind a stable application contract."""

    def __init__(
        self,
        *,
        version_control_gateway: VersionControlGateway,
        progress_journal: ProgressJournal,
        runtime_dependencies: FeatureIterationRuntimeDependencies | None = None,
    ) -> None:
        self._version_control_gateway = version_control_gateway
        self._progress_journal = progress_journal
        self._runtime_dependencies = (
            runtime_dependencies or FeatureIterationRuntimeDependencies()
        )

    def run(self, request: FeatureIterationRequest) -> FeatureIterationResult:
        """Execute one feature iteration through the runtime pipeline."""

        def _commit_feature_completion(
            project_root: Path,
            feature: dict[str, object],
        ) -> tuple[bool, str | None, str]:
            message = feature_completion_commit_subject(feature)
            commit_result = self._version_control_gateway.commit(
                CommitRequest(
                    workspace_path=project_root,
                    message=message,
                    stage_all=True,
                    allow_empty=False,
                )
            )
            output = commit_result.stdout + commit_result.stderr
            if commit_result.commit_created:
                return (True, None, output)
            return (False, commit_result.failure_stage, output)

        def _persist_iteration_report(report: Any) -> None:
            self._progress_journal.write_iteration_report(
                project_root=report.telemetry_inputs.iteration_inputs.project_root,
                feature_id=report.feature_id,
                payload=report.model_dump(mode="json"),
            )

        runtime = self._runtime_dependencies.runtime
        report = runtime.iteration.run_feature_iteration_pipeline(
            runtime.models.FeatureIterationInputs(
                project_root=request.project_root,
                feature_path=request.feature_path,
                run_all=request.run_all,
                attempt=request.attempt,
                feedback=request.feedback,
                verbose_output=request.verbose_output,
            ),
            runtime.iteration.IterationPipelineDependencies(
                evaluate_initial_feature_load=(
                    runtime.feature_state.evaluate_initial_feature_load
                ),
                ready_for_active_iteration=(
                    runtime.feature_state.ready_for_active_iteration
                ),
                touch_active_feature_for_iteration=(
                    runtime.feature_state.touch_active_feature_for_iteration
                ),
                run_implement_step=runtime.support.run_implement_step,
                refresh_feature_after_implement=(
                    runtime.feature_state.refresh_feature_after_implement
                ),
                should_archive_selected_feature=(
                    runtime.feature_state.should_archive_selected_feature
                ),
                archive_completed_feature=(
                    runtime.feature_state.archive_completed_feature
                ),
                run_gate_phase=runtime.phases.run_gate_phase,
                gate_phase_dependencies=runtime.phases.GatePhaseDependencies(
                    restore_archived_feature=(
                        runtime.feature_state.restore_archived_feature
                    ),
                    collect_changed_paths=runtime.checks.collect_changed_paths,
                ),
                run_verification_phase=runtime.phases.run_verification_phase,
                run_reviewer_phase=runtime.phases.run_reviewer_phase,
                reviewer_phase_dependencies=runtime.phases.ReviewerPhaseDependencies(
                    collect_changed_paths=runtime.checks.collect_changed_paths,
                    restore_archived_feature=(
                        runtime.feature_state.restore_archived_feature
                    ),
                ),
                run_completion_commit_phase=runtime.phases.run_completion_commit_phase,
                completion_phase_dependencies=runtime.phases.CompletionPhaseDependencies(
                    commit_feature_completion=_commit_feature_completion,
                    restore_archived_feature=(
                        runtime.feature_state.restore_archived_feature
                    ),
                ),
            ),
        )
        observers = self._runtime_dependencies.build_iteration_report_observers(
            self._runtime_dependencies.observer_dependencies_type(
                write_iteration_telemetry=(
                    lambda telemetry_inputs: self._runtime_dependencies.write_iteration_telemetry(
                        telemetry_inputs,
                        git_head_resolver=runtime.support.git_head_short,
                    )
                ),
                persist_iteration_report=_persist_iteration_report,
                git_head_resolver=runtime.support.git_head_short,
                print_summary=runtime.support.print_summary,
            )
        )
        outcome = self._runtime_dependencies.publish_iteration_report(report, observers)
        return FeatureIterationResult(
            completed=outcome.completed,
            result=outcome.result,
            failed_gate=outcome.failed_gate,
            next_action=outcome.next_action,
            feedback=outcome.feedback,
            log_path=outcome.log_path,
            verification_status=outcome.verification_status,
            verification_failed_command=outcome.verification_failed_command,
            reviewer_status=outcome.reviewer_status,
            reviewer_decision=outcome.reviewer_decision,
            failed_reviewer_id=outcome.failed_reviewer_id,
        )
