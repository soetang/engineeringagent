from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, Sequence

from engineeringagent.application import (
    FeatureIterationRequest,
    FeatureIterationResult,
    FeatureIterationService,
    FeatureIterationRuntime,
)
from engineeringagent.domain.audit import ProgressEvent
from engineeringagent.ports import (
    CommitRequest,
    CommitResult,
    DiffSummary,
    WorktreeStatus,
)


def _build_request(**overrides: object) -> FeatureIterationRequest:
    fields: dict[str, object] = {
        "project_root": Path("/tmp/project"),
        "feature_path": Path("docs/specifications/features/FEAT-001/specification.yaml"),
        "run_all": False,
        "attempt": 3,
        "feedback": "fix the failing check",
        "verbose_output": True,
    }
    fields.update(overrides)
    return FeatureIterationRequest.model_validate(fields)


class _FakeFeatureIterationInputs:
    def __init__(self, observed: dict[str, object], **kwargs: object) -> None:
        observed["feature_iteration_inputs"] = kwargs


class _FakeIterationPipelineDependencies:
    def __init__(self, observed: dict[str, object], **kwargs: object) -> None:
        observed["iteration_dependencies"] = kwargs


class _FakeGatePhaseDependencies:
    def __init__(self, observed: dict[str, object], **kwargs: object) -> None:
        observed["gate_dependencies"] = kwargs


class _FakeReviewerPhaseDependencies:
    def __init__(self, observed: dict[str, object], **kwargs: object) -> None:
        observed["reviewer_dependencies"] = kwargs


class _FakeCompletionPhaseDependencies:
    def __init__(self, observed: dict[str, object], **kwargs: object) -> None:
        observed["completion_dependencies"] = kwargs


class _FakeVersionControlGateway:
    def __init__(self, observed: dict[str, object], commit_result: CommitResult) -> None:
        self._observed = observed
        self._commit_result = commit_result

    def diff_against_base(
        self,
        workspace_path: Path,
        *,
        base_ref: str | None = None,
        head_ref: str | None = None,
    ) -> DiffSummary:
        raise AssertionError("unexpected diff_against_base call")

    def head_commit(self, workspace_path: Path) -> str | None:
        raise AssertionError("unexpected head_commit call")

    def worktree_status(self, workspace_path: Path) -> WorktreeStatus:
        raise AssertionError("unexpected worktree_status call")

    def commit(self, request: CommitRequest) -> CommitResult:
        commit_requests = self._observed.setdefault("commit_requests", [])
        assert isinstance(commit_requests, list)
        commit_requests.append(request)
        return self._commit_result


class _FakeProgressJournal:
    def __init__(self, observed: dict[str, object]) -> None:
        self._observed = observed

    def append(self, *, project_root: Path, event: ProgressEvent) -> None:
        raise AssertionError("unexpected append call")

    def append_feature_log(
        self,
        *,
        project_root: Path,
        feature_id: str,
        lines: Sequence[str],
    ) -> None:
        raise AssertionError("unexpected append_feature_log call")

    def write_iteration_report(
        self,
        *,
        project_root: Path,
        feature_id: str,
        payload: dict[str, Any],
    ) -> None:
        iteration_reports = self._observed.setdefault("iteration_reports", [])
        assert isinstance(iteration_reports, list)
        iteration_reports.append(
            {
                "project_root": project_root,
                "feature_id": feature_id,
                "payload": payload,
            }
        )

    def write_handoff(
        self,
        *,
        project_root: Path,
        feature_id: str,
        lines: Sequence[str],
    ) -> None:
        raise AssertionError("unexpected write_handoff call")

    def latest_handoff_path(
        self, *, project_root: Path, feature_id: str
    ) -> Path | None:
        raise AssertionError("unexpected latest_handoff_path call")


