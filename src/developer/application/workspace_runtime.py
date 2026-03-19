"""Application-layer workspace runtime composition helpers."""

from pathlib import Path

from developer.application.workspace_bridges import (
    DefaultWorkspaceRunnableAgentResolver,
)
from developer.config.service import ConfigService
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
    runner = LocalProcessWorkspaceRunner(
        registry=registry,
        agent_resolver=DefaultWorkspaceRunnableAgentResolver(),
        execution_adapter_resolver=DefaultWorkspaceExecutionAdapterResolver(),
    )
    return WorkspaceRunOrchestrator(provider, runner)
