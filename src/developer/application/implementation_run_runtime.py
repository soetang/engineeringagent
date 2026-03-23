"""Application-layer composition for workspace-backed implementation runs."""

from __future__ import annotations

from pathlib import Path

from developer.application.workspace_runtime import build_workspace_orchestrator
from developer.config.service import ConfigService
from developer.orchestrators.runs.implementation_workspace_run_orchestrator import (
    ImplementationWorkspaceRunOrchestrator,
)
from developer.orchestrators.runs.models import WorkspaceRunCommand, WorkspaceRunResult
from developer.orchestrators.runs.protocols import WorkspaceRunPort
from developer.version_control.adapters.git_adapter import GitVersionControlAdapter
from developer.workspaces.models import RunRequest, WorkspaceSpec
from developer.workspaces.services.file_registry import FileWorkspaceRegistry
from developer.workspaces.settings import WorkspaceSettings
from developer.workspaces.task_publication_store import (
    FileWorkspaceTaskPublicationStore,
)


class WorkspaceRunOrchestratorPortAdapter(WorkspaceRunPort):
    """Adapt the generic workspace runtime to the run-orchestrator port."""

    def __init__(self, workspace_runner) -> None:
        """Store the composed workspace runtime."""
        self._workspace_runner = workspace_runner

    def run(self, command: WorkspaceRunCommand) -> WorkspaceRunResult:
        """Translate orchestrator commands into workspace runtime requests."""
        workspace, run_handle = self._workspace_runner.run_in_workspace(
            WorkspaceSpec(
                provider=command.workspace_provider,
                repo_path=command.repo_path,
                base_branch=command.base_branch,
                task_id=command.task_id,
                metadata=command.workspace_metadata,
            ),
            RunRequest(
                agent_kind=command.agent_kind,
                context=command.run_context,
            ),
        )
        return WorkspaceRunResult(
            workspace_id=workspace.id,
            run_id=run_handle.id,
            status=run_handle.status.value,
            latest_message=run_handle.latest_message,
            metadata=dict(run_handle.metadata),
        )


def build_implementation_workspace_run_orchestrator(
    config_service: ConfigService,
) -> ImplementationWorkspaceRunOrchestrator:
    """Compose the concrete ports needed for workspace-backed run orchestration."""
    workspace_settings = config_service.get_config("workspaces", WorkspaceSettings)
    registry = FileWorkspaceRegistry(Path(workspace_settings.state_dir).resolve())
    return ImplementationWorkspaceRunOrchestrator(
        publication_store=FileWorkspaceTaskPublicationStore(registry),
        branch_inspector=GitVersionControlAdapter(),
        workspace_runner=WorkspaceRunOrchestratorPortAdapter(
            build_workspace_orchestrator(config_service)
        ),
    )
