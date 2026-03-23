"""Workspace-backed adapter for the run-orchestrator publication store port."""

from __future__ import annotations

from developer.orchestrators.runs.models import PublishedTaskBranch
from developer.orchestrators.runs.protocols import TaskPublicationStore
from developer.workspaces.services.file_registry import FileWorkspaceRegistry


class FileWorkspaceTaskPublicationStore(TaskPublicationStore):
    """Adapt persisted workspace publication state to orchestrator-owned models."""

    def __init__(self, registry: FileWorkspaceRegistry) -> None:
        """Store the workspace registry used to load publication state."""
        self._registry = registry

    def get_task_publication(
        self,
        task_name: str,
        task_path: str | None,
    ) -> PublishedTaskBranch | None:
        """Return the persisted publication record when one exists."""
        publication = self._registry.get_task_publication(task_name, task_path)
        if publication is None:
            return None
        return PublishedTaskBranch(branch_name=publication.branch_name)
