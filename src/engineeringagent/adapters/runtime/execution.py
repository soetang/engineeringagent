"""Adapters that bridge application executor ports to the legacy runtime pipeline."""

from __future__ import annotations

from importlib import import_module
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable

from engineeringagent.adapters.progress import write_iteration_telemetry
from engineeringagent.application import FeatureIterationRequest
from engineeringagent.application.feature_iteration_service import (
    FeatureIterationService,
)
from engineeringagent.bootstrap.iteration_reporting import (
    DefaultObserverDependencies,
    build_default_iteration_report_observers,
    publish_iteration_report,
)
from engineeringagent.domain.audit import (
    FeatureIterationInputs,
    IterationOutcome,
    IterationSummaryInputs,
)
from engineeringagent.domain.specification import feature_completion_commit_subject
from engineeringagent.ports import (
    CommitRequest,
    FeatureIterationExecutionRequest,
    FeatureIterationExecutionResult,
    FeatureIterationExecutor,
    ProgressJournal,
    RunLoopExecutionRequest,
    RunLoopExecutor,
    VersionControlGateway,
)
from .loop_run_builder import (
    RunConfigOptions,
    build_loop_run,
    build_run_config,
    enforce_worktree_precondition,
    run_selected_feature_iterations,
)
from .loop_run_context import LoopRun


def run_loop_controller(loop_run: LoopRun) -> int:
    """Execute run-loop orchestration through the runtime adapter boundary."""
    config = loop_run.config
    services = loop_run.services

    if config.max_iterations < 1:
        print("max_iterations must be >= 1")
        return 1

    try:
        resolved_paths = services.resolve_run_targets(
            config.project_root,
            config.feature_paths,
            config.run_all,
        )
    except ValueError as exc:
        print(exc)
        return 1

    run_all_feedback_exit_code = services.emit_run_all_snapshot_feedback(
        resolved_paths,
        config.run_all,
    )
    if run_all_feedback_exit_code is not None:
        return run_all_feedback_exit_code

    dry_run_exit_code = services.handle_dry_run(
        resolved_paths,
        config.run_all,
        config.dry_run,
    )
    if dry_run_exit_code is not None:
        return dry_run_exit_code

    worktree_precondition_exit_code = services.enforce_worktree_precondition(
        config.project_root,
        config.allow_dirty,
    )
    if worktree_precondition_exit_code is not None:
        return worktree_precondition_exit_code

    if not services.run_permission_precheck(project_root=config.project_root):
        return 1

    state = loop_run.state.with_resolved_feature_paths(resolved_paths)
    return services.run_selected_feature_iterations(loop_run.with_state(state))


class RuntimeRunLoopExecutor(RunLoopExecutor):
    """Execute run-loop requests through the loop runtime package."""

    def __init__(
        self,
        *,
        build_feature_iteration_service: Callable[[Path], FeatureIterationService],
        build_version_control_gateway: Callable[[Path], VersionControlGateway],
    ) -> None:
        self._build_feature_iteration_service = build_feature_iteration_service
        self._build_version_control_gateway = build_version_control_gateway

    def run(self, request: RunLoopExecutionRequest) -> int:
        """Build loop config and execute the runtime controller."""
        config = build_run_config(
            project_root=request.project_root,
            feature_paths=request.feature_paths,
            options=RunConfigOptions(
                request.dry_run,
                request.run_all,
                request.max_iterations,
                request.allow_dirty,
                request.verbose_output,
            ),
        )
        loop_run = build_loop_run(
            config,
            enforce_worktree_precondition_fn=self._enforce_worktree_precondition,
            run_selected_feature_iterations_fn=self._run_selected_feature_iterations,
            print_summary_fn=self._runtime_print_summary,
        )
        return run_loop_controller(loop_run)

    @staticmethod
    def _runtime_print_summary(summary: IterationSummaryInputs) -> None:
        runtime_support = import_module("engineeringagent.bootstrap.runtime_support")
        runtime_support.print_summary(summary)

    def _enforce_worktree_precondition(
        self,
        project_root: Path,
        allow_dirty: bool,
    ) -> int | None:
        return enforce_worktree_precondition(
            project_root,
            allow_dirty,
            read_worktree_status=self._read_worktree_status,
        )

    def _read_worktree_status(self, project_root: Path) -> object:
        return self._build_version_control_gateway(project_root).worktree_status(
            project_root,
        )

    def _run_selected_feature_iterations(self, loop_run: LoopRun) -> int:
        return run_selected_feature_iterations(
            loop_run,
            run_feature_iteration=self._run_feature_iteration,
        )

    def _run_feature_iteration(
        self,
        iteration_inputs: FeatureIterationInputs,
    ) -> IterationOutcome:
        result = self._build_feature_iteration_service(
            iteration_inputs.project_root
        ).run(
            FeatureIterationRequest(
                project_root=iteration_inputs.project_root,
                feature_path=iteration_inputs.feature_path,
                run_all=iteration_inputs.run_all,
                attempt=iteration_inputs.attempt,
                feedback=iteration_inputs.feedback,
                verbose_output=iteration_inputs.verbose_output,
            )
        )
        return IterationOutcome.model_validate(result.model_dump())


