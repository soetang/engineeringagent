"""Protocol boundaries for workspace orchestration."""

from typing import Protocol

from .workspace_models import (
    RunHandle,
    RunRequest,
    WorkspaceRunnableResult,
    WorkspaceSession,
    WorkspaceSpec,
)


class WorkspaceProvider(Protocol):
    """Provision and manage execution workspaces."""

    def create(self, spec: WorkspaceSpec) -> WorkspaceSession:
        """Create a workspace for the provided specification."""
        ...

    def get(self, workspace_id: str) -> WorkspaceSession:
        """Return a previously created workspace."""
        ...

    def list(self) -> list[WorkspaceSession]:
        """Return all known workspaces."""
        ...

    def destroy(self, workspace_id: str) -> None:
        """Destroy a previously created workspace."""
        ...


class WorkspaceRunRegistry(Protocol):
    """Persistence boundary for workspace sessions and runs."""

    def save_workspace(self, workspace: WorkspaceSession) -> None:
        """Persist workspace state."""
        ...

    def save_run(self, run: RunHandle) -> None:
        """Persist run state."""
        ...

    def get_workspace(self, workspace_id: str) -> WorkspaceSession:
        """Load one workspace."""
        ...

    def list_workspaces(self) -> list[WorkspaceSession]:
        """List persisted workspaces."""
        ...

    def get_run(self, run_id: str) -> RunHandle:
        """Load one run."""
        ...

    def list_runs(self, workspace_id: str | None = None) -> list[RunHandle]:
        """List persisted runs."""
        ...


class WorkspaceRunnableAgent(Protocol):
    """A complete workflow that can execute inside a workspace."""

    def run(
        self, request: RunRequest, workspace: WorkspaceSession
    ) -> WorkspaceRunnableResult:
        """Execute the requested workflow and return a summary."""
        ...


class WorkspaceRunnableAgentResolver(Protocol):
    """Resolve workflow implementations by agent kind."""

    def resolve(self, agent_kind: str) -> WorkspaceRunnableAgent:
        """Return the runnable agent for the requested kind."""
        ...


class WorkspaceRunner(Protocol):
    """Start and inspect workflow runs within workspaces."""

    def start_run(self, workspace_id: str, request: RunRequest) -> RunHandle:
        """Start a run in the requested workspace."""
        ...

    def get_run(self, run_id: str) -> RunHandle:
        """Return one run handle."""
        ...

    def list_runs(self, workspace_id: str | None = None) -> list[RunHandle]:
        """Return run handles, optionally for one workspace."""
        ...

    def cancel_run(self, run_id: str) -> None:
        """Cancel a run when supported."""
        ...
