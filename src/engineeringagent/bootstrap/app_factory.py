"""Application service assembly owned by the bootstrap layer."""

from __future__ import annotations

from importlib import import_module
from pathlib import Path

from engineeringagent import checks as checks_module
from engineeringagent.adapters.agents import ConfiguredAgentRunner
from engineeringagent.adapters.checks import (
    ChecksRepositoryValidator,
    FilesystemChecksCatalogRepository,
    RuntimeChecksRunner,
)
from engineeringagent.adapters.guidance import PackagedGuidanceTopicRepository
from engineeringagent.adapters.progress import FilesystemProgressJournal
from engineeringagent.adapters.prompts import FilesystemPromptDefinitionRepository
from engineeringagent.adapters.vcs import GitCliVersionControlGateway
from engineeringagent.application import (
    ChecksService,
    GuidanceService,
    InitWorkspaceService,
    PromptBuilder,
    RunLoopRequest,
    RunLoopService,
    ValidationService,
    WorkspaceRecoveryService,
)
from engineeringagent.config import resolve_harness_root
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
            load_harness_checks_document=self._load_run_all_checks_document,
            execute_run_loop=self._execute_run_loop,
        )

    def build_guidance_service(self) -> GuidanceService:
        """Create the packaged guidance service."""
        return GuidanceService(PackagedGuidanceTopicRepository())

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

    def build_prompt_definition_repository(self) -> PromptDefinitionRepository:
        """Create the default filesystem-backed prompt-definition repository."""
        return FilesystemPromptDefinitionRepository(
            resolve_harness_root(self.project_root) / "prompts"
        )

    def build_prompt_builder(self) -> PromptBuilder:
        """Create the default deterministic prompt builder."""
        return PromptBuilder(self.build_prompt_definition_repository())

    def build_workspace_recovery_service(self) -> WorkspaceRecoveryService:
        """Create the default workspace recovery service."""
        return WorkspaceRecoveryService(
            self.build_version_control_gateway(),
            self.build_progress_journal(),
        )

    def _load_run_all_checks_document(
        self,
        project_root: Path,
    ) -> tuple[object | None, str | None]:
        return checks_module.load_harness_checks_document(
            project_root,
            error_prefix="run config error",
            missing_context=" (required for --all)",
        )

    def _execute_run_loop(self, request: RunLoopRequest) -> int:
        loop_module = import_module("engineeringagent.loop")
        controller_module = import_module("engineeringagent.loop_runtime.controller")

        config = loop_module.build_run_config(
            project_root=request.project_root,
            feature_paths=request.feature_paths,
            options=loop_module.RunConfigOptions(
                request.dry_run,
                request.run_all,
                request.max_iterations,
                request.allow_dirty,
                request.verbose_output,
            ),
        )
        loop_run = loop_module.build_loop_run(config)
        return controller_module.run_loop_controller(loop_run)
