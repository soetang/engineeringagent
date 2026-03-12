from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from engineeringagent.adapters.vcs import GitWorktreeManager
from engineeringagent.ports import WorkspaceResetRequest, WorkspaceState


def test_reset_to_last_accepted_runs_reset_and_clean_then_reports_head_commit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Workspace reset should clean the tree and return the resolved head commit."""
    calls: list[list[str]] = []

    def _run(*args, **_kwargs):  # type: ignore[no-untyped-def]
        command = args[0]
        calls.append(command)
        if command[:3] == ["git", "reset", "--hard"]:
            return subprocess.CompletedProcess(command, 0, "reset ok\n", "")
        if command == ["git", "clean", "-fd"]:
            return subprocess.CompletedProcess(command, 0, "clean ok\n", "")
        if command == ["git", "rev-parse", "--short", "HEAD"]:
            return subprocess.CompletedProcess(command, 0, "abc123\n", "")
        raise AssertionError(command)

    monkeypatch.setattr(
        "engineeringagent.adapters.vcs.git_worktree_manager.subprocess.run",
        _run,
        raising=True,
    )

    result = GitWorktreeManager().reset_to_last_accepted(
        WorkspaceResetRequest(workspace_path=tmp_path, target_ref="abc123")
    )

    assert result.reset_applied is True
    assert result.head_commit == "abc123"
    assert result.failure_stage is None
    assert calls == [
        ["git", "reset", "--hard", "abc123"],
        ["git", "clean", "-fd"],
        ["git", "rev-parse", "--short", "HEAD"],
    ]


def test_reset_to_last_accepted_reports_clean_failure_without_resolving_head(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failed clean step should surface a deterministic workspace failure."""
    calls: list[list[str]] = []

    def _run(*args, **_kwargs):  # type: ignore[no-untyped-def]
        command = args[0]
        calls.append(command)
        if command[:3] == ["git", "reset", "--hard"]:
            return subprocess.CompletedProcess(command, 0, "reset ok\n", "")
        if command == ["git", "clean", "-fd"]:
            return subprocess.CompletedProcess(command, 1, "", "clean failed")
        raise AssertionError(command)

    monkeypatch.setattr(
        "engineeringagent.adapters.vcs.git_worktree_manager.subprocess.run",
        _run,
        raising=True,
    )

    result = GitWorktreeManager().reset_to_last_accepted(
        WorkspaceResetRequest(workspace_path=tmp_path, target_ref="abc123")
    )

    assert result.reset_applied is False
    assert result.head_commit is None
    assert result.failure_stage == "git_clean"
    assert result.stderr == "clean failed"
    assert calls == [
        ["git", "reset", "--hard", "abc123"],
        ["git", "clean", "-fd"],
    ]


def test_get_state_reports_changed_paths_and_untracked_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Workspace state should normalize porcelain output into the port model."""

    def _run(*args, **_kwargs):  # type: ignore[no-untyped-def]
        command = args[0]
        assert command == ["git", "status", "--porcelain", "--untracked-files=all"]
        return subprocess.CompletedProcess(
            command,
            0,
            " M src/engineeringagent/application/workspace_recovery_service.py\n"
            "R  old.py -> new.py\n"
            "?? harness/checks.yaml\n",
            "",
        )

    monkeypatch.setattr(
        "engineeringagent.adapters.vcs.git_worktree_manager.subprocess.run",
        _run,
        raising=True,
    )

    result = GitWorktreeManager().get_state(tmp_path)

    assert result == WorkspaceState(
        clean=False,
        changed_paths=(
            "src/engineeringagent/application/workspace_recovery_service.py",
            "new.py",
            "harness/checks.yaml",
        ),
        has_untracked_files=True,
    )


def test_get_state_raises_when_git_status_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Workspace state lookup should fail loudly on git errors."""

    def _run(*args, **_kwargs):  # type: ignore[no-untyped-def]
        command = args[0]
        assert command == ["git", "status", "--porcelain", "--untracked-files=all"]
        return subprocess.CompletedProcess(command, 128, "", "fatal: not a git repository")

    monkeypatch.setattr(
        "engineeringagent.adapters.vcs.git_worktree_manager.subprocess.run",
        _run,
        raising=True,
    )

    with pytest.raises(RuntimeError, match="fatal: not a git repository"):
        GitWorktreeManager().get_state(tmp_path)
