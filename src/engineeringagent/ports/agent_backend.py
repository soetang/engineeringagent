"""Backend-owned agent contracts shared across the canonical ports layer."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict

from .agent_runner import AgentRunRequest


class AgentBackendRunResult(BaseModel):
    """Backend response used by normalized agent execution."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    text: str
    session_id: str | None = None


class AgentBackendFailureDetails(BaseModel):
    """Optional process details for backend failures."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    returncode: int | None = None
    stdout: str | None = None
    stderr: str | None = None
    command_args: list[str] | None = None


@runtime_checkable
class RequestRunAgentBackend(Protocol):
    """Single-path backend contract keyed by ``AgentRunRequest``."""

    @property
    def name(self) -> str:
        """Return backend identifier used in typed errors."""
        raise NotImplementedError

    def run_request(self, request: AgentRunRequest) -> Any:
        """Execute one normalized request and return text or parsed payload."""
        raise NotImplementedError


@runtime_checkable
class AgentBackend(Protocol):
    """Backend interface implemented by concrete agent runners."""

    @property
    def name(self) -> str:
        """Return a short backend identifier."""
        raise NotImplementedError

    def run(
        self,
        project_root: Path,
        prompt: str,
        *,
        session_id: str | None = None,
    ) -> AgentBackendRunResult:
        """Execute the backend and return raw text plus optional session id."""
        raise NotImplementedError


class AgentOutputValidationError(Exception):
    """Raised when structured agent output cannot be validated after retries."""

    def __init__(
        self,
        *,
        backend: str,
        attempts: int,
        last_text: str | None,
        error_summary: str,
        backend_metadata: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            f"Agent output validation failed after {attempts} attempt(s) "
            f"using backend {backend!r}: {error_summary}"
        )
        self.backend = backend
        self.attempts = attempts
        self.last_text = last_text
        self.error_summary = error_summary
        self.backend_metadata = backend_metadata or {}


class AgentBackendError(Exception):
    """Raised when an agent backend fails to execute successfully."""

    def __init__(
        self,
        *,
        backend: str,
        message: str,
        process: AgentBackendFailureDetails | None = None,
        backend_metadata: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(f"{backend}: {message}")
        self.backend = backend
        self.message = message
        self.process = process or AgentBackendFailureDetails()
        self.backend_metadata = backend_metadata or {}

    @property
    def returncode(self) -> int | None:
        """Optional process exit code (when available)."""
        return self.process.returncode

    @property
    def stdout(self) -> str | None:
        """Optional process standard output (when available)."""
        return self.process.stdout

    @property
    def stderr(self) -> str | None:
        """Optional process standard error output (when available)."""
        return self.process.stderr

    @property
    def command_args(self) -> list[str] | None:
        """Optional argv used to execute the backend process."""
        return self.process.command_args

    @property
    def output(self) -> str:
        """Combined stdout + stderr for convenience."""
        return (self.stdout or "") + (self.stderr or "")
