"""Protocol interfaces for implementation run orchestration."""

from __future__ import annotations

from typing import Protocol

from developer.orchestrators.runs.models import WorkspaceRunCommand, WorkspaceRunResult


class ImplementationRunTask(Protocol):
    """Task contract required by workspace-backed run orchestration."""

    @property
    def task_id(self) -> str:
        """Return the stable task identity."""
        ...

    @property
    def task_name(self) -> str:
        """Return the current task name."""
        ...

    @property
    def task_path(self) -> str | None:
        """Return the task path when one is available."""
        ...

    @property
    def base_branch(self) -> str | None:
        """Return the task's preferred base branch when explicitly defined."""
        ...

    @property
    def workspace_provider(self) -> str:
        """Return the workspace provider required for this task."""
        ...

    @property
    def workspace_agent_kind(self) -> str:
        """Return the workspace agent kind required for this task."""
        ...

    def get_branch_name(self) -> str:
        """Return the stable branch name for this task."""
        ...


class PublishedTaskBranchView(Protocol):
    """Minimal publication data required by the run orchestrator."""

    @property
    def branch_name(self) -> str:
        """Return the published branch name for the task."""
        ...


class TaskPublicationStore(Protocol):
    """Loads persisted publication information used during planning."""

    def get_task_publication(
        self,
        task_name: str,
        task_path: str | None,
    ) -> PublishedTaskBranchView | None:
        """Return the stored publication branch for the task when present."""
        ...


class BranchInspectionPort(Protocol):
    """Reads branch state without owning orchestration decisions."""

    def get_current_branch(self, repo_path: str) -> str:
        """Return the currently checked out branch name."""
        ...

    def branch_exists(
        self,
        repo_path: str,
        branch_name: str,
        remote_name: str = "origin",
    ) -> bool:
        """Return whether the branch already exists locally or remotely."""
        ...


class WorkspaceRunPort(Protocol):
    """Delegates an already-planned run to workspace infrastructure."""

    def run(self, command: WorkspaceRunCommand) -> WorkspaceRunResult:
        """Execute the workspace run command."""
        ...


__all__ = [
    "BranchInspectionPort",
    "ImplementationRunTask",
    "PublishedTaskBranchView",
    "TaskPublicationStore",
    "WorkspaceRunPort",
]
