"""Protocol interfaces for orchestrator dependencies."""

from typing import Any, Mapping, Protocol, Type

from pydantic import BaseModel

from developer.tasks.protocol import ImplementationTask

from .models import (
    AgentResult,
    GatePhase,
    GateResult,
    ImplementationContext,
    IterationArtifact,
    RunPublicationResult,
)


class PromptBuilder(Protocol):
    """Builds prompts from orchestrator context."""

    def build(self, context: Mapping[str, Any]) -> str:
        """Return the prompt text for the next agent run."""
        ...


class AgentRunner(Protocol):
    """Runs the agent for a prompt and returns an agent result."""

    def run_agent(
        self,
        prompt: str,
        output_format: Type[BaseModel] | None = None,
    ) -> BaseModel | str:
        """Execute the agent and return the parsed output."""
        ...


class GateRunner(Protocol):
    """Runs quality gates for a given phase."""

    def check(
        self, phase: GatePhase, stop_on_first_failure: bool = False
    ) -> GateResult:
        """Run the requested phase gate and return pass/fail state."""
        ...


class ImplementationLifecycleObserver(Protocol):
    """Observer hooks around implementation loop lifecycle events."""

    def validate(self, context: ImplementationContext) -> None:
        """Run preflight validation before the implementation loop starts."""
        ...

    def on_iteration_passed(
        self,
        attempt: int,
        context: ImplementationContext,
        agent_result: AgentResult,
    ) -> IterationArtifact | None:
        """Handle a passing iteration before the next completion check."""
        ...

    def on_run_succeeded(
        self,
        context: ImplementationContext,
    ) -> RunPublicationResult | None:
        """Handle publication after the final success gate passes."""
        ...

    def on_run_failed(
        self,
        context: ImplementationContext,
        feedback: str | None,
    ) -> None:
        """Handle a failed run after all iterations are exhausted."""
        ...


__all__ = [
    "AgentRunner",
    "GateRunner",
    "ImplementationLifecycleObserver",
    "ImplementationTask",
    "PromptBuilder",
]
