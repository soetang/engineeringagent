from __future__ import annotations

from pathlib import Path

from engineeringagent.adapters.agents import ConfiguredAgentRunner
from engineeringagent.adapters.clock import SystemClock
from engineeringagent.adapters.config import FilesystemConfigurationProvider
from engineeringagent.adapters.quality import (
    ChecksRepositoryValidator,
    RuntimeChecksRunner,
)
from engineeringagent.adapters.runtime import RuntimeRunLoopExecutor
from engineeringagent.adapters.documents import (
    ChecksCatalogLoadOptions,
    FilesystemChecksCatalogRepository,
)
from engineeringagent.adapters.progress import FilesystemProgressJournal
from engineeringagent.adapters.prompts import FilesystemPromptDefinitionRepository
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
from engineeringagent.application.feature_iteration import (
    FeatureIterationRuntimeDependencies,
)
from engineeringagent.bootstrap import AppFactory
from engineeringagent.ports import ConfigurationProvider


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
    assert isinstance(
        feature_iteration_service._runtime_dependencies,
        FeatureIterationRuntimeDependencies,
    )
    assert isinstance(
        feature_iteration_service._version_control_gateway,
        GitCliVersionControlGateway,
    )
    assert isinstance(
        feature_iteration_service._progress_journal,
        FilesystemProgressJournal,
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
    assert isinstance(validation_service._validator, ChecksRepositoryValidator)
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
    assert isinstance(feature_iteration_service._runtime_dependencies.clock, SystemClock)
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
