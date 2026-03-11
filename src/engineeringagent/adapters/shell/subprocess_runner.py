"""Subprocess-backed shell adapter."""

from __future__ import annotations

import shlex
import subprocess
from pathlib import Path

from engineeringagent.ports import CommandResult, ShellRunner

_UNSUPPORTED_SHELL_TOKENS = {
    "|",
    "||",
    "&",
    "&&",
    ";",
    ";;",
    "<",
    ">",
    "<<",
    ">>",
    "(",
    ")",
    "|&",
}


def parse_command_argv(command: str) -> tuple[str, ...]:
    """Parse one command string into argv and reject shell-only syntax."""
    if not isinstance(command, str):
        raise TypeError("command must be a string")

    normalized = command.strip()
    if not normalized:
        raise ValueError("command must be a non-empty argv-style string")

    lexer = shlex.shlex(normalized, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    lexer.commenters = ""
    try:
        tokens = list(lexer)
    except ValueError as exc:
        raise ValueError(f"command parse error: {exc}") from exc

    if not tokens:
        raise ValueError("command must be a non-empty argv-style string")

    disallowed: list[str] = []
    seen: set[str] = set()
    for token in tokens:
        if token in _UNSUPPORTED_SHELL_TOKENS and token not in seen:
            seen.add(token)
            disallowed.append(token)
    if disallowed:
        unique = ", ".join(disallowed)
        raise ValueError(
            "shell syntax is not supported in command strings "
            f"(found: {unique}). Provide a plain argv-style command."
        )

    return tuple(tokens)


class SubprocessShellRunner(ShellRunner):
    """Run argv-style commands through subprocess with normalized failures."""

    def run(self, project_root: Path, command: str) -> CommandResult:
        """Execute one command from the selected repository root."""
        try:
            argv = parse_command_argv(command)
        except ValueError as exc:
            return CommandResult(
                command=command,
                returncode=2,
                stdout="",
                stderr=(
                    f"{exc}\n"
                    "Remediation: provide a plain argv-style command without shell operators.\n"
                ),
            )

        try:
            proc = subprocess.run(
                argv,
                shell=False,
                cwd=project_root,
                capture_output=True,
                text=True,
                check=False,
            )
        except FileNotFoundError:
            return CommandResult(
                command=command,
                returncode=127,
                stdout="",
                stderr=(
                    f"command executable not found: {argv[0]}\n"
                    "Remediation: install the executable or use an absolute/path-resolvable command.\n"
                ),
            )

        return CommandResult(
            command=command,
            returncode=proc.returncode,
            stdout=proc.stdout or "",
            stderr=proc.stderr or "",
        )


def run_shell_command(project_root: Path, command: str) -> CommandResult:
    """Execute one command through the default subprocess-backed adapter."""
    return SubprocessShellRunner().run(project_root, command)
