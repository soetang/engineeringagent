"""Application service assembly owned by the bootstrap layer."""

from __future__ import annotations

from pathlib import Path

from engineeringagent.adapters.agents import ConfiguredAgentRunner
from engineeringagent.adapters.clock import SystemClock
from engineeringagent.adapters.config import FilesystemConfigurationProvider
from engineeringagent.adapters.quality.changed_paths import collect_changed_paths
from engineeringagent.adapters.quality.validation import (
    QualityRepositoryValidator,
)
from engineeringagent.adapters.quality.runtime import RuntimeChecksRunner
from engineeringagent.adapters.documents import (
    ChecksCatalogLoadOptions,
    FilesystemChecksCatalogRepository,
    FilesystemGuidanceTopicRepository,
)
from engineeringagent.adapters.progress import (
    FilesystemProgressJournal,
    write_iteration_telemetry,
)
from engineeringagent.adapters.prompts import FilesystemPromptDefinitionRepository
from engineeringagent.adapters.runtime import (
    RuntimeRunLoopExecutor,
)
from engineeringagent.adapters.runtime import feature_state
from engineeringagent.adapters.runtime.iteration_phases import (
    CompletionPhaseDependencies,
    GatePhaseDependencies,
    ReviewerPhaseDependencies,
    run_completion_commit_phase,
    run_gate_phase,
    run_reviewer_phase,
    run_verification_phase,
)
from engineeringagent.adapters.vcs import (
    GitCliVersionControlGateway,
    GitWorktreeManager,
)
from engineeringagent.application.checks_service import ChecksService
from engineeringagent.application.feature_iteration_service import (
    FeatureIterationService,
)
from engineeringagent.application.guidance_service import GuidanceService
from engineeringagent.application.init_workspace_service import InitWorkspaceService
from engineeringagent.application.prompt_builder import PromptBuilder
from engineeringagent.application.run_loop_service import RunLoopService
from engineeringagent.application.validation_service import ValidationService
from engineeringagent.application.workspace_recovery_service import (
    WorkspaceRecoveryService,
)
from engineeringagent.ports import (
    AgentRunner,
    Clock,
    ConfigurationProvider,
    PromptDefinitionRepository,
    ProgressJournal,
    VersionControlGateway,
)
from engineeringagent.application.feature_iteration.runtime_dependencies import (
    FeatureIterationDependencies,
)
from engineeringagent.bootstrap import runtime_support
from engineeringagent.bootstrap.iteration_reporting import (
    DefaultObserverDependencies,
    DefaultIterationReportPublisher,
    IterationReportPublisher,
)
from engineeringagent.domain.audit.iteration_records import IterationReport


def _persist_iteration_report(
    progress_journal: ProgressJournal,
    report: IterationReport,
) -> None:
    """Persist the structured iteration report through the journal port."""
    progress_journal.write_iteration_report(
        project_root=report.telemetry_inputs.iteration_inputs.project_root,
        feature_id=report.feature_id,
        payload=report.model_dump(mode="json"),
    )


def _build_iteration_report_publisher(
    progress_journal: ProgressJournal,
) -> IterationReportPublisher:
    """Build the default iteration-report publisher from bootstrap seams."""
    return DefaultIterationReportPublisher(
        DefaultObserverDependencies(
            write_iteration_telemetry=(
                lambda telemetry_inputs: write_iteration_telemetry(
                    telemetry_inputs,
                    git_head_resolver=runtime_support.git_head_short,
                )
            ),
            persist_iteration_report=(
                lambda report: _persist_iteration_report(progress_journal, report)
            ),
            git_head_resolver=runtime_support.git_head_short,
            print_summary=runtime_support.print_summary,
        )
    )


def _build_feature_iteration_dependencies(
    *,
    clock: Clock,
) -> FeatureIterationDependencies:
    """Build the default runtime seam bundle for feature iterations."""
    return FeatureIterationDependencies(
        clock=clock,
        evaluate_initial_feature_load=feature_state.evaluate_initial_feature_load,
        describe_action=runtime_support.describe_action,
        ready_for_active_iteration=feature_state.ready_for_active_iteration,
        touch_active_feature_for_iteration=(feature_state.touch_active_feature_for_iteration),
        run_implement_step=runtime_support.run_implement_step,
        refresh_feature_after_implement=(feature_state.refresh_feature_after_implement),
        should_archive_selected_feature=(feature_state.should_archive_selected_feature),
        archive_completed_feature=feature_state.archive_completed_feature,
        collect_changed_paths=collect_changed_paths,
        restore_archived_feature=feature_state.restore_archived_feature,
        run_gate_phase=run_gate_phase,
        build_gate_phase_dependencies=GatePhaseDependencies,
        run_verification_phase=run_verification_phase,
        run_reviewer_phase=run_reviewer_phase,
        build_reviewer_phase_dependencies=ReviewerPhaseDependencies,
        run_completion_commit_phase=run_completion_commit_phase,
        build_completion_phase_dependencies=CompletionPhaseDependencies,
    )


class AppFactory:
    """Compose concrete application services from repository adapters."""

    def __init__(self, project_root: Path) -> None:
        self._project_root = project_root.resolve()

    @property
    def project_root(self) -> Path:
        """Return the repository root used for factory-scoped resolution."""
        return self._project_root

    def build_configuration_provider(self) -> ConfigurationProvider:
        """Create the default repository-configuration provider."""
        return FilesystemConfigurationProvider(self.project_root)

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
        return FeatureIterationService(
            version_control_gateway=self.build_version_control_gateway(),
            iteration_report_publisher=_build_iteration_report_publisher(
                self.build_progress_journal()
            ),
            dependencies=_build_feature_iteration_dependencies(
                clock=self.build_clock(),
            ),
        )

    def build_guidance_service(self) -> GuidanceService:
        """Create the default guidance service."""
        return GuidanceService(FilesystemGuidanceTopicRepository())

    def build_validation_service(self) -> ValidationService:
        """Create the default repository validation service."""
        return ValidationService(QualityRepositoryValidator())

    def build_init_workspace_service(self) -> InitWorkspaceService:
        """Create the default workspace initialization service."""
        return InitWorkspaceService()

    def build_progress_journal(self) -> FilesystemProgressJournal:
        """Create the default filesystem-backed progress journal."""
        return FilesystemProgressJournal()

    def build_agent_runner(self) -> AgentRunner:
        """Create the default configured agent-runner adapter."""
        return ConfiguredAgentRunner()

    def build_clock(self) -> Clock:
        """Create the default clock adapter."""
        return SystemClock()

    def build_version_control_gateway(self) -> VersionControlGateway:
        """Create the default git-backed version-control gateway."""
        return GitCliVersionControlGateway()

    def build_feature_workspace_manager(self) -> GitWorktreeManager:
        """Create the default git-backed feature workspace manager."""
        return GitWorktreeManager()

    def build_prompt_definition_repository(self) -> PromptDefinitionRepository:
        """Create the default filesystem-backed prompt-definition repository."""
        config = self.build_configuration_provider().load()
        return FilesystemPromptDefinitionRepository(
            self.project_root / config.paths.harness_root / "prompts"
        )

    def build_prompt_builder(self) -> PromptBuilder:
        """Create the default deterministic prompt builder."""
        config = self.build_configuration_provider().load()
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
