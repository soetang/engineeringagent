from __future__ import annotations

import json
import subprocess
from pathlib import Path

from pydantic import BaseModel, ConfigDict


DEFAULT_OPENCODE_AGENT = "engineeringagent"


class OpenCodeAgentRunResult(BaseModel):
    """Structured OpenCode invocation result.

    This wrapper exists to keep OpenCode-protocol parsing under the opencode module
    boundary. Callers may depend on stdout/stderr/returncode for logging, and may
    additionally consume `session_id` / `text_payload` when `format="json"`.
    """

    model_config = ConfigDict(frozen=True)

    args: list[str]
    returncode: int
    stdout: str
    stderr: str
    session_id: str | None = None
    text_payload: str | None = None


def _extract_json_session_and_last_text_payload(  # noqa: C901
    stdout: str,
) -> tuple[str | None, str | None]:
    """Extract (session_id, last text payload) from OpenCode JSON event stream.

    Returns (None, None) on any parsing/extraction failure.
    """

    raw = stdout.strip("\n")
    if not raw.strip():
        return None, None

    session_id: str | None = None
    candidates: list[str] = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            return None, None
        if not isinstance(event, dict):
            continue
        if session_id is None:
            maybe_session = event.get("sessionID")
            if isinstance(maybe_session, str) and maybe_session:
                session_id = maybe_session

        if event.get("type") != "text":
            continue
        part = event.get("part")
        if not isinstance(part, dict):
            continue
        text = part.get("text")
        if isinstance(text, str):
            candidates.append(text)

    if session_id is None or not candidates:
        return None, None
    return session_id, candidates[-1]


def start_agent(
    project_root: Path,
    prompt: str,
    *,
    agent: str = DEFAULT_OPENCODE_AGENT,
    format: str | None = None,  # pylint: disable=redefined-builtin
    session: str | None = None,
) -> OpenCodeAgentRunResult:
    """Run an OpenCode agent.

    Args:
        project_root: Repository root used as command working directory.
        prompt: Prompt passed to the OpenCode agent.
        agent: Agent name for ``opencode run --agent``.
        format: Optional OpenCode output format (e.g. "json").
        session: Optional OpenCode session identifier for same-session followups.
    Returns:
        Completed process from the OpenCode invocation.
    """
    command: list[str] = ["opencode", "run"]
    if session:
        command.extend(["--session", session])
    if format:
        command.extend(["--format", format])
    command.extend(["--agent", agent, "--", prompt])

    proc = subprocess.run(
        command,
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
    )

    stdout = proc.stdout or ""
    stderr = proc.stderr or ""
    session_id: str | None = None
    text_payload: str | None = None
    if format == "json":
        session_id, text_payload = _extract_json_session_and_last_text_payload(stdout)

    return OpenCodeAgentRunResult(
        args=[str(item) for item in proc.args]
        if isinstance(proc.args, list)
        else [str(proc.args)],
        returncode=int(proc.returncode),
        stdout=stdout,
        stderr=stderr,
        session_id=session_id,
        text_payload=text_payload,
    )
