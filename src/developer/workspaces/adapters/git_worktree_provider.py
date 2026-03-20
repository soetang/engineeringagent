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
        task_branch_name = str(spec.metadata.get("task_branch_name") or spec.task_id)
        branch_name = self._build_branch_name(task_branch_name, workspace_id)
        remote_name = str(spec.metadata.get("remote_name") or "origin")
        start_point = self._resolve_start_point(
            repo_path=repo_path,
            remote_name=remote_name,
            requested_start_point=str(
                spec.metadata.get("start_point") or spec.base_branch
            ),
        )
        worktree_path = (self._workspaces_root / workspace_id).resolve()

        self._run_git(
            repo_path,
            "worktree",
            "add",
            "-b",
            branch_name,
            str(worktree_path),
            start_point,
        )

        workspace = WorkspaceSession(
            id=workspace_id,
            provider="git_worktree",
            status=WorkspaceStatus.READY,
            created_at=datetime.now(UTC),
            execution_target=self._build_execution_target(repo_path, worktree_path),
            metadata={
                **spec.metadata,
                "workspace_branch_name": branch_name,
                "task_branch_name": task_branch_name,
                "base_branch": spec.base_branch,
                "task_id": spec.task_id,
                "remote_name": remote_name,
                "start_point": start_point,
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

        self._run_git(Path(repo_path), "worktree", "remove", worktree_path)

        destroyed = workspace.model_copy(update={"status": WorkspaceStatus.DESTROYED})
        self._registry.save_workspace(destroyed)

    def _build_branch_name(self, task_branch_name: str, workspace_id: str) -> str:
        """Create a disposable workspace branch from a stable task branch name."""
        cleaned_task_id = re.sub(r"[^A-Za-z0-9._/-]+", "-", task_branch_name).strip(
            "-/"
        )
        normalized_task_id = cleaned_task_id or "task"
        return f"developer/{normalized_task_id}/ws-{workspace_id}"

    def _resolve_start_point(
        self,
        repo_path: Path,
        remote_name: str,
        requested_start_point: str,
    ) -> str:
        """Resolve a valid git ref for the new disposable workspace branch."""
        if self._local_branch_exists(repo_path, requested_start_point):
            return requested_start_point
        if not self._remote_branch_exists(
            repo_path, remote_name, requested_start_point
        ):
            return requested_start_point
        self._run_git(repo_path, "fetch", remote_name, requested_start_point)
        return f"{remote_name}/{requested_start_point}"

    def _local_branch_exists(self, repo_path: Path, branch_name: str) -> bool:
        """Return whether the named branch exists locally."""
        result = subprocess.run(
            ["git", "show-ref", "--verify", "--quiet", f"refs/heads/{branch_name}"],
            cwd=repo_path,
            capture_output=True,
            text=True,
        )
        return result.returncode == 0

    def _remote_branch_exists(
        self, repo_path: Path, remote_name: str, branch_name: str
    ) -> bool:
        """Return whether the named branch exists on the remote."""
        result = subprocess.run(
            ["git", "ls-remote", "--heads", remote_name, branch_name],
            cwd=repo_path,
            capture_output=True,
            text=True,
        )
        return result.returncode == 0 and bool(result.stdout.strip())

    def _run_git(self, repo_path: Path, *args: str) -> None:
        """Run a git command for workspace lifecycle management."""
        subprocess.run(
            ["git", *args],
            cwd=repo_path,
            check=True,
            capture_output=True,
            text=True,
        )

    def _build_execution_target(
        self, repo_path: Path, worktree_path: Path
    ) -> ExecutionTarget:
        """Build the execution target persisted for a git worktree."""
        return ExecutionTarget(
            kind="local_path",
            location=str(worktree_path),
            metadata={"repo_path": str(repo_path)},
        )
