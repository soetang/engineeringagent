from __future__ import annotations

import subprocess
from pathlib import Path


def status_porcelain(project_root: Path) -> subprocess.CompletedProcess[str]:
    """Return git porcelain status for the repository.

    Args:
        project_root: Repository root used as command working directory.

    Returns:
        Completed process from ``git status --porcelain``.
    """
    return subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
    )


def head_short(project_root: Path) -> subprocess.CompletedProcess[str]:
    """Return short git HEAD commit hash output.

    Args:
        project_root: Repository root used as command working directory.

    Returns:
        Completed process from ``git rev-parse --short HEAD``.
    """
    return subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
    )


def ls_files(project_root: Path) -> subprocess.CompletedProcess[str]:
    """Return tracked file list output.

    Args:
        project_root: Repository root used as command working directory.

    Returns:
        Completed process from ``git ls-files``.
    """

    return subprocess.run(
        ["git", "ls-files"],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
    )


def add_all(project_root: Path) -> subprocess.CompletedProcess[str]:
    """Stage repository changes for feature completion commit.

    Args:
        project_root: Repository root used as command working directory.

    Returns:
        Completed process from ``git add -A -- .``.
    """
    return subprocess.run(
        ["git", "add", "-A", "--", "."],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
    )


def commit(project_root: Path, message: str) -> subprocess.CompletedProcess[str]:
    """Create a deterministic completion commit with fixed local identity.

    Args:
        project_root: Repository root used as command working directory.
        message: Commit subject/body passed to ``git commit -m``.

    Returns:
        Completed process from the git commit invocation.
    """
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
    """Install pre-commit git hooks for the repository.

    Args:
        project_root: Repository root used as command working directory.
        hook_type: Optional hook type (e.g. "commit-msg").

    Returns:
        Completed process from the ``pre-commit install`` invocation.
    """
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
    """Return `git diff --name-status` output for changed-path discovery.

    Args:
        project_root: Repository root used as command working directory.
        base: Optional base revision passed to `git diff`.
        head: Optional head revision passed to `git diff`.

    Returns:
        Completed process from the git diff invocation.
    """

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
