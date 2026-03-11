from __future__ import annotations

# pyright: reportAttributeAccessIssue=false

from pathlib import Path
from types import SimpleNamespace

from engineeringagent.adapters.loop import RuntimeFeatureIterationExecutor
from engineeringagent.ports import (
    CommitRequest,
    FeatureIterationExecutionRequest,
    FeatureIterationExecutionResult,
)


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


def _fake_import_module(
    modules: SimpleNamespace,
):
    mapping = {
        "engineeringagent.loop": modules.loop,
        "engineeringagent.checks": modules.changed_paths,
        "engineeringagent.loop_runtime.feature_state": modules.feature_state,
        "engineeringagent.loop_runtime.models": modules.models,
        "engineeringagent.loop_runtime.observers": modules.observers,
        "engineeringagent.loop_runtime.telemetry": modules.telemetry,
        "engineeringagent.loop_runtime.iteration": modules.iteration,
        "engineeringagent.loop_runtime.phases": modules.phases,
        "engineeringagent.bootstrap.app_factory": modules.app_factory,
    }

    def _import(name: str) -> SimpleNamespace:
        try:
            return mapping[name]
        except KeyError as exc:
            raise AssertionError(f"unexpected module import: {name}") from exc

    return _import


def test_runtime_feature_iteration_executor_builds_runtime_pipeline(
    monkeypatch,
) -> None:
    """The adapter should translate the port request into runtime pipeline calls."""
    observed: dict[str, object] = {}

    def _fake_run_feature_iteration_pipeline(inputs: object, dependencies: object) -> str:
        observed["inputs"] = inputs
        observed["dependencies"] = dependencies
        return "iteration-report"

    def _fake_publish_iteration_report(report: str, observers: object) -> object:
        observed["report"] = report
        observed["observers"] = observers
        return SimpleNamespace(
            completed=True,
            result="passed",
            failed_gate=None,
            next_action="select_next_feature",
            feedback=None,
            log_path=".engineeringagent/progress/FEAT-001/iteration-report.json",
            verification_status="passed",
            verification_failed_command=None,
            reviewer_status="passed",
            reviewer_decision="approved",
            failed_reviewer_id=None,
        )

    loop_module = SimpleNamespace(
        run_implement_step=object(),
        git_head_short=object(),
        print_summary=object(),
    )
    commit_result = SimpleNamespace(
        stdout="commit stdout\n",
        stderr="commit stderr\n",
        commit_created=False,
        failure_stage="git_commit",
    )
    observed["commit_result"] = commit_result
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
    models_module = SimpleNamespace(
        FeatureIterationInputs=lambda **kwargs: _FakeFeatureIterationInputs(
            observed, **kwargs
        )
    )
    observers_module = SimpleNamespace(
        publish_iteration_report=_fake_publish_iteration_report,
        build_default_iteration_report_observers=lambda dependencies: (
            observed.__setitem__("default_observer_dependencies", dependencies),
            ("observer",),
        )[1],
        DefaultObserverDependencies=lambda **kwargs: kwargs,
    )
    telemetry_module = SimpleNamespace(write_iteration_telemetry=object())
    iteration_module = SimpleNamespace(
        run_feature_iteration_pipeline=_fake_run_feature_iteration_pipeline,
        IterationPipelineDependencies=lambda **kwargs: _FakeIterationPipelineDependencies(
            observed, **kwargs
        ),
    )
    phases_module = SimpleNamespace(
        run_gate_phase=object(),
        run_verification_phase=object(),
        run_reviewer_phase=object(),
        run_completion_commit_phase=object(),
        GatePhaseDependencies=lambda **kwargs: _FakeGatePhaseDependencies(
            observed, **kwargs
        ),
        ReviewerPhaseDependencies=lambda **kwargs: _FakeReviewerPhaseDependencies(
            observed, **kwargs
        ),
        CompletionPhaseDependencies=lambda **kwargs: _FakeCompletionPhaseDependencies(
            observed, **kwargs
        ),
    )
    app_factory_module = SimpleNamespace(
        AppFactory=lambda project_root: SimpleNamespace(
            project_root=project_root,
            build_version_control_gateway=lambda: SimpleNamespace(
                commit=lambda request: observed.setdefault("commit_requests", []).append(
                    request
                )
                or commit_result
            ),
            build_progress_journal=lambda: SimpleNamespace(
                write_iteration_report=lambda **kwargs: observed.setdefault(
                    "iteration_reports", []
                ).append(kwargs)
            ),
        )
    )

    monkeypatch.setattr(
        "engineeringagent.adapters.loop.runtime_feature_iteration_executor.import_module",
        _fake_import_module(
            SimpleNamespace(
                loop=loop_module,
                changed_paths=changed_paths_module,
                feature_state=feature_state_module,
                models=models_module,
                observers=observers_module,
                telemetry=telemetry_module,
                iteration=iteration_module,
                phases=phases_module,
                app_factory=app_factory_module,
            )
        ),
    )

    request = FeatureIterationExecutionRequest(
        project_root=Path("/tmp/project"),
        feature_path=Path("docs/spec/features/FEAT-001/spec.yaml"),
        run_all=True,
        attempt=4,
        feedback="keep going",
        verbose_output=False,
    )

    result = RuntimeFeatureIterationExecutor().run(request)

    assert result == FeatureIterationExecutionResult(
        completed=True,
        result="passed",
        failed_gate=None,
        next_action="select_next_feature",
        feedback=None,
        log_path=".engineeringagent/progress/FEAT-001/iteration-report.json",
        verification_status="passed",
        verification_failed_command=None,
        reviewer_status="passed",
        reviewer_decision="approved",
        failed_reviewer_id=None,
    )
    assert observed["feature_iteration_inputs"] == {
        "project_root": Path("/tmp/project"),
        "feature_path": Path("docs/spec/features/FEAT-001/spec.yaml"),
        "run_all": True,
        "attempt": 4,
        "feedback": "keep going",
        "verbose_output": False,
    }
    assert observed["report"] == "iteration-report"
    assert observed["gate_dependencies"] == {
        "restore_archived_feature": feature_state_module.restore_archived_feature,
        "collect_changed_paths": changed_paths_module.collect_changed_paths,
    }
    assert observed["reviewer_dependencies"] == {
        "collect_changed_paths": changed_paths_module.collect_changed_paths,
        "restore_archived_feature": feature_state_module.restore_archived_feature,
    }
    completion_dependencies = observed["completion_dependencies"]
    assert isinstance(completion_dependencies, dict)
    assert callable(completion_dependencies["commit_feature_completion"])
    assert (
        completion_dependencies["restore_archived_feature"]
        is feature_state_module.restore_archived_feature
    )
    assert observed["observers"] == ("observer",)
    observer_dependencies = observed["default_observer_dependencies"]
    assert isinstance(observer_dependencies, dict)
    assert callable(observer_dependencies["write_iteration_telemetry"])
    assert callable(observer_dependencies["persist_iteration_report"])
    assert observer_dependencies["git_head_resolver"] is loop_module.git_head_short
    assert observer_dependencies["print_summary"] is loop_module.print_summary

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

    observer_dependencies["persist_iteration_report"](
        SimpleNamespace(
            telemetry_inputs=SimpleNamespace(
                iteration_inputs=SimpleNamespace(project_root=Path("/tmp/project"))
            ),
            feature_id="FEAT-001",
            model_dump=lambda mode="json": {"result": "passed", "mode": mode},
        )
    )
    assert observed["iteration_reports"] == [
        {
            "project_root": Path("/tmp/project"),
            "feature_id": "FEAT-001",
            "payload": {"result": "passed", "mode": "json"},
        }
    ]
