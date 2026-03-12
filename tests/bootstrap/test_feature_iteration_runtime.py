from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

from engineeringagent.application.feature_iteration import (
    FeatureIterationRuntimeDependencies,
    IterationReport,
)
from engineeringagent.bootstrap.feature_iteration_runtime import (
    _build_iteration_pipeline_dependencies,
    _build_iteration_report_observers,
    _commit_feature_completion,
    _persist_iteration_report,
)
from engineeringagent.bootstrap.iteration_reporting import DefaultObserverDependencies
from engineeringagent.ports import CommitRequest, CommitResult

from tests.application.test_feature_iteration_service import (
    _FakeClock,
    _FakeCompletionPhaseDependencies,
    _FakeGatePhaseDependencies,
    _FakeProgressJournal,
    _FakeReviewerPhaseDependencies,
    _FakeVersionControlGateway,
)


def _build_runtime_dependencies(
    observed: dict[str, object],
) -> FeatureIterationRuntimeDependencies:
    def _fake_write_iteration_telemetry(
        telemetry_inputs: object,
        **kwargs: object,
    ) -> str:
        observed["telemetry_call"] = {
            "telemetry_inputs": telemetry_inputs,
            **kwargs,
        }
        return "progress/run-feature-FEAT-001.txt"

    def _fake_observer_dependencies_type(**kwargs: object) -> DefaultObserverDependencies:
        dependencies = DefaultObserverDependencies.model_validate(kwargs)
        observed["default_observer_dependencies"] = dependencies
        return dependencies

    return FeatureIterationRuntimeDependencies(
        clock=_FakeClock(),
        evaluate_initial_feature_load=lambda _feature_path: None,
        describe_action=lambda project_root, action, structured: (
            f"{project_root}:{action}:{structured}"
        ),
        ready_for_active_iteration=lambda _result, _feature: True,
        touch_active_feature_for_iteration=lambda _feature, _path: None,
        run_implement_step=lambda *args, **kwargs: None,
        refresh_feature_after_implement=lambda _project_root, _feature_path: None,
        should_archive_selected_feature=lambda _result, _feature: False,
        archive_completed_feature=lambda _project_root, _feature_path: (False, None, None),
        collect_changed_paths=lambda _project_root: None,
        restore_archived_feature=lambda _archived_path, _feature_path: (True, None),
        run_feature_iteration_pipeline=lambda inputs, dependencies: "iteration-report",
        run_gate_phase=lambda *args, **kwargs: None,
        build_gate_phase_dependencies=lambda **kwargs: _FakeGatePhaseDependencies(
            observed, **kwargs
        ),
        run_verification_phase=lambda *args, **kwargs: None,
        run_reviewer_phase=lambda *args, **kwargs: None,
        build_reviewer_phase_dependencies=lambda **kwargs: _FakeReviewerPhaseDependencies(
            observed, **kwargs
        ),
        run_completion_commit_phase=lambda *args, **kwargs: None,
        build_completion_phase_dependencies=lambda **kwargs: _FakeCompletionPhaseDependencies(
            observed, **kwargs
        ),
        git_head_short=lambda _project_root: "abc1234",
        print_summary=lambda _summary: None,
        observer_dependencies_type=_fake_observer_dependencies_type,
        write_iteration_telemetry=_fake_write_iteration_telemetry,
        build_iteration_pipeline_dependencies=_build_iteration_pipeline_dependencies,
        build_iteration_report_observers=_build_iteration_report_observers,
        publish_iteration_report=lambda report, _observers: report,
    )


def test_commit_feature_completion_returns_failure_tuple_shape() -> None:
    """Bootstrap commit wiring should preserve the pipeline callback contract."""
    observed: dict[str, object] = {}
    gateway = _FakeVersionControlGateway(
        observed,
        CommitResult(
            stdout="commit stdout\n",
            stderr="commit stderr\n",
            commit_created=False,
            commit_sha=None,
            failure_stage="git_commit",
        ),
    )

    outcome = _commit_feature_completion(
        gateway,
        project_root=Path("/tmp/project"),
        feature={"expected_commit_subject": "feat: complete FEAT-001"},
    )

    assert outcome == (False, "git_commit", "commit stdout\ncommit stderr\n")
    assert observed["commit_requests"] == [
        CommitRequest(
            workspace_path=Path("/tmp/project"),
            message="feat: complete FEAT-001",
            stage_all=True,
            allow_empty=False,
        )
    ]


