from __future__ import annotations

import subprocess
from pathlib import Path


DEFAULT_OPENCODE_AGENT = "engineeringagent"


def start_agent(
    project_root: Path,
    prompt: str,
    *,
    agent: str = DEFAULT_OPENCODE_AGENT,
    capture_output: bool = True,
    text: bool = True,
) -> subprocess.CompletedProcess[str]:
    """Run an OpenCode agent with deterministic defaults.

    Args:
        project_root: Repository root used as command working directory.
        prompt: Prompt passed to the OpenCode agent.
        agent: Agent name for ``opencode run --agent``.
        capture_output: Whether to capture stdout/stderr.
        text: Whether command streams are decoded as text.

    Returns:
        Completed process from the OpenCode invocation.
    """
    return subprocess.run(
        ["opencode", "run", "--agent", agent, prompt],
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
    """Run a custom implement shell command from loop orchestration.

    Args:
        project_root: Repository root used as command working directory.
        command: Shell command string passed by loop implement override.
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
