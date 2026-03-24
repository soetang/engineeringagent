"""Protocol interfaces for loop orchestrator dependencies."""

from typing import Any, Mapping, Protocol, Type

from pydantic import BaseModel

from .models import (
    AgentResult,
    CompletionResult,
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


class ImplementationTask(Protocol):
    """Task contract used by the implementation loop orchestrator."""

    @property
    def task_id(self) -> str:
        """Return the stable task identity."""
        ...

    @property
    def task_name(self) -> str:
        """Return the current task name."""
        ...

    @property
    def task_path(self) -> str | None:
        """Return the current task path when present."""
        ...

    def is_complete(self) -> CompletionResult:
        """Return whether the task is currently complete."""
        ...

    def get_branch_name(self) -> str:
        """Return the stable publication branch name for this task."""
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
