"""Local git-worktree-backed workspace provider."""

import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from developer.workspaces.models import (
    ExecutionTarget,
    WorkspaceSession,
    WorkspaceSpec,
    WorkspaceStatus,
)
from developer.workspaces.protocols import WorkspaceProvider, WorkspaceRunRegistry


class GitWorktreeWorkspaceProvider(WorkspaceProvider):
    """Provision local git worktrees as isolated execution workspaces."""

    def __init__(
        self,
        workspaces_root: Path,
        registry: WorkspaceRunRegistry,
    ) -> None:
        """Prepare the root directory used for created worktrees."""
        self._workspaces_root = workspaces_root
        self._registry = registry
        self._workspaces_root.mkdir(parents=True, exist_ok=True)

    def create(self, spec: WorkspaceSpec) -> WorkspaceSession:
        """Create a git worktree for the requested task."""
        repo_path = Path(spec.repo_path).resolve()
        workspace_id = uuid4().hex
        branch_name = self._build_branch_name(spec.task_id, workspace_id)
        worktree_path = (self._workspaces_root / workspace_id).resolve()

        subprocess.run(
            [
                "git",
                "worktree",
                "add",
                "-b",
                branch_name,
                str(worktree_path),
                spec.base_branch,
            ],
            cwd=repo_path,
            check=True,
            capture_output=True,
            text=True,
        )

        workspace = WorkspaceSession(
            id=workspace_id,
            provider="git_worktree",
            status=WorkspaceStatus.READY,
            created_at=datetime.now(UTC),
            execution_target=self._build_execution_target(repo_path, worktree_path),
            metadata={
                **spec.metadata,
                "branch_name": branch_name,
                "base_branch": spec.base_branch,
                "task_id": spec.task_id,
            },
        )
        self._registry.save_workspace(workspace)
        return workspace

    def get(self, workspace_id: str) -> WorkspaceSession:
        """Return one persisted workspace session."""
        return self._registry.get_workspace(workspace_id)

    def list(self) -> list[WorkspaceSession]:
        """Return all persisted workspace sessions."""
        return self._registry.list_workspaces()

    def destroy(self, workspace_id: str) -> None:
        """Remove the git worktree checkout and mark the session destroyed."""
        workspace = self._registry.get_workspace(workspace_id)
        worktree_path = workspace.execution_target.location
        repo_path = workspace.execution_target.metadata.get("repo_path")
        if not isinstance(repo_path, str):
            raise ValueError("Workspace metadata is missing worktree removal details")

        subprocess.run(
            ["git", "worktree", "remove", worktree_path],
            cwd=repo_path,
            check=True,
            capture_output=True,
            text=True,
        )

        destroyed = workspace.model_copy(update={"status": WorkspaceStatus.DESTROYED})
        self._registry.save_workspace(destroyed)

    def _build_branch_name(self, task_id: str, workspace_id: str) -> str:
        """Create a task-derived branch name safe for git refs."""
        cleaned_task_id = re.sub(r"[^A-Za-z0-9._-]+", "-", task_id).strip("-")
        normalized_task_id = cleaned_task_id or "task"
        return f"developer/{normalized_task_id}/{workspace_id}"

    def _build_execution_target(
        self, repo_path: Path, worktree_path: Path
    ) -> ExecutionTarget:
        """Build the execution target persisted for a git worktree."""
        return ExecutionTarget(
            kind="local_path",
            location=str(worktree_path),
            metadata={"repo_path": str(repo_path)},
        )
