"""Application service for feature-iteration execution requests."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from engineeringagent.application.contracts import (
    FeatureIterationRequest,
    FeatureIterationResult,
    FeatureIterationRuntime,
)
from engineeringagent.domain.specification import feature_completion_commit_subject
from engineeringagent.ports import CommitRequest, ProgressJournal, VersionControlGateway


class FeatureIterationService:
    """Own feature-iteration requests behind a stable application contract."""

    def __init__(
        self,
        *,
        version_control_gateway: VersionControlGateway,
        progress_journal: ProgressJournal,
        runtime: FeatureIterationRuntime,
    ) -> None:
        self._version_control_gateway = version_control_gateway
        self._progress_journal = progress_journal
        self._runtime = runtime

    def run(self, request: FeatureIterationRequest) -> FeatureIterationResult:
        """Execute one feature iteration through the injected runtime boundary."""
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

        report = self._runtime.run_feature_iteration_pipeline(
            self._runtime.build_inputs(
                project_root=request.project_root,
                feature_path=request.feature_path,
                run_all=request.run_all,
                attempt=request.attempt,
                feedback=request.feedback,
                verbose_output=request.verbose_output,
            ),
            self._runtime.build_iteration_dependencies(
                evaluate_initial_feature_load=(
                    self._runtime.evaluate_initial_feature_load
                ),
                ready_for_active_iteration=self._runtime.ready_for_active_iteration,
                touch_active_feature_for_iteration=(
                    self._runtime.touch_active_feature_for_iteration
                ),
                run_implement_step=self._runtime.run_implement_step,
                refresh_feature_after_implement=(
                    self._runtime.refresh_feature_after_implement
                ),
                should_archive_selected_feature=(
                    self._runtime.should_archive_selected_feature
                ),
                archive_completed_feature=self._runtime.archive_completed_feature,
                run_gate_phase=self._runtime.run_gate_phase,
                gate_phase_dependencies=self._runtime.build_gate_phase_dependencies(
                    restore_archived_feature=self._runtime.restore_archived_feature,
                    collect_changed_paths=self._runtime.collect_changed_paths,
                ),
                run_verification_phase=self._runtime.run_verification_phase,
                run_reviewer_phase=self._runtime.run_reviewer_phase,
                reviewer_phase_dependencies=(
                    self._runtime.build_reviewer_phase_dependencies(
                        collect_changed_paths=self._runtime.collect_changed_paths,
                        restore_archived_feature=self._runtime.restore_archived_feature,
                    )
                ),
                run_completion_commit_phase=self._runtime.run_completion_commit_phase,
                completion_phase_dependencies=(
                    self._runtime.build_completion_phase_dependencies(
                        commit_feature_completion=_commit_feature_completion,
                        restore_archived_feature=self._runtime.restore_archived_feature,
                    )
                ),
            ),
        )
        observers = self._runtime.build_default_iteration_report_observers(
            self._runtime.build_default_observer_dependencies(
                write_iteration_telemetry=(
                    lambda telemetry_inputs, git_head_resolver: (
                        self._runtime.write_iteration_telemetry(
                            telemetry_inputs,
                            git_head_resolver=git_head_resolver,
                        )
                    )
                ),
                persist_iteration_report=_persist_iteration_report,
                git_head_resolver=self._runtime.git_head_resolver,
                print_summary=self._runtime.print_summary,
            )
        )
        outcome = self._runtime.publish_iteration_report(
            report,
            observers,
        )
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
