"""Adapter that delegates feature-iteration execution to current runtime modules."""

from __future__ import annotations

from importlib import import_module
from pathlib import Path
from typing import Any

from engineeringagent.domain.specification import feature_completion_commit_subject
from engineeringagent.ports import (
    CommitRequest,
    FeatureIterationExecutionRequest,
    FeatureIterationExecutionResult,
)


class RuntimeFeatureIterationExecutor:
    """Execute feature-iteration requests through the current runtime pipeline."""

    @staticmethod
    def _app_factory(project_root: Path) -> Any:
        """Resolve `AppFactory` lazily to avoid bootstrap import cycles."""
        app_factory_module = import_module("engineeringagent.bootstrap.app_factory")
        return app_factory_module.AppFactory(project_root)

    def run(
        self,
        request: FeatureIterationExecutionRequest,
    ) -> FeatureIterationExecutionResult:
        """Build runtime inputs and execute the current iteration pipeline."""
        loop_module = import_module("engineeringagent.loop")
        changed_paths_module = import_module("engineeringagent.changed_paths")
        feature_state_module = import_module("engineeringagent.loop_runtime.feature_state")
        models_module = import_module("engineeringagent.loop_runtime.models")
        observers_module = import_module("engineeringagent.loop_runtime.observers")
        telemetry_module = import_module("engineeringagent.loop_runtime.telemetry")
        iteration_module = import_module("engineeringagent.loop_runtime.iteration")
        phases_module = import_module("engineeringagent.loop_runtime.phases")

        def _commit_feature_completion(
            project_root: Path,
            feature: dict[str, Any],
        ) -> tuple[bool, str | None, str]:
            message = feature_completion_commit_subject(feature)
            commit_result = self._app_factory(project_root).build_version_control_gateway().commit(
                CommitRequest(
                    project_root=project_root,
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
            self._app_factory(
                report.telemetry_inputs.iteration_inputs.project_root
            ).build_progress_journal().write_iteration_report(
                project_root=report.telemetry_inputs.iteration_inputs.project_root,
                feature_id=report.feature_id,
                payload=report.model_dump(mode="json"),
            )

        report = iteration_module.run_feature_iteration_pipeline(
            models_module.FeatureIterationInputs(
                project_root=request.project_root,
                feature_path=request.feature_path,
                run_all=request.run_all,
                attempt=request.attempt,
                feedback=request.feedback,
                verbose_output=request.verbose_output,
            ),
            iteration_module.IterationPipelineDependencies(
                evaluate_initial_feature_load=(
                    feature_state_module.evaluate_initial_feature_load
                ),
                ready_for_active_iteration=feature_state_module.ready_for_active_iteration,
                touch_active_feature_for_iteration=(
                    feature_state_module.touch_active_feature_for_iteration
                ),
                run_implement_step=loop_module.run_implement_step,
                refresh_feature_after_implement=(
                    feature_state_module.refresh_feature_after_implement
                ),
                should_archive_selected_feature=(
                    feature_state_module.should_archive_selected_feature
                ),
                archive_completed_feature=feature_state_module.archive_completed_feature,
                run_gate_phase=phases_module.run_gate_phase,
                gate_phase_dependencies=phases_module.GatePhaseDependencies(
                    restore_archived_feature=feature_state_module.restore_archived_feature,
                    collect_changed_paths=changed_paths_module.collect_changed_paths,
                ),
                run_verification_phase=phases_module.run_verification_phase,
                run_reviewer_phase=phases_module.run_reviewer_phase,
                reviewer_phase_dependencies=phases_module.ReviewerPhaseDependencies(
                    collect_changed_paths=changed_paths_module.collect_changed_paths,
                    restore_archived_feature=feature_state_module.restore_archived_feature,
                ),
                run_completion_commit_phase=phases_module.run_completion_commit_phase,
                completion_phase_dependencies=(
                    phases_module.CompletionPhaseDependencies(
                        commit_feature_completion=_commit_feature_completion,
                        restore_archived_feature=feature_state_module.restore_archived_feature,
                    )
                ),
            ),
        )
        observers = observers_module.build_default_iteration_report_observers(
            observers_module.DefaultObserverDependencies(
                write_iteration_telemetry=(
                    lambda telemetry_inputs, git_head_resolver: (
                        telemetry_module.write_iteration_telemetry(
                            telemetry_inputs,
                            git_head_resolver=git_head_resolver,
                        )
                    )
                ),
                persist_iteration_report=_persist_iteration_report,
                git_head_resolver=loop_module.git_head_short,
                print_summary=loop_module.print_summary,
            )
        )
        outcome = observers_module.publish_iteration_report(
            report,
            observers,
        )
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
