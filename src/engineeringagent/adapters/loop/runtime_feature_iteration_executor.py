"""Feature-iteration adapter backed by the legacy loop runtime modules."""

from __future__ import annotations

from importlib import import_module
from types import SimpleNamespace
from typing import Any

from engineeringagent.domain.specification import feature_completion_commit_subject
from engineeringagent.ports import (
    CommitRequest,
    FeatureIterationExecutionRequest,
    FeatureIterationExecutionResult,
    FeatureIterationExecutor,
    ProgressJournal,
    VersionControlGateway,
)


class _RuntimeModules(SimpleNamespace):
    """Imported runtime modules grouped to keep adapter state compact."""

    checks: Any
    loop: Any
    feature_state: Any
    iteration: Any
    models: Any
    observers: Any
    phases: Any
    telemetry: Any


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
            loop=import_module("engineeringagent.loop"),
            feature_state=import_module("engineeringagent.loop_runtime.feature_state"),
            iteration=import_module("engineeringagent.loop_runtime.iteration"),
            models=import_module("engineeringagent.loop_runtime.models"),
            observers=import_module("engineeringagent.loop_runtime.observers"),
            phases=import_module("engineeringagent.loop_runtime.phases"),
            telemetry=import_module("engineeringagent.loop_runtime.telemetry"),
        )

    def run(
        self,
        request: FeatureIterationExecutionRequest,
    ) -> FeatureIterationExecutionResult:
        """Execute one feature iteration through the runtime pipeline."""

        def _commit_feature_completion(
            project_root,
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
                run_implement_step=self._runtime.loop.run_implement_step,
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
        observers = self._runtime.observers.build_default_iteration_report_observers(
            self._runtime.observers.DefaultObserverDependencies(
                write_iteration_telemetry=(
                    lambda telemetry_inputs, git_head_resolver: (
                        self._runtime.telemetry.write_iteration_telemetry(
                            telemetry_inputs,
                            git_head_resolver=git_head_resolver,
                        )
                    )
                ),
                persist_iteration_report=_persist_iteration_report,
                git_head_resolver=self._runtime.loop.git_head_short,
                print_summary=self._runtime.loop.print_summary,
            )
        )
        outcome = self._runtime.observers.publish_iteration_report(report, observers)
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