def _build_runtime_modules(
    observed: dict[str, object],
    *,
    commit_result: CommitResult,
    publish_outcome: object,
) -> tuple[FeatureIterationRuntime, _FakeVersionControlGateway, _FakeProgressJournal]:
    def _fake_run_feature_iteration_pipeline(inputs: object, dependencies: object) -> str:
        observed["inputs"] = inputs
        observed["dependencies"] = dependencies
        return "iteration-report"

    def _fake_publish_iteration_report(report: str, observers: object) -> object:
        observed["report"] = report
        observed["observers"] = observers
        return publish_outcome

    loop_module = SimpleNamespace(
        run_implement_step=object(),
        git_head_short=object(),
        print_summary=object(),
    )
    changed_paths_module = SimpleNamespace(collect_changed_paths=object())
    feature_state_module = SimpleNamespace(
        evaluate_initial_feature_load=object(),
        ready_for_active_iteration=object(),
        touch_active_feature_for_iteration=object(),
        refresh_feature_after_implement=object(),
        should_archive_selected_feature=object(),
        archive_completed_feature=object(),
        restore_archived_feature=object(),
    )

    def _fake_write_iteration_telemetry(
        telemetry_inputs: object,
        *,
        git_head_resolver: object,
    ) -> None:
        observed["telemetry_call"] = {
            "telemetry_inputs": telemetry_inputs,
            "git_head_resolver": git_head_resolver,
        }

    runtime = FeatureIterationRuntime(
        build_inputs=lambda **kwargs: _FakeFeatureIterationInputs(observed, **kwargs),
        build_iteration_dependencies=lambda **kwargs: _FakeIterationPipelineDependencies(
            observed, **kwargs
        ),
        run_feature_iteration_pipeline=_fake_run_feature_iteration_pipeline,
        build_gate_phase_dependencies=lambda **kwargs: _FakeGatePhaseDependencies(
            observed, **kwargs
        ),
        build_reviewer_phase_dependencies=lambda **kwargs: (
            _FakeReviewerPhaseDependencies(observed, **kwargs)
        ),
        build_completion_phase_dependencies=lambda **kwargs: (
            _FakeCompletionPhaseDependencies(observed, **kwargs)
        ),
        build_default_observer_dependencies=lambda **kwargs: kwargs,
        build_default_iteration_report_observers=lambda dependencies: (
            observed.__setitem__("default_observer_dependencies", dependencies),
            ("observer",),
        )[1],
        publish_iteration_report=_fake_publish_iteration_report,
        write_iteration_telemetry=_fake_write_iteration_telemetry,
        run_implement_step=loop_module.run_implement_step,
        git_head_resolver=loop_module.git_head_short,
        print_summary=loop_module.print_summary,
        evaluate_initial_feature_load=feature_state_module.evaluate_initial_feature_load,
        ready_for_active_iteration=feature_state_module.ready_for_active_iteration,
        touch_active_feature_for_iteration=(
            feature_state_module.touch_active_feature_for_iteration
        ),
        refresh_feature_after_implement=(
            feature_state_module.refresh_feature_after_implement
        ),
        should_archive_selected_feature=(
            feature_state_module.should_archive_selected_feature
        ),
        archive_completed_feature=feature_state_module.archive_completed_feature,
        restore_archived_feature=feature_state_module.restore_archived_feature,
        collect_changed_paths=changed_paths_module.collect_changed_paths,
        run_gate_phase=object(),
        run_verification_phase=object(),
        run_reviewer_phase=object(),
        run_completion_commit_phase=object(),
    )
    version_control_gateway = _FakeVersionControlGateway(observed, commit_result)
    progress_journal = _FakeProgressJournal(observed)
    return (runtime, version_control_gateway, progress_journal)


