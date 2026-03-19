"""Local synchronous workspace runner."""

from datetime import UTC, datetime
from uuid import uuid4

from developer.orchestrators.workspace_protocols import (
    WorkspaceRunRegistry,
    WorkspaceRunnableAgentResolver,
)
from developer.workspaces.models import RunHandle, RunRequest, RunStatus


class LocalProcessWorkspaceRunner:
    """Run workspace-backed workflows synchronously with persisted state."""

    def __init__(
        self,
        registry: WorkspaceRunRegistry,
        agent_resolver: WorkspaceRunnableAgentResolver,
    ) -> None:
        """Store persistence and workflow resolution dependencies."""
        self._registry = registry
        self._agent_resolver = agent_resolver

    def start_run(self, workspace_id: str, request: RunRequest) -> RunHandle:
        """Create, execute, and persist a run handle."""
        workspace = self._registry.get_workspace(workspace_id)
        run = RunHandle(
            id=uuid4().hex,
            workspace_id=workspace_id,
            status=RunStatus.PENDING,
            agent_kind=request.agent_kind,
            latest_message="Run created",
        )
        self._registry.save_run(run)

        running_run = run.model_copy(
            update={
                "status": RunStatus.RUNNING,
                "started_at": datetime.now(UTC),
                "latest_message": f"{request.agent_kind} run started",
            }
        )
        self._registry.save_run(running_run)

        try:
            agent = self._agent_resolver.resolve(request.agent_kind)
            result = agent.run(request=request, workspace=workspace)
        except Exception as exc:
            failed_run = running_run.model_copy(
                update={
                    "status": RunStatus.FAILED,
                    "finished_at": datetime.now(UTC),
                    "latest_message": str(exc),
                }
            )
            self._registry.save_run(failed_run)
            raise

        final_status = (
            RunStatus.SUCCEEDED if result.status == "succeeded" else RunStatus.FAILED
        )
        finished_run = running_run.model_copy(
            update={
                "status": final_status,
                "finished_at": datetime.now(UTC),
                "latest_message": result.message,
                "result_summary": result.summary,
            }
        )
        self._registry.save_run(finished_run)
        return finished_run

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

        cancelled_run = run.model_copy(
            update={
                "status": RunStatus.CANCELLED,
                "finished_at": datetime.now(UTC),
                "latest_message": "Run cancelled",
            }
        )
        self._registry.save_run(cancelled_run)
