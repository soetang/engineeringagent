from __future__ import annotations

import subprocess
from pathlib import Path


def run_shell_command(
    project_root: Path,
    command: str,
    *,
    capture_output: bool = True,
    text: bool = True,
) -> subprocess.CompletedProcess[str]:
    """Run a shell command from loop orchestration.

    Args:
        project_root: Repository root used as command cwd.
        command: Shell command string to execute.
        capture_output: Whether to capture stdout/stderr.
        text: Whether command streams are decoded as text.

    Returns:
        Completed process from the shell command invocation.
    """
    return subprocess.run(
        command,
        shell=True,
        cwd=project_root,
        capture_output=capture_output,
        text=text,
        check=False,
    )