def test_feature_iteration_service_executes_runtime_pipeline() -> None:
    """The service should build and publish the runtime iteration pipeline."""
    observed: dict[str, object] = {}
    commit_result = CommitResult(
        stdout="commit stdout\n",
        stderr="commit stderr\n",
        commit_created=False,
        commit_sha=None,
        failure_stage="git_commit",
    )
    runtime, version_control_gateway, progress_journal = _build_runtime_modules(
        observed,
        commit_result=commit_result,
        publish_outcome=SimpleNamespace(
            completed=False,
            result="failed",
            failed_gate="tests",
            next_action="retry_same_feature",
            feedback="rerun focused tests",
            log_path=".engineeringagent/progress/FEAT-001/iteration-report.json",
            verification_status="failed:tests",
            verification_failed_command="uv run pytest tests/application",
            reviewer_status="not_run",
            reviewer_decision=None,
            failed_reviewer_id=None,
        ),
    )

    result = FeatureIterationService(
        version_control_gateway=version_control_gateway,
        progress_journal=progress_journal,
        runtime=runtime,
    ).run(_build_request())

    assert result == FeatureIterationResult(
        completed=False,
        result="failed",
        failed_gate="tests",
        next_action="retry_same_feature",
        feedback="rerun focused tests",
        log_path=".engineeringagent/progress/FEAT-001/iteration-report.json",
        verification_status="failed:tests",
        verification_failed_command="uv run pytest tests/application",
        reviewer_status="not_run",
        reviewer_decision=None,
        failed_reviewer_id=None,
    )
    assert observed["feature_iteration_inputs"] == {
        "project_root": Path("/tmp/project"),
        "feature_path": Path(
            "docs/specifications/features/FEAT-001/specification.yaml"
        ),
        "run_all": False,
        "attempt": 3,
        "feedback": "fix the failing check",
        "verbose_output": True,
    }
    assert observed["report"] == "iteration-report"
    assert observed["gate_dependencies"] == {
        "restore_archived_feature": runtime.restore_archived_feature,
        "collect_changed_paths": runtime.collect_changed_paths,
    }
    assert observed["reviewer_dependencies"] == {
        "collect_changed_paths": runtime.collect_changed_paths,
        "restore_archived_feature": runtime.restore_archived_feature,
    }
    completion_dependencies = observed["completion_dependencies"]
    assert isinstance(completion_dependencies, dict)
    commit_outcome = completion_dependencies["commit_feature_completion"](
        Path("/tmp/project"),
        {"expected_commit_subject": "feat: complete FEAT-001"},
    )
    assert commit_outcome == (False, "git_commit", "commit stdout\ncommit stderr\n")
    assert observed["commit_requests"] == [
        CommitRequest(
            workspace_path=Path("/tmp/project"),
            message="feat: complete FEAT-001",
            stage_all=True,
            allow_empty=False,
        )
    ]
    observer_dependencies = observed["default_observer_dependencies"]
    assert isinstance(observer_dependencies, dict)
    observer_dependencies["write_iteration_telemetry"](
        "telemetry-inputs",
        runtime.git_head_resolver,
    )
    assert observed["telemetry_call"] == {
        "telemetry_inputs": "telemetry-inputs",
        "git_head_resolver": runtime.git_head_resolver,
    }
    observer_dependencies["persist_iteration_report"](
        SimpleNamespace(
            telemetry_inputs=SimpleNamespace(
                iteration_inputs=SimpleNamespace(project_root=Path("/tmp/project"))
            ),
            feature_id="FEAT-001",
            model_dump=lambda mode="json": {"result": "failed", "mode": mode},
        )
    )
    assert observed["iteration_reports"] == [
        {
            "project_root": Path("/tmp/project"),
            "feature_id": "FEAT-001",
            "payload": {"result": "failed", "mode": "json"},
        }
    ]


def test_feature_iteration_service_commit_completion_reports_success() -> None:
    """Successful completion commits should return the passing tuple shape."""
    observed: dict[str, object] = {}
    runtime, version_control_gateway, progress_journal = _build_runtime_modules(
        observed,
        commit_result=CommitResult(
            stdout="ok\n",
            stderr="",
            commit_created=True,
            commit_sha="abc1234",
            failure_stage=None,
        ),
        publish_outcome=SimpleNamespace(
            completed=True,
            result="passed",
            failed_gate=None,
            next_action="select_next_feature",
            feedback=None,
            log_path=None,
            verification_status="passed",
            verification_failed_command=None,
            reviewer_status="passed",
            reviewer_decision="approved",
            failed_reviewer_id=None,
        ),
    )

    FeatureIterationService(
        version_control_gateway=version_control_gateway,
        progress_journal=progress_journal,
        runtime=runtime,
    ).run(_build_request())

    completion_dependencies = observed["completion_dependencies"]
    assert isinstance(completion_dependencies, dict)
    assert completion_dependencies["commit_feature_completion"](
        Path("/tmp/project"),
        {"expected_commit_subject": "feat: complete FEAT-001"},
    ) == (True, None, "ok\n")
