"""Agent execution adapters."""

from engineeringagent.ports import AgentRunRequest, AgentRunner

from .runtime import run_agent


class ConfiguredAgentRunner(AgentRunner):
    """Delegate agent execution to the configured adapter runtime."""

    def run(self, request: AgentRunRequest) -> object:
        """Execute one configured agent request."""
        return run_agent(
            request.project_root,
            request.prompt,
            output_type=request.output_type,
            max_validation_retries=request.max_validation_retries,
        )

__all__ = ["ConfiguredAgentRunner"]
