"""Domain-owned orchestration for workspace-backed implementation runs."""

from __future__ import annotations

from uuid import uuid4

from developer.orchestrators.runs.models import (
    ImplementationWorkspacePlan,
    ImplementationWorkspaceRunOutcome,
    ImplementationWorkspaceRunRequest,
    WorkspaceRunCommand,
)
from developer.orchestrators.runs.protocols import (
    BranchInspectionPort,
    PublishedTaskBranchView,
    TaskPublicationStore,
    WorkspaceRunPort,
)

IMPLEMENTATION_AGENT_KIND = "implementation"


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
        publication = self._publication_store.get_task_publication(
            request.task.task_name,
            request.task.task_path,
        )
        plan = self._build_plan(request, publication)
        run_result = self._workspace_runner.run(
            WorkspaceRunCommand(
                repo_path=request.repo_path,
                base_branch=plan.base_branch,
                task_id=request.task.task_id,
                workspace_metadata=plan.workspace_metadata,
                agent_kind=IMPLEMENTATION_AGENT_KIND,
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
        publication: PublishedTaskBranchView | None,
    ) -> ImplementationWorkspacePlan:
        """Resolve the workspace branch plan for one run."""
        base_branch = self._branch_inspector.get_current_branch(request.repo_path)
        task_branch_name = self._resolve_task_branch(request, publication)
        workspace_start_point = self._resolve_workspace_start_point(
            publication=publication,
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
                "task_input": request.normalized_task_input,
                "task_id": request.task.task_id,
                "task_name": request.task.task_name,
                "task_path": request.task.task_path,
                "task_branch_name": task_branch_name,
                "max_iterations": request.max_iterations,
            },
        )

    def _resolve_task_branch(
        self,
        request: ImplementationWorkspaceRunRequest,
        publication: PublishedTaskBranchView | None,
    ) -> str:
        """Reuse a published branch when available, otherwise avoid collisions."""
        if publication is not None:
            return publication.branch_name

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
        publication: PublishedTaskBranchView | None,
        base_branch: str,
    ) -> str:
        """Choose the ref used to seed the disposable workspace branch."""
        if publication is not None:
            return publication.branch_name
        return base_branch
