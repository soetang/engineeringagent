"""Protocol boundaries for workspace runtime components."""

from typing import Protocol

from engineeringagent.tasks.models import TaskPublicationState
from engineeringagent.workspaces.models import (
    ExecutionTarget,
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

    def save_task_publication(self, publication: TaskPublicationState) -> None:
        """Persist publication state for one task."""
        ...

    def get_task_publication(
        self,
        task_name: str,
        task_path: str | None = None,
    ) -> TaskPublicationState | None:
        """Load publication state for one task, if present."""
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


class WorkspaceExecutionAdapter(Protocol):
    """Execute a workspace-runnable workflow inside one execution target."""

    def run(
        self,
        workspace: WorkspaceSession,
        request: RunRequest,
        agent: WorkspaceRunnableAgent,
    ) -> WorkspaceRunnableResult:
        """Run a workflow inside the requested execution target."""
        ...


class WorkspaceExecutionAdapterResolver(Protocol):
    """Resolve target-specific execution adapters."""

    def resolve(self, target: ExecutionTarget) -> WorkspaceExecutionAdapter:
        """Return the execution adapter for the requested target."""
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


__all__ = [
    "WorkspaceExecutionAdapter",
    "WorkspaceExecutionAdapterResolver",
    "WorkspaceProvider",
    "WorkspaceRunRegistry",
    "WorkspaceRunnableAgent",
    "WorkspaceRunnableAgentResolver",
    "WorkspaceRunner",
]
