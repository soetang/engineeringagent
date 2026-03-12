"""Legacy compatibility re-export for adapter-owned agent contracts."""

from engineeringagent.adapters.agents.contracts import (
    AgentBackend,
    AgentBackendError,
    AgentBackendFailureDetails,
    AgentBackendRunResult,
    AgentOutputValidationError,
    AgentRunRequest,
    RequestRunAgentBackend,
)

__all__ = [
    "AgentBackend",
    "AgentBackendError",
    "AgentBackendFailureDetails",
    "AgentBackendRunResult",
    "AgentOutputValidationError",
    "AgentRunRequest",
    "RequestRunAgentBackend",
]
