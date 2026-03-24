"""Application-layer workspace runtime composition helpers."""

from pathlib import Path

from engineeringagent.agent_backends.select_agent_backend_service import (
    SelectAgentBackendService,
)
from engineeringagent.application.publication_runtime import (
    RegistryPublicationStateStore,
    RegistryRunMetadataStore,
    WorkspaceProviderLifecyclePort,
)
from engineeringagent.application.workspace_bridges import (
    DefaultWorkspaceRunnableAgentResolver,
    WorkspaceRunnableImplementationAgent,
)
from engineeringagent.config.service import ConfigService
from engineeringagent.forge.select_service import SelectForgeService
from engineeringagent.orchestrators.publication import PublicationObserver
from engineeringagent.prompts import ConfiguredPublicationPromptRenderer
from engineeringagent.version_control.select_service import SelectVersionControlService
from engineeringagent.workspaces.adapters.default_execution_adapter_resolver import (
    DefaultWorkspaceExecutionAdapterResolver,
)
from engineeringagent.workspaces.adapters.git_worktree_provider import (
    GitWorktreeWorkspaceProvider,
)
from engineeringagent.workspaces.adapters.local_process_runner import (
    LocalProcessWorkspaceRunner,
)
from engineeringagent.workspaces.services.file_registry import FileWorkspaceRegistry
from engineeringagent.workspaces.services.workspace_run_orchestrator import (
    WorkspaceRunOrchestrator,
)
from engineeringagent.workspaces.settings import WorkspaceSettings


def build_workspace_orchestrator(
    config_service: ConfigService | None = None,
) -> WorkspaceRunOrchestrator:
    """Create the default workspace-backed implementation orchestrator."""
    resolved_config_service = config_service or ConfigService()
    settings = resolved_config_service.get_config("workspaces", WorkspaceSettings)
    registry = FileWorkspaceRegistry(Path(settings.state_dir).resolve())
    provider = GitWorktreeWorkspaceProvider(
        workspaces_root=Path(settings.git_worktree_root_dir).resolve(),
        registry=registry,
    )
    observer = _build_workspace_observer(resolved_config_service, registry, provider)
    runner = LocalProcessWorkspaceRunner(
        registry=registry,
        agent_resolver=DefaultWorkspaceRunnableAgentResolver(
            WorkspaceRunnableImplementationAgent(observer=observer)
        ),
        execution_adapter_resolver=DefaultWorkspaceExecutionAdapterResolver(),
    )
    return WorkspaceRunOrchestrator(provider, runner)


def _build_workspace_observer(
    config_service: ConfigService,
    registry: FileWorkspaceRegistry,
    provider: GitWorktreeWorkspaceProvider,
) -> PublicationObserver | None:
    """Build the optional observer used for commits and publication."""
    version_control = SelectVersionControlService(config_service).select()
    forge = SelectForgeService(config_service).select()
    if version_control is None:
        return None
    agent_runner = SelectAgentBackendService(config_service).select_agent()
    return PublicationObserver(
        publication_state_store=RegistryPublicationStateStore(registry),
        run_metadata_store=RegistryRunMetadataStore(registry),
        workspace_lifecycle=WorkspaceProviderLifecyclePort(provider),
        version_control=version_control,
        prompt_renderer=ConfiguredPublicationPromptRenderer(config_service),
        agent_runner=agent_runner,
        forge=forge,
    )
