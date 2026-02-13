from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Sequence


def run_process(
    args: str | Sequence[str],
    *,
    cwd: Path,
    capture_output: bool = False,
    text: bool = False,
    shell: bool = False,
) -> subprocess.CompletedProcess[str]:
    """Execute a process with a deterministic repository cwd."""
    return subprocess.run(
        args,
        cwd=cwd,
        capture_output=capture_output,
        text=text,
        shell=shell,
    )
