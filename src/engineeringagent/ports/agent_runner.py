"""Agent execution port used by orchestration code."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict


class AgentRunRequest(BaseModel):
    """Stable request envelope for one agent execution."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    project_root: Path
    prompt: str
    output_type: Any = str
    max_validation_retries: int = 2


class AgentRunner(Protocol):
    """Run an agent without exposing backend resolution details."""

    def run(self, request: AgentRunRequest) -> Any:
        """Execute one normalized agent request."""
        raise NotImplementedError
