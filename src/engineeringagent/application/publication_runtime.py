"""Application-owned adapters for publication orchestrator ports."""

from collections.abc import Mapping

from engineeringagent.orchestrators.publication import PublicationState
from engineeringagent.tasks.models import TaskPublicationState
from engineeringagent.workspaces.protocols import (
    WorkspaceProvider,
    WorkspaceRunRegistry,
)


class RegistryPublicationStateStore:
    """Persist publication state through the workspace registry."""

    def __init__(self, registry: WorkspaceRunRegistry) -> None:
        """Store the registry used for persistence."""
        self._registry = registry

    def save_publication(self, publication: PublicationState) -> None:
        """Persist publication state after translating to the registry model."""
        self._registry.save_task_publication(
            TaskPublicationState(
                task_name=publication.task_name,
                task_path=publication.task_path,
                branch_name=publication.branch_name,
                base_branch=publication.base_branch,
                pr_url=publication.pr_url,
                pr_number=publication.pr_number,
                status=publication.status,
            )
        )


class RegistryRunMetadataStore:
    """Persist publication metadata through the workspace registry."""

    def __init__(self, registry: WorkspaceRunRegistry) -> None:
        """Store the registry used for run metadata updates."""
        self._registry = registry

    def update_run_metadata(self, run_id: str, updates: Mapping[str, object]) -> None:
        """Merge updates into the persisted run metadata."""
        run = self._registry.get_run(run_id)
        metadata = dict(run.metadata)
        metadata.update(dict(updates))
        self._registry.save_run(run.model_copy(update={"metadata": metadata}))

    def append_run_metadata_item(self, run_id: str, key: str, value: object) -> None:
        """Append one value to a run-metadata list."""
        run = self._registry.get_run(run_id)
        metadata = dict(run.metadata)
        existing = metadata.get(key, [])
        metadata[key] = [*existing, value] if isinstance(existing, list) else [value]
        self._registry.save_run(run.model_copy(update={"metadata": metadata}))


class WorkspaceProviderLifecyclePort:
    """Destroy workspaces through the configured workspace provider."""

    def __init__(self, workspace_provider: WorkspaceProvider) -> None:
        """Store the provider used for cleanup."""
        self._workspace_provider = workspace_provider

    def destroy_workspace(self, workspace_id: str) -> None:
        """Destroy one provisioned workspace."""
        self._workspace_provider.destroy(workspace_id)
