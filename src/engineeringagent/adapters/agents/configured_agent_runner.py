"""Configured agent-runner adapter."""

from __future__ import annotations

from engineeringagent.agents import run_agent
from engineeringagent.ports import AgentRunRequest, AgentRunner


class ConfiguredAgentRunner(AgentRunner):
    """Delegate agent execution to the configured backend boundary."""

    def run(self, request: AgentRunRequest) -> object:
        """Execute one configured agent request."""
        return run_agent(
            request.project_root,
            request.prompt,
            output_type=request.output_type,
            max_validation_retries=request.max_validation_retries,
        )
