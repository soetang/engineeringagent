"""Application service assembly owned by the bootstrap layer."""

from __future__ import annotations

from pathlib import Path

from engineeringagent.adapters.agents import ConfiguredAgentRunner
from engineeringagent.adapters.config import load_repository_config
from engineeringagent.adapters.quality import (
    ChecksRepositoryValidator,
    RuntimeChecksRunner,
)
from engineeringagent.adapters.documents import (
    ChecksCatalogLoadOptions,
    FilesystemChecksCatalogRepository,
    FilesystemGuidanceTopicRepository,
)
from engineeringagent.adapters.progress import FilesystemProgressJournal
from engineeringagent.adapters.prompts import FilesystemPromptDefinitionRepository
from engineeringagent.adapters.runtime import RuntimeRunLoopExecutor
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
from engineeringagent.ports import (
    AgentRunner,
    PromptDefinitionRepository,
    VersionControlGateway,
)


class AppFactory:
    """Compose concrete application services from repository adapters."""

    def __init__(self, project_root: Path) -> None:
        self._project_root = project_root.resolve()

    @property
    def project_root(self) -> Path:
        """Return the repository root used for factory-scoped resolution."""
        return self._project_root

    def build_checks_service(self) -> ChecksService:
        """Create the default deterministic checks service."""
        return ChecksService(
            RuntimeChecksRunner(),
            FilesystemChecksCatalogRepository(),
        )

    def build_run_loop_service(self) -> RunLoopService:
        """Create the default run-loop application service."""
        return RunLoopService(
            checks_catalog_repository=FilesystemChecksCatalogRepository(
                ChecksCatalogLoadOptions(
                    error_prefix="run config error",
                    missing_context=" (required for --all)",
                )
            ),
            executor=RuntimeRunLoopExecutor(
                build_feature_iteration_service=lambda project_root: AppFactory(
                    project_root
                ).build_feature_iteration_service(),
                build_version_control_gateway=lambda project_root: AppFactory(
                    project_root
                ).build_version_control_gateway(),
            ),
        )

    def build_feature_iteration_service(self) -> FeatureIterationService:
        """Create the default feature-iteration application service."""
        from engineeringagent.bootstrap.feature_iteration_runtime import (  # pylint: disable=import-outside-toplevel
            build_feature_iteration_runtime_dependencies,
        )

        return FeatureIterationService(
            version_control_gateway=self.build_version_control_gateway(),
            progress_journal=self.build_progress_journal(),
            runtime_dependencies=build_feature_iteration_runtime_dependencies(),
        )

    def build_guidance_service(self) -> GuidanceService:
        """Create the default guidance service."""
        return GuidanceService(FilesystemGuidanceTopicRepository())

    def build_validation_service(self) -> ValidationService:
        """Create the default repository validation service."""
        return ValidationService(ChecksRepositoryValidator())

    def build_init_workspace_service(self) -> InitWorkspaceService:
        """Create the default workspace initialization service."""
        return InitWorkspaceService()

    def build_progress_journal(self) -> FilesystemProgressJournal:
        """Create the default filesystem-backed progress journal."""
        return FilesystemProgressJournal()

    def build_agent_runner(self) -> AgentRunner:
        """Create the default configured agent-runner adapter."""
        return ConfiguredAgentRunner()

    def build_version_control_gateway(self) -> VersionControlGateway:
        """Create the default git-backed version-control gateway."""
        return GitCliVersionControlGateway()

    def build_feature_workspace_manager(self) -> GitFeatureWorkspaceManager:
        """Create the default git-backed feature workspace manager."""
        return GitFeatureWorkspaceManager()

    def build_prompt_definition_repository(self) -> PromptDefinitionRepository:
        """Create the default filesystem-backed prompt-definition repository."""
        config = load_repository_config(self.project_root)
        return FilesystemPromptDefinitionRepository(
            self.project_root / config.paths.harness_root / "prompts"
        )

    def build_prompt_builder(self) -> PromptBuilder:
        """Create the default deterministic prompt builder."""
        config = load_repository_config(self.project_root)
        return PromptBuilder(
            self.build_prompt_definition_repository(),
            implementation_prompt_id=config.agents.implementation.prompt_definition,
        )

    def build_workspace_recovery_service(self) -> WorkspaceRecoveryService:
        """Create the default workspace recovery service."""
        return WorkspaceRecoveryService(
            self.build_feature_workspace_manager(),
            self.build_progress_journal(),
        )
