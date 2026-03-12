from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import cast

from engineeringagent.adapters.agents import ConfiguredAgentRunner
from engineeringagent.adapters.clock import SystemClock
from engineeringagent.adapters.config import FilesystemConfigurationProvider
from engineeringagent.adapters.documents import (
    ChecksCatalogLoadOptions,
    FilesystemChecksCatalogRepository,
)
from engineeringagent.adapters.progress import FilesystemProgressJournal
from engineeringagent.adapters.prompts import FilesystemPromptDefinitionRepository
from engineeringagent.adapters.quality.validation import (
    QualityRepositoryValidator,
)
from engineeringagent.adapters.quality.runtime import RuntimeChecksRunner
from engineeringagent.adapters.runtime import (
    RuntimeFeatureIterationDependencies,
    RuntimeFeatureIterationWorkflow,
    RuntimeRunLoopExecutor,
)
from engineeringagent.adapters.runtime.feature_iteration_workflow import (
    build_iteration_pipeline_dependencies,
)
from engineeringagent.adapters.vcs import (
    GitCliVersionControlGateway,
    GitFeatureWorkspaceManager,
)
from engineeringagent.application import (
    ChecksService,
    FeatureIterationService,
    GuidanceService,
    InitWorkspaceService,
    PromptBuilder,
    RunLoopService,
    ValidationService,
    WorkspaceRecoveryService,
)
from engineeringagent.application.feature_iteration_runtime import (
    FeatureIterationInputs,
    IterationReport,
    IterationTelemetryInputs,
)
from engineeringagent.bootstrap import AppFactory
import engineeringagent.bootstrap.app_factory as app_factory_module
from engineeringagent.bootstrap.app_factory import (
    _build_iteration_report_publisher,
    _persist_iteration_report,
)
from engineeringagent.bootstrap.iteration_reporting import DefaultIterationReportPublisher
from engineeringagent.ports import CommitRequest, CommitResult
from engineeringagent.ports import ConfigurationProvider

from tests.application.test_feature_iteration_service import (
    _FakeClock,
    _FakeCompletionPhaseDependencies,
    _FakeGatePhaseDependencies,
    _FakeProgressJournal,
    _FakeReviewerPhaseDependencies,
    _FakeVersionControlGateway,
)


def test_app_factory_resolves_project_root() -> None:
    """Factory root resolution is absolute and deterministic."""
    factory = AppFactory(Path("."))

    assert factory.project_root == Path(".").resolve()


def test_app_factory_builds_default_application_services(tmp_path: Path) -> None:
    """Factory wires the concrete default services used by the CLI."""
    factory = AppFactory(tmp_path)
    checks_service = factory.build_checks_service()
    feature_iteration_service = factory.build_feature_iteration_service()
    run_loop_service = factory.build_run_loop_service()

    assert isinstance(checks_service, ChecksService)
    assert isinstance(feature_iteration_service, FeatureIterationService)
    assert isinstance(run_loop_service, RunLoopService)
    assert isinstance(checks_service._checks_runner, RuntimeChecksRunner)
    assert isinstance(feature_iteration_service._workflow.__self__, RuntimeFeatureIterationWorkflow)
    assert isinstance(
        feature_iteration_service._workflow.__self__._runtime_dependencies,
        RuntimeFeatureIterationDependencies,
    )
    assert isinstance(
        feature_iteration_service._workflow.__self__._version_control_gateway,
        GitCliVersionControlGateway,
    )
    assert isinstance(
        feature_iteration_service._workflow.__self__._iteration_report_publisher,
        DefaultIterationReportPublisher,
    )
    assert isinstance(
        checks_service._checks_catalog_repository,
        FilesystemChecksCatalogRepository,
    )
    assert isinstance(
        run_loop_service._checks_catalog_repository,
        FilesystemChecksCatalogRepository,
    )
    assert isinstance(run_loop_service._executor, RuntimeRunLoopExecutor)
    assert (
        run_loop_service._checks_catalog_repository._options
        == ChecksCatalogLoadOptions(
            error_prefix="run config error",
            missing_context=" (required for --all)",
        )
    )
    assert isinstance(factory.build_guidance_service(), GuidanceService)
    validation_service = factory.build_validation_service()
    assert isinstance(validation_service, ValidationService)
    assert isinstance(validation_service._validator, QualityRepositoryValidator)
    assert isinstance(factory.build_init_workspace_service(), InitWorkspaceService)
    assert isinstance(factory.build_progress_journal(), FilesystemProgressJournal)
    assert isinstance(factory.build_agent_runner(), ConfiguredAgentRunner)
    assert isinstance(factory.build_clock(), SystemClock)
    configuration_provider = factory.build_configuration_provider()
    assert isinstance(configuration_provider, FilesystemConfigurationProvider)
    assert isinstance(configuration_provider, ConfigurationProvider)
    assert isinstance(
        factory.build_version_control_gateway(),
        GitCliVersionControlGateway,
    )
    assert isinstance(
        factory.build_prompt_definition_repository(),
        FilesystemPromptDefinitionRepository,
    )
    assert isinstance(factory.build_prompt_builder(), PromptBuilder)
    assert isinstance(
        feature_iteration_service._workflow.__self__._runtime_dependencies.clock,
        SystemClock,
    )
    recovery_service = factory.build_workspace_recovery_service()
    assert isinstance(recovery_service, WorkspaceRecoveryService)
    assert isinstance(recovery_service._workspace_manager, GitFeatureWorkspaceManager)
    assert isinstance(recovery_service._progress_journal, FilesystemProgressJournal)
    assert isinstance(
        factory.build_feature_workspace_manager(), GitFeatureWorkspaceManager
    )


