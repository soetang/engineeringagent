"""Tests for the git worktree workspace provider."""

import os
import subprocess
from pathlib import Path

from developer.workspaces.models import WorkspaceSpec, WorkspaceStatus
from developer.workspaces.services.file_registry import FileWorkspaceRegistry
from developer.workspaces.adapters.git_worktree_provider import (
    GitWorktreeWorkspaceProvider,
)


def _git_env() -> dict[str, str]:
    """Return git author env suitable for temporary test commits."""
    env = os.environ.copy()
    env.update(
        {
            "GIT_AUTHOR_NAME": "Test User",
            "GIT_AUTHOR_EMAIL": "test@example.com",
            "GIT_COMMITTER_NAME": "Test User",
            "GIT_COMMITTER_EMAIL": "test@example.com",
        }
    )
    return env


def _run_git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """Run a git command for a temporary repository."""
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
        env=_git_env(),
    )


def _init_repo(repo: Path) -> None:
    """Create a small repository with one commit on main."""
    repo.mkdir(parents=True)
    _run_git(repo, "init", "-b", "main")
    (repo / "README.md").write_text("start\n", encoding="utf-8")
    _run_git(repo, "add", "README.md")
    _run_git(repo, "commit", "-m", "initial")


def test_git_worktree_provider_creates_worktree_and_records_metadata(tmp_path) -> None:
    """Provider should create an isolated worktree and persist the session."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    registry = FileWorkspaceRegistry(tmp_path / "state")
    provider = GitWorktreeWorkspaceProvider(tmp_path / "workspaces", registry)

    workspace = provider.create(
        WorkspaceSpec(
            provider="git_worktree",
            repo_path=str(repo),
            base_branch="main",
            task_id="task 123",
        )
    )

    worktree_path = Path(workspace.execution_target.location)
    assert workspace.status is WorkspaceStatus.READY
    assert workspace.execution_target.kind == "local_path"
    assert worktree_path.exists()
    assert (worktree_path / ".git").exists()
    assert workspace.metadata["base_branch"] == "main"
    assert workspace.metadata["task_id"] == "task 123"
    assert workspace.metadata["branch_name"].startswith("developer/task-123/")
    assert registry.get_workspace(workspace.id) == workspace


def test_git_worktree_provider_stores_absolute_execution_paths(
    tmp_path, monkeypatch
) -> None:
    """Provider should persist absolute paths for downstream execution."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    monkeypatch.chdir(tmp_path)

    registry = FileWorkspaceRegistry(tmp_path / "state")
    provider = GitWorktreeWorkspaceProvider(Path("developer-workspaces"), registry)

    workspace = provider.create(
        WorkspaceSpec(
            provider="git_worktree",
            repo_path="repo",
            base_branch="main",
            task_id="task-123",
        )
    )

    execution_path = Path(workspace.execution_target.location)
    assert workspace.execution_target.kind == "local_path"
    assert execution_path.is_absolute() is True
    assert workspace.execution_target.metadata["repo_path"] == str(repo.resolve())
