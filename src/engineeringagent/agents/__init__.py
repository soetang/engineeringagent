"""Canonical agent invocation boundary.

This package is the stable callsite-facing surface for running an agent.

Feature FEAT-109 will migrate production code to use `run_agent(...)` so that
backend specifics (OpenCode today, others later) remain encapsulated.
"""

from engineeringagent.agents.api import run_agent
from engineeringagent.agents.contracts import (
    AgentBackend,
    AgentBackendError,
    AgentBackendFailureDetails,
    AgentBackendRunResult,
    AgentOutputValidationError,
)

__all__ = [
    "AgentBackend",
    "AgentBackendError",
    "AgentBackendFailureDetails",
    "AgentBackendRunResult",
    "AgentOutputValidationError",
    "run_agent",
]
