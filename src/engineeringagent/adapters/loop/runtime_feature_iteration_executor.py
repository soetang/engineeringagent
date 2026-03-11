"""Feature-iteration adapter backed by the legacy loop runtime modules."""

from __future__ import annotations

from importlib import import_module
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
        self._checks_module = import_module("engineeringagent.checks")
        self._loop_module = import_module("engineeringagent.loop")
        self._feature_state = import_module("engineeringagent.loop_runtime.feature_state")
        self._iteration = import_module("engineeringagent.loop_runtime.iteration")
        self._models = import_module("engineeringagent.loop_runtime.models")
        self._observers = import_module("engineeringagent.loop_runtime.observers")
        self._phases = import_module("engineeringagent.loop_runtime.phases")
        self._telemetry = import_module("engineeringagent.loop_runtime.telemetry")

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

        report = self._iteration.run_feature_iteration_pipeline(
            self._models.FeatureIterationInputs(
                project_root=request.project_root,
                feature_path=request.feature_path,
                run_all=request.run_all,
                attempt=request.attempt,
                feedback=request.feedback,
                verbose_output=request.verbose_output,
            ),
            self._iteration.IterationPipelineDependencies(
                evaluate_initial_feature_load=(
                    self._feature_state.evaluate_initial_feature_load
                ),
                ready_for_active_iteration=self._feature_state.ready_for_active_iteration,
                touch_active_feature_for_iteration=(
                    self._feature_state.touch_active_feature_for_iteration
                ),
                run_implement_step=self._loop_module.run_implement_step,
                refresh_feature_after_implement=(
                    self._feature_state.refresh_feature_after_implement
                ),
                should_archive_selected_feature=(
                    self._feature_state.should_archive_selected_feature
                ),
                archive_completed_feature=self._feature_state.archive_completed_feature,
                run_gate_phase=self._phases.run_gate_phase,
                gate_phase_dependencies=self._phases.GatePhaseDependencies(
                    restore_archived_feature=self._feature_state.restore_archived_feature,
                    collect_changed_paths=self._checks_module.collect_changed_paths,
                ),
                run_verification_phase=self._phases.run_verification_phase,
                run_reviewer_phase=self._phases.run_reviewer_phase,
                reviewer_phase_dependencies=self._phases.ReviewerPhaseDependencies(
                    collect_changed_paths=self._checks_module.collect_changed_paths,
                    restore_archived_feature=self._feature_state.restore_archived_feature,
                ),
                run_completion_commit_phase=self._phases.run_completion_commit_phase,
                completion_phase_dependencies=self._phases.CompletionPhaseDependencies(
                    commit_feature_completion=_commit_feature_completion,
                    restore_archived_feature=self._feature_state.restore_archived_feature,
                ),
            ),
        )
        observers = self._observers.build_default_iteration_report_observers(
            self._observers.DefaultObserverDependencies(
                write_iteration_telemetry=(
                    lambda telemetry_inputs, git_head_resolver: (
                        self._telemetry.write_iteration_telemetry(
                            telemetry_inputs,
                            git_head_resolver=git_head_resolver,
                        )
                    )
                ),
                persist_iteration_report=_persist_iteration_report,
                git_head_resolver=self._loop_module.git_head_short,
                print_summary=self._loop_module.print_summary,
            )
        )
        outcome = self._observers.publish_iteration_report(report, observers)
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
