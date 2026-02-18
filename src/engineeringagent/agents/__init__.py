"""Canonical agent invocation boundary.

This package is the stable callsite-facing surface for running an agent.

Feature FEAT-109 will migrate production code to use `run_agent(...)` so that
backend specifics (OpenCode today, others later) remain encapsulated.
"""

from engineeringagent.agents.api import (
    AgentBackend,
    AgentBackendError,
    AgentBackendFailureDetails,
    AgentBackendRunResult,
    AgentOutputValidationError,
    run_agent,
)

__all__ = [
    "AgentBackend",
    "AgentBackendError",
    "AgentBackendFailureDetails",
    "AgentBackendRunResult",
    "AgentOutputValidationError",
    "run_agent",
]