class _RuntimeModules(SimpleNamespace):
    """Imported runtime modules grouped to keep adapter state compact."""

    checks: Any
    support: Any
    feature_state: Any
    iteration: Any
    models: Any
    phases: Any


class RuntimeFeatureIterationExecutor(FeatureIterationExecutor):
    """Execute feature iterations through the existing loop-runtime pipeline."""

    def __init__(
        self,
        *,
        version_control_gateway: VersionControlGateway,
        progress_journal: ProgressJournal,
    ) -> None:
        self._version_control_gateway = version_control_gateway
        self._progress_journal = progress_journal
        self._runtime = _RuntimeModules(
            checks=import_module("engineeringagent.checks"),
            support=import_module("engineeringagent.bootstrap.runtime_support"),
            feature_state=import_module("engineeringagent.loop_runtime.feature_state"),
            iteration=import_module("engineeringagent.loop_runtime.iteration"),
            models=import_module("engineeringagent.domain.audit.iteration"),
            phases=import_module("engineeringagent.adapters.runtime.iteration_phases"),
        )

    def run(
        self,
        request: FeatureIterationExecutionRequest,
    ) -> FeatureIterationExecutionResult:
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

        report = self._runtime.iteration.run_feature_iteration_pipeline(
            self._runtime.models.FeatureIterationInputs(
                project_root=request.project_root,
                feature_path=request.feature_path,
                run_all=request.run_all,
                attempt=request.attempt,
                feedback=request.feedback,
                verbose_output=request.verbose_output,
            ),
            self._runtime.iteration.IterationPipelineDependencies(
                evaluate_initial_feature_load=(
                    self._runtime.feature_state.evaluate_initial_feature_load
                ),
                ready_for_active_iteration=(
                    self._runtime.feature_state.ready_for_active_iteration
                ),
                touch_active_feature_for_iteration=(
                    self._runtime.feature_state.touch_active_feature_for_iteration
                ),
                run_implement_step=self._runtime.support.run_implement_step,
                refresh_feature_after_implement=(
                    self._runtime.feature_state.refresh_feature_after_implement
                ),
                should_archive_selected_feature=(
                    self._runtime.feature_state.should_archive_selected_feature
                ),
                archive_completed_feature=(
                    self._runtime.feature_state.archive_completed_feature
                ),
                run_gate_phase=self._runtime.phases.run_gate_phase,
                gate_phase_dependencies=self._runtime.phases.GatePhaseDependencies(
                    restore_archived_feature=(
                        self._runtime.feature_state.restore_archived_feature
                    ),
                    collect_changed_paths=self._runtime.checks.collect_changed_paths,
                ),
                run_verification_phase=self._runtime.phases.run_verification_phase,
                run_reviewer_phase=self._runtime.phases.run_reviewer_phase,
                reviewer_phase_dependencies=self._runtime.phases.ReviewerPhaseDependencies(
                    collect_changed_paths=self._runtime.checks.collect_changed_paths,
                    restore_archived_feature=(
                        self._runtime.feature_state.restore_archived_feature
                    ),
                ),
                run_completion_commit_phase=(
                    self._runtime.phases.run_completion_commit_phase
                ),
                completion_phase_dependencies=self._runtime.phases.CompletionPhaseDependencies(
                    commit_feature_completion=_commit_feature_completion,
                    restore_archived_feature=(
                        self._runtime.feature_state.restore_archived_feature
                    ),
                ),
            ),
        )
        observers = build_default_iteration_report_observers(
            DefaultObserverDependencies(
                write_iteration_telemetry=(
                    lambda telemetry_inputs: write_iteration_telemetry(
                        telemetry_inputs,
                        git_head_resolver=self._runtime.support.git_head_short,
                    )
                ),
                persist_iteration_report=_persist_iteration_report,
                git_head_resolver=self._runtime.support.git_head_short,
                print_summary=self._runtime.support.print_summary,
            )
        )
        outcome = publish_iteration_report(report, observers)
        return FeatureIterationExecutionResult(
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