def test_persist_iteration_report_writes_json_payload_to_journal() -> None:
    """Bootstrap report persistence should stay on the journal port boundary."""
    observed: dict[str, object] = {}
    journal = _FakeProgressJournal(observed)
    report = cast(
        IterationReport,
        SimpleNamespace(
            telemetry_inputs=SimpleNamespace(
                iteration_inputs=SimpleNamespace(project_root=Path("/tmp/project"))
            ),
            feature_id="FEAT-001",
            model_dump=lambda mode="json": {"result": "failed", "mode": mode},
        ),
    )

    _persist_iteration_report(journal, report)

    assert observed["iteration_reports"] == [
        {
            "project_root": Path("/tmp/project"),
            "feature_id": "FEAT-001",
            "payload": {"result": "failed", "mode": "json"},
        }
    ]


def test_build_iteration_pipeline_dependencies_wires_completion_commit() -> None:
    """Bootstrap should assemble the pipeline dependency bundle with commit wiring."""
    observed: dict[str, object] = {}
    runtime_dependencies = _build_runtime_dependencies(observed)
    gateway = _FakeVersionControlGateway(
        observed,
        CommitResult(
            stdout="ok\n",
            stderr="",
            commit_created=True,
            commit_sha="abc1234",
            failure_stage=None,
        ),
    )

    dependencies = _build_iteration_pipeline_dependencies(runtime_dependencies, gateway)

    assert dependencies.describe_action is runtime_dependencies.describe_action
    assert dependencies.run_implement_step is runtime_dependencies.run_implement_step
    completion_dependencies = dependencies.completion_phase_dependencies
    assert isinstance(completion_dependencies, _FakeCompletionPhaseDependencies)
    recorded_completion_dependencies = observed["completion_dependencies"]
    assert isinstance(recorded_completion_dependencies, dict)
    assert recorded_completion_dependencies["commit_feature_completion"](
        Path("/tmp/project"),
        {"expected_commit_subject": "feat: complete FEAT-001"},
    ) == (True, None, "ok\n")
    assert observed["commit_requests"] == [
        CommitRequest(
            workspace_path=Path("/tmp/project"),
            message="feat: complete FEAT-001",
            stage_all=True,
            allow_empty=False,
        )
    ]


def test_build_iteration_report_observers_uses_runtime_and_journal_dependencies() -> None:
    """Bootstrap should assemble default observers from runtime and journal seams."""
    observed: dict[str, object] = {}
    runtime_dependencies = _build_runtime_dependencies(observed)
    journal = _FakeProgressJournal(observed)

    _build_iteration_report_observers(runtime_dependencies, journal)

    observer_dependencies = cast(
        DefaultObserverDependencies,
        observed["default_observer_dependencies"],
    )
    assert observer_dependencies.git_head_resolver is runtime_dependencies.git_head_short
    assert observer_dependencies.print_summary is runtime_dependencies.print_summary
    observer_dependencies.write_iteration_telemetry(cast(Any, "telemetry-inputs"))
    observer_dependencies.persist_iteration_report(
        cast(
            Any,
            SimpleNamespace(
                telemetry_inputs=SimpleNamespace(
                    iteration_inputs=SimpleNamespace(project_root=Path("/tmp/project"))
                ),
                feature_id="FEAT-001",
                model_dump=lambda mode="json": {"result": "failed", "mode": mode},
            ),
        )
    )
    assert observed["telemetry_call"] == {
        "telemetry_inputs": "telemetry-inputs",
        "git_head_resolver": runtime_dependencies.git_head_short,
    }
    assert observed["iteration_reports"] == [
        {
            "project_root": Path("/tmp/project"),
            "feature_id": "FEAT-001",
            "payload": {"result": "failed", "mode": "json"},
        }
    ]
