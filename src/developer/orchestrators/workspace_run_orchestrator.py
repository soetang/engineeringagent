"""Composition service for workspace-backed workflow execution."""

from developer.orchestrators.workspace_protocols import (
    WorkspaceProvider,
    WorkspaceRunner,
)

from .workspace_models import RunHandle, RunRequest, WorkspaceSession, WorkspaceSpec


class WorkspaceRunOrchestrator:
    """Coordinate workspace provisioning with workflow execution."""

    def __init__(
        self,
        workspace_provider: WorkspaceProvider,
        workspace_runner: WorkspaceRunner,
    ) -> None:
        """Store workspace lifecycle and run lifecycle dependencies."""
        self._workspace_provider = workspace_provider
        self._workspace_runner = workspace_runner

    def run_in_workspace(
        self,
        workspace_spec: WorkspaceSpec,
        request: RunRequest,
    ) -> tuple[WorkspaceSession, RunHandle]:
        """Create a workspace and start a run inside it."""
        workspace = self._workspace_provider.create(workspace_spec)
        run = self._workspace_runner.start_run(workspace.id, request)
        return workspace, run
