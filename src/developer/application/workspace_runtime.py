"""Application-layer workspace runtime composition helpers."""

from pathlib import Path

from developer.agent_backends.select_agent_backend_service import (
    SelectAgentBackendService,
)
from developer.application.observers.workspace_version_control_observer import (
    WorkspaceVersionControlObserver,
)
from developer.application.workspace_bridges import (
    DefaultWorkspaceRunnableAgentResolver,
    WorkspaceRunnableImplementationAgent,
)
from developer.config.service import ConfigService
from developer.forge.select_service import SelectForgeService
from developer.version_control.content_service import VersionControlContentService
from developer.version_control.select_service import SelectVersionControlService
from developer.workspaces.adapters.default_execution_adapter_resolver import (
    DefaultWorkspaceExecutionAdapterResolver,
)
from developer.workspaces.adapters.git_worktree_provider import (
    GitWorktreeWorkspaceProvider,
)
from developer.workspaces.adapters.local_process_runner import (
    LocalProcessWorkspaceRunner,
)
from developer.workspaces.services.file_registry import FileWorkspaceRegistry
from developer.workspaces.services.workspace_run_orchestrator import (
    WorkspaceRunOrchestrator,
)
from developer.workspaces.settings import WorkspaceSettings


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
) -> WorkspaceVersionControlObserver | None:
    """Build the optional observer used for commits and publication."""
    version_control = SelectVersionControlService(config_service).select()
    forge = SelectForgeService(config_service).select()
    if version_control is None:
        return None
    content_service = VersionControlContentService(
        agent_runner=SelectAgentBackendService(config_service).select_agent(),
        config_service=config_service,
    )
    return WorkspaceVersionControlObserver(
        registry=registry,
        workspace_provider=provider,
        version_control=version_control,
        content_service=content_service,
        forge=forge,
    )
