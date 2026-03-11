"""Shell-execution port used by orchestration code."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, ConfigDict


class CommandResult(BaseModel):
    """Stable result envelope for one shell-command execution."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    command: str
    returncode: int
    stdout: str
    stderr: str


class ShellRunner(Protocol):
    """Run one argv-style command without exposing subprocess details."""

    def run(self, project_root: Path, command: str) -> CommandResult:
        """Execute one command from the selected repository root."""
        raise NotImplementedError