def test_app_factory_uses_configured_harness_root_for_prompt_definitions(
    tmp_path: Path,
) -> None:
    """Factory prompt wiring respects the effective harness root."""
    (tmp_path / "engineeringagent.toml").write_text(
        '[paths]\nharness_root = "custom-harness"\n',
        encoding="utf-8",
    )
    prompts_root = tmp_path / "custom-harness" / "prompts"
    prompts_root.mkdir(parents=True)

    factory = AppFactory(tmp_path)
    repository = factory.build_prompt_definition_repository()

    assert isinstance(repository, FilesystemPromptDefinitionRepository)
    assert repository._prompts_root == prompts_root


def test_app_factory_uses_configured_implementation_prompt_definition(
    tmp_path: Path,
) -> None:
    """Factory prompt wiring respects the effective implementation prompt id."""
    (tmp_path / "engineeringagent.toml").write_text(
        '[agents.implementation]\nprompt_definition = "repo_override"\n',
        encoding="utf-8",
    )

    prompt_builder = AppFactory(tmp_path).build_prompt_builder()

    assert prompt_builder._implementation_prompt_id == "repo_override"


def _build_runtime_dependencies(
    observed: dict[str, object],
) -> RuntimeFeatureIterationDependencies:
    return RuntimeFeatureIterationDependencies(
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
    )


def test_runtime_feature_iteration_commit_wiring_returns_failure_tuple_shape() -> None:
    """Runtime execution wiring should preserve the pipeline callback contract."""
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

    dependencies = build_iteration_pipeline_dependencies(
        _build_runtime_dependencies(observed),
        gateway,
    )
    completion_dependencies = dependencies.completion_phase_dependencies

    assert isinstance(completion_dependencies, _FakeCompletionPhaseDependencies)
    recorded_completion_dependencies = observed["completion_dependencies"]
    assert isinstance(recorded_completion_dependencies, dict)
    outcome = recorded_completion_dependencies["commit_feature_completion"](
        Path("/tmp/project"),
        {"expected_commit_subject": "feat: complete FEAT-001"},
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


def test_app_factory_persist_iteration_report_writes_json_payload_to_journal() -> None:
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


def test_app_factory_build_iteration_pipeline_dependencies_wires_completion_commit() -> None:
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

    dependencies = build_iteration_pipeline_dependencies(
        runtime_dependencies,
        gateway,
    )

    assert dependencies.describe_action is runtime_dependencies.describe_action
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


def test_app_factory_build_iteration_report_publisher_uses_journal_dependency(
    monkeypatch,
) -> None:
    """Bootstrap should assemble the default report publisher from journal seams."""
    observed: dict[str, object] = {}
    journal = _FakeProgressJournal(observed)
    monkeypatch.setattr(
        app_factory_module,
        "write_iteration_telemetry",
        lambda telemetry_inputs, git_head_resolver: (
            observed.setdefault(
                "telemetry_call",
                {
                    "telemetry_inputs": telemetry_inputs,
                    "git_head_resolver": git_head_resolver,
                },
            ),
            "progress/run-feature-FEAT-001.txt",
        )[-1],
    )
    monkeypatch.setattr(
        app_factory_module.runtime_support,
        "git_head_short",
        lambda _project_root: "abc1234",
    )
    monkeypatch.setattr(
        app_factory_module.runtime_support,
        "print_summary",
        lambda summary: observed.setdefault("summary", summary),
    )

    publisher = _build_iteration_report_publisher(journal)
    report = IterationReport(
        completed=False,
        result="failed",
        failed_gate="tests",
        next_action="retry_same_feature",
        feedback="rerun",
        feature_id="FEAT-001",
        attempt=1,
        selected_feature_path="docs/specifications/features/FEAT-001/specification.yaml",
        implement_step="engineeringagent implement",
        verification_status="failed:tests",
        verification_failed_command="uv run pytest",
        reviewer_status="not_run",
        reviewer_decision=None,
        failed_reviewer_id=None,
        telemetry_inputs=IterationTelemetryInputs(
            iteration_inputs=FeatureIterationInputs(
                project_root=Path("/tmp/project"),
                feature_path=Path(
                    "docs/specifications/features/FEAT-001/specification.yaml"
                ),
                run_all=False,
                attempt=1,
                feedback="rerun",
                verbose_output=False,
            ),
            started=1.0,
            feature_id="FEAT-001",
            result="failed",
            failed_gate="tests",
            next_action="retry_same_feature",
            implement_status="passed",
            gate_status="failed:tests",
            verification_status="failed:tests",
            verification_failed_command="uv run pytest",
            reviewer_status="not_run",
            reviewer_decision=None,
            failed_reviewer_id=None,
            implement_output="implemented",
            gate_output="tests failed",
            verification_output="pytest failed",
            reviewer_output="",
            feedback="rerun",
        ),
    )

    outcome = publisher.publish(report)

    assert outcome.result == "failed"
    assert observed["telemetry_call"] == {
        "telemetry_inputs": report.telemetry_inputs,
        "git_head_resolver": app_factory_module.runtime_support.git_head_short,
    }
    persisted_reports = observed["iteration_reports"]
    assert isinstance(persisted_reports, list)
    assert persisted_reports == [
        {
            "project_root": Path("/tmp/project"),
            "feature_id": "FEAT-001",
            "payload": {
                **report.model_dump(mode="json"),
                "log_path": "progress/run-feature-FEAT-001.txt",
            },
        }
    ]
