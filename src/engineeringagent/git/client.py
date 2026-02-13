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
    )
