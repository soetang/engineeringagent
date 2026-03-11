from __future__ import annotations

from pathlib import Path

from engineeringagent.adapters.checks import (
    ChecksRepositoryValidator,
    FilesystemChecksCatalogRepository,
    RuntimeChecksRunner,
)
from engineeringagent.adapters.agents import ConfiguredAgentRunner
from engineeringagent.adapters.progress import FilesystemProgressJournal
from engineeringagent.adapters.prompts import FilesystemPromptDefinitionRepository
from engineeringagent.adapters.vcs import GitCliVersionControlGateway
from engineeringagent.application import (
    ChecksService,
    GuidanceService,
    InitWorkspaceService,
    PromptBuilder,
    ValidationService,
    WorkspaceRecoveryService,
)
from engineeringagent.bootstrap import AppFactory


def test_app_factory_resolves_project_root() -> None:
    """Factory root resolution is absolute and deterministic."""
    factory = AppFactory(Path("."))

    assert factory.project_root == Path(".").resolve()


def test_app_factory_builds_default_application_services(tmp_path: Path) -> None:
    """Factory wires the concrete default services used by the CLI."""
    factory = AppFactory(tmp_path)
    checks_service = factory.build_checks_service()

    assert isinstance(checks_service, ChecksService)
    assert isinstance(checks_service._checks_runner, RuntimeChecksRunner)
    assert isinstance(
        checks_service._checks_catalog_repository,
        FilesystemChecksCatalogRepository,
    )
    assert isinstance(factory.build_guidance_service(), GuidanceService)
    validation_service = factory.build_validation_service()
    assert isinstance(validation_service, ValidationService)
    assert isinstance(validation_service._validator, ChecksRepositoryValidator)
    assert isinstance(factory.build_init_workspace_service(), InitWorkspaceService)
    assert isinstance(factory.build_progress_journal(), FilesystemProgressJournal)
    assert isinstance(factory.build_agent_runner(), ConfiguredAgentRunner)
    assert isinstance(
        factory.build_version_control_gateway(),
        GitCliVersionControlGateway,
    )
    assert isinstance(
        factory.build_prompt_definition_repository(),
        FilesystemPromptDefinitionRepository,
    )
    assert isinstance(factory.build_prompt_builder(), PromptBuilder)
    recovery_service = factory.build_workspace_recovery_service()
    assert isinstance(recovery_service, WorkspaceRecoveryService)
    assert isinstance(recovery_service._version_control, GitCliVersionControlGateway)
    assert isinstance(recovery_service._progress_journal, FilesystemProgressJournal)


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
