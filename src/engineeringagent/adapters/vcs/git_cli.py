from __future__ import annotations

import subprocess
from pathlib import Path


def ls_files(project_root: Path) -> subprocess.CompletedProcess[str]:
    """Return tracked file list output."""
    return subprocess.run(
        ["git", "ls-files"],
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
