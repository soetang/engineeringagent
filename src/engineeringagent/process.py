from __future__ import annotations

import shlex
import subprocess
from pathlib import Path

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


def run_shell_command(
    project_root: Path,
    command: str,
    *,
    capture_output: bool = True,
    text: bool = True,
) -> subprocess.CompletedProcess[str]:
    """Run an argv-style command from loop orchestration.

    Args:
        project_root: Repository root used as command cwd.
        command: Command string to parse and execute as argv.
        capture_output: Whether to capture stdout/stderr.
        text: Whether command streams are decoded as text.

    Returns:
        Completed process from the argv invocation.
    """

    def _failed_result(returncode: int, stderr: str) -> subprocess.CompletedProcess[str]:
        completed_stdout = "" if capture_output and text else None
        completed_stderr = stderr if capture_output and text else None
        return subprocess.CompletedProcess(
            args=command,
            returncode=returncode,
            stdout=completed_stdout,
            stderr=completed_stderr,
        )

    try:
        argv = parse_command_argv(command)
    except ValueError as exc:
        return _failed_result(
            2,
            f"{exc}\nRemediation: provide a plain argv-style command without shell operators.\n",
        )

    try:
        return subprocess.run(
            argv,
            shell=False,
            cwd=project_root,
            capture_output=capture_output,
            text=text,
            check=False,
        )
    except FileNotFoundError:
        executable = argv[0]
        return _failed_result(
            127,
            (
                f"command executable not found: {executable}\n"
                "Remediation: install the executable or use an absolute/path-resolvable command.\n"
            ),
        )
