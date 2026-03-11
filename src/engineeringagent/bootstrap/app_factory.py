"""Application service assembly owned by the bootstrap layer."""

from __future__ import annotations

from importlib import import_module
from pathlib import Path

from engineeringagent.adapters.agents import ConfiguredAgentRunner
from engineeringagent.adapters.checks import (
    ChecksRepositoryValidator,
    RuntimeChecksRunner,
)
from engineeringagent.adapters.documents import (
    ChecksCatalogLoadOptions,
    FilesystemChecksCatalogRepository,
)
from engineeringagent.adapters.guidance import PackagedGuidanceTopicRepository
from engineeringagent.adapters.loop import RuntimeRunLoopExecutor
from engineeringagent.adapters.progress import FilesystemProgressJournal
from engineeringagent.adapters.prompts import FilesystemPromptDefinitionRepository
from engineeringagent.adapters.vcs import (
    GitCliVersionControlGateway,
    GitFeatureWorkspaceManager,
)
from engineeringagent.application import (
    ChecksService,
    FeatureIterationService,
    FeatureIterationRuntime,
    GuidanceService,
    InitWorkspaceService,
    PromptBuilder,
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
            checks_catalog_repository=FilesystemChecksCatalogRepository(
                ChecksCatalogLoadOptions(
                    error_prefix="run config error",
                    missing_context=" (required for --all)",
                )
            ),
            executor=RuntimeRunLoopExecutor(),
        )

    def build_feature_iteration_service(self) -> FeatureIterationService:
        """Create the default feature-iteration application service."""
        return FeatureIterationService(
            version_control_gateway=self.build_version_control_gateway(),
            progress_journal=self.build_progress_journal(),
            runtime=self.build_feature_iteration_runtime(),
        )

    def build_feature_iteration_runtime(self) -> FeatureIterationRuntime:
        """Create the legacy loop-runtime collaborator bundle for the service."""
        checks_module = import_module("engineeringagent.checks")
        loop_module = import_module("engineeringagent.loop")
        feature_state = import_module("engineeringagent.loop_runtime.feature_state")
        iteration = import_module("engineeringagent.loop_runtime.iteration")
        models = import_module("engineeringagent.loop_runtime.models")
        observers = import_module("engineeringagent.loop_runtime.observers")
        phases = import_module("engineeringagent.loop_runtime.phases")
        telemetry = import_module("engineeringagent.loop_runtime.telemetry")

        return FeatureIterationRuntime(
            build_inputs=models.FeatureIterationInputs,
            build_iteration_dependencies=iteration.IterationPipelineDependencies,
            run_feature_iteration_pipeline=iteration.run_feature_iteration_pipeline,
            build_gate_phase_dependencies=phases.GatePhaseDependencies,
            build_reviewer_phase_dependencies=phases.ReviewerPhaseDependencies,
            build_completion_phase_dependencies=phases.CompletionPhaseDependencies,
            build_default_observer_dependencies=observers.DefaultObserverDependencies,
            build_default_iteration_report_observers=(
                observers.build_default_iteration_report_observers
            ),
            publish_iteration_report=observers.publish_iteration_report,
            write_iteration_telemetry=telemetry.write_iteration_telemetry,
            run_implement_step=loop_module.run_implement_step,
            git_head_resolver=loop_module.git_head_short,
            print_summary=loop_module.print_summary,
            evaluate_initial_feature_load=feature_state.evaluate_initial_feature_load,
            ready_for_active_iteration=feature_state.ready_for_active_iteration,
            touch_active_feature_for_iteration=(
                feature_state.touch_active_feature_for_iteration
            ),
            refresh_feature_after_implement=(
                feature_state.refresh_feature_after_implement
            ),
            should_archive_selected_feature=(
                feature_state.should_archive_selected_feature
            ),
            archive_completed_feature=feature_state.archive_completed_feature,
            restore_archived_feature=feature_state.restore_archived_feature,
            collect_changed_paths=checks_module.collect_changed_paths,
            run_gate_phase=phases.run_gate_phase,
            run_verification_phase=phases.run_verification_phase,
            run_reviewer_phase=phases.run_reviewer_phase,
            run_completion_commit_phase=phases.run_completion_commit_phase,
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

    def build_feature_workspace_manager(self) -> GitFeatureWorkspaceManager:
        """Create the default git-backed feature workspace manager."""
        return GitFeatureWorkspaceManager()

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
            self.build_feature_workspace_manager(),
            self.build_progress_journal(),
        )
