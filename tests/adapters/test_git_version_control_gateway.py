from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from engineeringagent.adapters.vcs import GitCliVersionControlGateway
from engineeringagent.ports import CommitRequest, ResetRequest, VersionControlFailure


def test_diff_against_base_includes_requested_refs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pass the selected diff refs through to git."""
    captured: dict[str, object] = {}

    def _run(*args, **kwargs):  # type: ignore[no-untyped-def]
        captured["args"] = args
        captured["kwargs"] = kwargs
        return subprocess.CompletedProcess(args[0], 0, "A\tsrc/app.py\n", "")

    monkeypatch.setattr(
        "engineeringagent.adapters.vcs.git_version_control_gateway.subprocess.run",
        _run,
        raising=True,
    )

    result = GitCliVersionControlGateway().diff_against_base(
        tmp_path,
        base_ref="main",
        head_ref="feature",
    )

    assert result.summary_text == "A\tsrc/app.py\n"
    assert captured["args"] == (
        [
            "git",
            "diff",
            "--name-status",
            "--find-renames",
            "--diff-filter=AMDR",
            "main",
            "feature",
        ],
    )
    assert captured["kwargs"] == {
        "cwd": tmp_path,
        "capture_output": True,
        "text": True,
        "check": False,
    }


def test_diff_against_base_raises_on_git_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Raise a typed gateway failure when git diff exits non-zero."""
    def _run(*args, **kwargs):  # type: ignore[no-untyped-def]
        return subprocess.CompletedProcess(args[0], 1, "", "boom")

    monkeypatch.setattr(
        "engineeringagent.adapters.vcs.git_version_control_gateway.subprocess.run",
        _run,
        raising=True,
    )

    with pytest.raises(VersionControlFailure, match="boom"):
        GitCliVersionControlGateway().diff_against_base(tmp_path)


def test_commit_stages_and_commits_with_fixed_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Stage all files before committing with the deterministic identity."""
    calls: list[list[str]] = []

    def _run(*args, **kwargs):  # type: ignore[no-untyped-def]
        command = args[0]
        calls.append(command)
        if command[:3] == ["git", "add", "-A"]:
            return subprocess.CompletedProcess(command, 0, "", "")
        if command[:5] == ["git", "-c", "user.name=engineeringagent", "-c", "user.email=engineeringagent@local"]:
            return subprocess.CompletedProcess(command, 0, "[main abc123] msg\n", "")
        if command == ["git", "rev-parse", "--short", "HEAD"]:
            return subprocess.CompletedProcess(command, 0, "abc123\n", "")
        raise AssertionError(command)

    monkeypatch.setattr(
        "engineeringagent.adapters.vcs.git_version_control_gateway.subprocess.run",
        _run,
        raising=True,
    )

    result = GitCliVersionControlGateway().commit(
        CommitRequest(project_root=tmp_path, message="msg")
    )

    assert result.commit_created is True
    assert result.commit_sha == "abc123"
    assert result.failure_stage is None
    assert calls == [
        ["git", "add", "-A", "--", "."],
        [
            "git",
            "-c",
            "user.name=engineeringagent",
            "-c",
            "user.email=engineeringagent@local",
            "commit",
            "-m",
            "msg",
        ],
        ["git", "rev-parse", "--short", "HEAD"],
    ]


def test_commit_reports_git_add_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Return a staged failure result when `git add` fails."""
    def _run(*args, **kwargs):  # type: ignore[no-untyped-def]
        command = args[0]
        if command[:3] == ["git", "add", "-A"]:
            return subprocess.CompletedProcess(command, 1, "", "add failed")
        raise AssertionError(command)

    monkeypatch.setattr(
        "engineeringagent.adapters.vcs.git_version_control_gateway.subprocess.run",
        _run,
        raising=True,
    )

    result = GitCliVersionControlGateway().commit(
        CommitRequest(project_root=tmp_path, message="msg")
    )

    assert result.commit_created is False
    assert result.failure_stage == "git_add"
    assert result.stderr == "add failed"


def test_worktree_status_reports_dirty_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Normalize git porcelain output into a deterministic dirty flag."""

    def _run(*args, **kwargs):  # type: ignore[no-untyped-def]
        return subprocess.CompletedProcess(args[0], 0, " M src/app.py\n", "")

    monkeypatch.setattr(
        "engineeringagent.adapters.vcs.git_version_control_gateway.subprocess.run",
        _run,
        raising=True,
    )

    result = GitCliVersionControlGateway().worktree_status(tmp_path)

    assert result.dirty is True
    assert result.stdout == " M src/app.py\n"
    assert result.stderr == ""


def test_worktree_status_raises_on_git_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Surface git status failures through the typed gateway error."""

    def _run(*args, **kwargs):  # type: ignore[no-untyped-def]
        return subprocess.CompletedProcess(args[0], 128, "", "not a git repository")

    monkeypatch.setattr(
        "engineeringagent.adapters.vcs.git_version_control_gateway.subprocess.run",
        _run,
        raising=True,
    )

    with pytest.raises(VersionControlFailure, match="not a git repository"):
        GitCliVersionControlGateway().worktree_status(tmp_path)


def test_reset_hard_runs_reset_and_clean_then_reports_head_commit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Hard reset should clean the workspace and return the resolved head commit."""
    calls: list[list[str]] = []

    def _run(*args, **kwargs):  # type: ignore[no-untyped-def]
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
        "engineeringagent.adapters.vcs.git_version_control_gateway.subprocess.run",
        _run,
        raising=True,
    )

    result = GitCliVersionControlGateway().reset_hard(
        ResetRequest(project_root=tmp_path, target_ref="abc123")
    )

    assert result.reset_applied is True
    assert result.head_commit == "abc123"
    assert result.failure_stage is None
    assert calls == [
        ["git", "reset", "--hard", "abc123"],
        ["git", "clean", "-fd"],
        ["git", "rev-parse", "--short", "HEAD"],
    ]


def test_reset_hard_reports_clean_failure_without_resolving_head(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failed clean step should surface a deterministic reset failure."""
    calls: list[list[str]] = []

    def _run(*args, **kwargs):  # type: ignore[no-untyped-def]
        command = args[0]
        calls.append(command)
        if command[:3] == ["git", "reset", "--hard"]:
            return subprocess.CompletedProcess(command, 0, "reset ok\n", "")
        if command == ["git", "clean", "-fd"]:
            return subprocess.CompletedProcess(command, 1, "", "clean failed")
        raise AssertionError(command)

    monkeypatch.setattr(
        "engineeringagent.adapters.vcs.git_version_control_gateway.subprocess.run",
        _run,
        raising=True,
    )

    result = GitCliVersionControlGateway().reset_hard(
        ResetRequest(project_root=tmp_path, target_ref="abc123")
    )

    assert result.reset_applied is False
    assert result.head_commit is None
    assert result.failure_stage == "git_clean"
    assert result.stderr == "clean failed"
    assert calls == [
        ["git", "reset", "--hard", "abc123"],
        ["git", "clean", "-fd"],
    ]
