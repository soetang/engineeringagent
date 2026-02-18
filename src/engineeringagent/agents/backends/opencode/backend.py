from __future__ import annotations

from pathlib import Path

from engineeringagent.agents.contracts import (
    AgentBackendError,
    AgentBackendFailureDetails,
    AgentBackendRunResult,
)

from .client import DEFAULT_OPENCODE_AGENT, start_agent


class OpenCodeAgentBackend:
    """Agent backend adapter for OpenCode.

    This backend is intentionally small: it is responsible only for invoking the
    subprocess runner and extracting (text, session_id) for same-session retries.
    Structured output prompting, JSON parsing, and Pydantic validation are owned
    by `engineeringagent.agents.run_agent`.
    """

    def __init__(
        self,
        *,
        agent: str = DEFAULT_OPENCODE_AGENT,
        format: str | None = None,  # pylint: disable=redefined-builtin
    ) -> None:
        self._agent = agent
        self._format = format

    @property
    def name(self) -> str:
        """Backend identifier used in error messages and telemetry."""
        return "opencode"

    def run(
        self,
        project_root: Path,
        prompt: str,
        *,
        session_id: str | None = None,
    ) -> AgentBackendRunResult:
        """Run the OpenCode agent and return a backend-normalized result."""
        proc = start_agent(
            project_root,
            prompt,
            agent=self._agent,
            format=self._format,
            session=session_id,
        )

        if proc.returncode != 0:
            raise AgentBackendError(
                backend=self.name,
                message="opencode run failed",
                process=AgentBackendFailureDetails(
                    returncode=proc.returncode,
                    stdout=proc.stdout,
                    stderr=proc.stderr,
                    command_args=list(proc.args),
                ),
            )

        if self._format == "json":
            text_payload = proc.text_payload
            if not isinstance(text_payload, str) or not text_payload.strip():
                raise AgentBackendError(
                    backend=self.name,
                    message="opencode json output missing final text payload",
                    process=AgentBackendFailureDetails(
                        returncode=proc.returncode,
                        stdout=proc.stdout,
                        stderr=proc.stderr,
                        command_args=list(proc.args),
                    ),
                    backend_metadata={"session_id": proc.session_id}
                    if proc.session_id
                    else None,
                )

            return AgentBackendRunResult(
                text=text_payload,
                session_id=proc.session_id,
            )

        output = (proc.stdout or "") + (proc.stderr or "")
        return AgentBackendRunResult(text=output)
