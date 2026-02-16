from __future__ import annotations

import subprocess
from pathlib import Path


DEFAULT_OPENCODE_AGENT = "engineeringagent"


def start_agent(
    project_root: Path,
    prompt: str,
    *,
    agent: str = DEFAULT_OPENCODE_AGENT,
    format: str | None = None,
    session: str | None = None,
    capture_output: bool = True,
    text: bool = True,
) -> subprocess.CompletedProcess[str]:
    """Run an OpenCode agent with deterministic defaults.

    Args:
        project_root: Repository root used as command working directory.
        prompt: Prompt passed to the OpenCode agent.
        agent: Agent name for ``opencode run --agent``.
        format: Optional OpenCode output format (e.g. "json").
        session: Optional OpenCode session identifier for same-session followups.
        capture_output: Whether to capture stdout/stderr.
        text: Whether command streams are decoded as text.

    Returns:
        Completed process from the OpenCode invocation.
    """
    command: list[str] = ["opencode", "run"]
    if session:
        command.extend(["--session", session])
    if format:
        command.extend(["--format", format])
    command.extend(["--agent", agent, prompt])

    return subprocess.run(
        command,
        cwd=project_root,
        capture_output=capture_output,
        text=text,
    )


def run_shell_command(
    project_root: Path,
    command: str,
    *,
    capture_output: bool = True,
    text: bool = True,
) -> subprocess.CompletedProcess[str]:
    """Run a shell command from loop orchestration.

    Args:
        project_root: Repository root used as command working directory.
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
    )
