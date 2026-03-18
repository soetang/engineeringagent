"""Protocol interfaces for orchestrator dependencies."""

from typing import Type, Protocol
from pydantic import BaseModel

from .models import AgentResult, CompletionResult, GatePhase, GateResult


class PromptBuilder(Protocol):
    """Builds prompts from task-specific and attempt-specific injections."""

    def build(self, injections: dict) -> str:
        """Return the prompt text for the next agent run."""
        ...


class AgentRunner(Protocol):
    """Runs the agent for a prompt and returns an agent result."""

    def run(
        self, prompt: str, output_format: Type[BaseModel] | None = None
    ) -> AgentResult:
        """Execute the agent and return the parsed output."""
        ...


class GateRunner(Protocol):
    """Runs quality gates for a given phase."""

    def check(self, phase: GatePhase) -> GateResult:
        """Run the requested phase gate and return pass/fail state."""
        ...


class CompletionJudge(Protocol):
    """Determines whether the orchestrator should continue iterating."""

    def is_complete(self) -> CompletionResult:
        """Return whether the current result satisfies completion conditions."""
        ...
