"""Integration tests for isolated workspace execution."""

import os
import subprocess
from pathlib import Path

import pytest

from developer.workspaces.adapters.default_execution_adapter_resolver import (
    DefaultWorkspaceExecutionAdapterResolver,
)
from developer.workspaces.adapters.git_worktree_provider import (
    GitWorktreeWorkspaceProvider,
)
from developer.workspaces.adapters.local_process_runner import (
    LocalProcessWorkspaceRunner,
)
from developer.workspaces.models import RunRequest, WorkspaceSession, WorkspaceSpec
from developer.workspaces.models import WorkspaceRunnableResult
from developer.workspaces.protocols import WorkspaceRunnableAgent
from developer.workspaces.services.file_registry import FileWorkspaceRegistry


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
    (repo / "app.py").write_text("print('before')\n", encoding="utf-8")
    (repo / "README.md").write_text("start\n", encoding="utf-8")
    _run_git(repo, "add", "app.py", "README.md")
    _run_git(repo, "commit", "-m", "initial")


class _FakeWorkspaceRunnableAgent(WorkspaceRunnableAgent):
    def run(
        self, request: RunRequest, workspace: WorkspaceSession
    ) -> WorkspaceRunnableResult:
        del request
        workspace_root = Path(workspace.execution_target.location)
        assert Path.cwd() == workspace_root
        Path("app.py").write_text("print('after')\n", encoding="utf-8")
        Path("new_file.txt").write_text("created\n", encoding="utf-8")
        return WorkspaceRunnableResult(
            status="succeeded",
            message="updated 2 files",
            summary="updated 2 files",
        )


class _StaticResolver:
    def __init__(self, agent: WorkspaceRunnableAgent) -> None:
        self._agent = agent

    def resolve(self, agent_kind: str) -> WorkspaceRunnableAgent:
        del agent_kind
        return self._agent


@pytest.mark.integration
def test_workspace_run_modifies_files_in_isolated_worktree(tmp_path) -> None:
    """Workspace runs should edit the worktree checkout, not the source repo."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    registry = FileWorkspaceRegistry(tmp_path / "state")
    provider = GitWorktreeWorkspaceProvider(tmp_path / "workspaces", registry)

    workspace = provider.create(
        WorkspaceSpec(
            provider="git_worktree",
            repo_path=str(repo),
            base_branch="main",
            task_id="task-123",
        )
    )

    runner = LocalProcessWorkspaceRunner(
        registry=registry,
        agent_resolver=_StaticResolver(_FakeWorkspaceRunnableAgent()),
        execution_adapter_resolver=DefaultWorkspaceExecutionAdapterResolver(),
    )

    run = runner.start_run(
        workspace_id=workspace.id,
        request=RunRequest(agent_kind="fake", context={}),
    )

    workspace_root = Path(workspace.execution_target.location)
    workspace_status = _run_git(workspace_root, "status", "--short").stdout

    assert run.status.value == "succeeded"
    assert (repo / "new_file.txt").exists() is False
    assert (repo / "app.py").read_text(encoding="utf-8") == "print('before')\n"
    assert (workspace_root / "app.py").read_text(encoding="utf-8") == "print('after')\n"
    assert (workspace_root / "new_file.txt").read_text(encoding="utf-8") == "created\n"
    assert " M app.py" in workspace_status
    assert "?? new_file.txt" in workspace_status
