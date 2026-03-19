"""Local synchronous workspace runner."""

from datetime import UTC, datetime
from uuid import uuid4

from developer.workspaces.models import RunHandle, RunRequest, RunStatus
from developer.workspaces.protocols import (
    WorkspaceExecutionAdapterResolver,
    WorkspaceRunRegistry,
    WorkspaceRunnableAgentResolver,
)


class LocalProcessWorkspaceRunner:
    """Run workspace-backed workflows synchronously with persisted state."""

    def __init__(
        self,
        registry: WorkspaceRunRegistry,
        agent_resolver: WorkspaceRunnableAgentResolver,
        execution_adapter_resolver: WorkspaceExecutionAdapterResolver,
    ) -> None:
        """Store persistence and workflow resolution dependencies."""
        self._registry = registry
        self._agent_resolver = agent_resolver
        self._execution_adapter_resolver = execution_adapter_resolver

    def start_run(self, workspace_id: str, request: RunRequest) -> RunHandle:
        """Create, execute, and persist a run handle."""
        workspace = self._registry.get_workspace(workspace_id)
        pending_run = RunHandle(
            id=uuid4().hex,
            workspace_id=workspace_id,
            status=RunStatus.PENDING,
            agent_kind=request.agent_kind,
            latest_message="Run created",
        )
        self._registry.save_run(pending_run)

        running_run = self._save_updated_run(
            pending_run,
            status=RunStatus.RUNNING,
            started_at=datetime.now(UTC),
            latest_message=f"{request.agent_kind} run started",
        )

        try:
            agent = self._agent_resolver.resolve(request.agent_kind)
            execution_adapter = self._execution_adapter_resolver.resolve(
                workspace.execution_target
            )
            result = execution_adapter.run(
                workspace=workspace,
                request=request,
                agent=agent,
            )
        except Exception as exc:
            self._save_updated_run(
                running_run,
                status=RunStatus.FAILED,
                finished_at=datetime.now(UTC),
                latest_message=str(exc),
            )
            raise

        final_status = (
            RunStatus.SUCCEEDED if result.status == "succeeded" else RunStatus.FAILED
        )
        return self._save_updated_run(
            running_run,
            status=final_status,
            finished_at=datetime.now(UTC),
            latest_message=result.message,
            result_summary=result.summary,
        )

    def get_run(self, run_id: str) -> RunHandle:
        """Return one persisted run handle."""
        return self._registry.get_run(run_id)

    def list_runs(self, workspace_id: str | None = None) -> list[RunHandle]:
        """Return persisted run handles."""
        return self._registry.list_runs(workspace_id=workspace_id)

    def cancel_run(self, run_id: str) -> None:
        """Mark a non-terminal run as cancelled."""
        run = self._registry.get_run(run_id)
        if run.status in {
            RunStatus.SUCCEEDED,
            RunStatus.FAILED,
            RunStatus.CANCELLED,
        }:
            return

        self._save_updated_run(
            run,
            status=RunStatus.CANCELLED,
            finished_at=datetime.now(UTC),
            latest_message="Run cancelled",
        )

    def _save_updated_run(self, run: RunHandle, **updates: object) -> RunHandle:
        """Persist one updated run handle and return it."""
        updated_run = run.model_copy(update=updates)
        self._registry.save_run(updated_run)
        return updated_run
