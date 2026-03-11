from __future__ import annotations

import subprocess
from pathlib import Path


def status_porcelain(project_root: Path) -> subprocess.CompletedProcess[str]:
    """Return git porcelain status for the repository."""
    return subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
    )


def head_short(project_root: Path) -> subprocess.CompletedProcess[str]:
    """Return short git HEAD commit hash output."""
    return subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
    )


def ls_files(project_root: Path) -> subprocess.CompletedProcess[str]:
    """Return tracked file list output."""
    return subprocess.run(
        ["git", "ls-files"],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
    )


def add_all(project_root: Path) -> subprocess.CompletedProcess[str]:
    """Stage repository changes for feature completion commit."""
    return subprocess.run(
        ["git", "add", "-A", "--", "."],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
    )


def commit(project_root: Path, message: str) -> subprocess.CompletedProcess[str]:
    """Create a deterministic completion commit with fixed local identity."""
    return subprocess.run(
        [
            "git",
            "-c",
            "user.name=engineeringagent",
            "-c",
            "user.email=engineeringagent@local",
            "commit",
            "-m",
            message,
        ],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
    )


def precommit_install(
    project_root: Path,
    *,
    hook_type: str | None = None,
) -> subprocess.CompletedProcess[str]:
    """Install pre-commit git hooks for the repository."""
    command = ["pre-commit", "install"]
    if hook_type is not None:
        command.extend(["--hook-type", hook_type])

    return subprocess.run(
        command,
        cwd=project_root,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        check=False,
    )


def diff_name_status(
    project_root: Path,
    *,
    base: str | None = None,
    head: str | None = None,
) -> subprocess.CompletedProcess[str]:
    """Return `git diff --name-status` output for changed-path discovery."""
    command = [
        "git",
        "diff",
        "--name-status",
        "--find-renames",
        "--diff-filter=AMDR",
    ]
    if base is not None:
        command.append(base)
    if head is not None:
        command.append(head)

    return subprocess.run(
        command,
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
    )
