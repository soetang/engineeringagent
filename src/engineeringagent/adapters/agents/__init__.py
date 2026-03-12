"""Agent execution adapters."""

from collections.abc import Callable

from engineeringagent.ports import AgentRunRequest, AgentRunner

from .runtime import run_agent


class ConfiguredAgentRunner(AgentRunner):
    """Delegate agent execution to the configured adapter runtime."""

    def __init__(
        self,
        *,
        run_agent_fn: Callable[..., object] | None = None,
    ) -> None:
        self._run_agent_fn = run_agent if run_agent_fn is None else run_agent_fn

    def run(self, request: AgentRunRequest) -> object:
        """Execute one configured agent request."""
        return self._run_agent_fn(
            request.project_root,
            request.prompt,
            output_type=request.output_type,
            max_validation_retries=request.max_validation_retries,
        )

__all__ = ["ConfiguredAgentRunner"]
