"""Domain-owned orchestration for workspace-backed implementation runs."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from developer.orchestrators.runs.models import (
    ImplementationWorkspacePlan,
    ImplementationWorkspaceRunOutcome,
    ImplementationWorkspaceRunRequest,
    WorkspaceRunCommand,
)
from developer.orchestrators.runs.protocols import (
    BranchInspectionPort,
    TaskPublicationStore,
    WorkspaceRunPort,
)


class ImplementationWorkspaceRunOrchestrator:
    """Plan and dispatch one implementation run through workspace infrastructure."""

    def __init__(
        self,
        publication_store: TaskPublicationStore,
        branch_inspector: BranchInspectionPort,
        workspace_runner: WorkspaceRunPort,
    ) -> None:
        """Store the ports required to plan and execute the run."""
        self._publication_store = publication_store
        self._branch_inspector = branch_inspector
        self._workspace_runner = workspace_runner

    def run(
        self,
        request: ImplementationWorkspaceRunRequest,
    ) -> ImplementationWorkspaceRunOutcome:
        """Build a workspace plan and delegate execution to the runtime port."""
        publication_branch = self._publication_store.get_task_publication_branch(
            request.task.task_name,
            request.task.task_path,
        )
        plan = self._build_plan(request, publication_branch)
        run_result = self._workspace_runner.run(
            WorkspaceRunCommand(
                repo_path=request.repo_path,
                workspace_provider=request.task.workspace_provider,
                base_branch=plan.base_branch,
                task_id=request.task.task_id,
                agent_kind=request.task.workspace_agent_kind,
                workspace_metadata=plan.workspace_metadata,
                run_context=plan.run_context,
            )
        )
        return ImplementationWorkspaceRunOutcome(
            task_name=request.task.task_name,
            workspace_id=run_result.workspace_id,
            run_id=run_result.run_id,
            status=run_result.status,
            latest_message=run_result.latest_message,
            metadata=run_result.metadata,
        )

    def _build_plan(
        self,
        request: ImplementationWorkspaceRunRequest,
        publication_branch: str | None,
    ) -> ImplementationWorkspacePlan:
        """Resolve the workspace branch plan for one run."""
        base_branch = self._resolve_base_branch(request)
        task_branch_name = self._resolve_task_branch(request, publication_branch)
        workspace_start_point = self._resolve_workspace_start_point(
            publication_branch=publication_branch,
            base_branch=base_branch,
        )
        return ImplementationWorkspacePlan(
            base_branch=base_branch,
            task_branch_name=task_branch_name,
            workspace_start_point=workspace_start_point,
            workspace_metadata={
                "task_id": request.task.task_id,
                "task_name": request.task.task_name,
                "task_path": request.task.task_path,
                "task_branch_name": task_branch_name,
                "remote_name": request.remote_name,
                "start_point": workspace_start_point,
            },
            run_context={
                "task_input": self._build_workspace_task_input(request),
                "task_id": request.task.task_id,
                "task_name": request.task.task_name,
                "task_path": request.task.task_path,
                "task_branch_name": task_branch_name,
                "max_iterations": request.max_iterations,
            },
        )

    def _resolve_base_branch(self, request: ImplementationWorkspaceRunRequest) -> str:
        """Prefer the task-defined base branch before consulting repository state."""
        if request.task.base_branch:
            return request.task.base_branch
        return self._branch_inspector.get_current_branch(request.repo_path)

    def _resolve_task_branch(
        self,
        request: ImplementationWorkspaceRunRequest,
        publication_branch: str | None,
    ) -> str:
        """Reuse a published branch when available, otherwise avoid collisions."""
        if publication_branch is not None:
            return publication_branch

        candidate = request.task.get_branch_name()
        if not self._branch_inspector.branch_exists(
            request.repo_path,
            candidate,
            remote_name=request.remote_name,
        ):
            return candidate
        return f"{candidate}-{uuid4().hex[:8]}"

    def _resolve_workspace_start_point(
        self,
        publication_branch: str | None,
        base_branch: str,
    ) -> str:
        """Choose the ref used to seed the disposable workspace branch."""
        if publication_branch is not None:
            return publication_branch
        return base_branch

    def _build_workspace_task_input(
        self,
        request: ImplementationWorkspaceRunRequest,
    ) -> str:
        """Build a workspace-safe task reference from the task's canonical path."""
        task_path = request.task.task_path
        if not task_path:
            raise ValueError("Workspace implementation run is missing task_path")

        repo_path = Path(request.repo_path).resolve()
        candidate = Path(task_path).expanduser()
        if candidate.is_absolute():
            try:
                candidate = candidate.resolve().relative_to(repo_path)
            except ValueError:
                return str(candidate.resolve())
        return str(candidate)
