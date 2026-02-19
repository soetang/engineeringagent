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
    StructuredOutputAgentBackend,
)
from engineeringagent.agents.helpers import (
    classify_backend_exception,
    describe_action,
    preflight,
)
from engineeringagent.agents.registry import (
    build_backend_scaffold_manifest,
    default_backend_id,
    list_backends,
    resolve_backend_id,
)

__all__ = [
    "AgentBackend",
    "AgentBackendError",
    "AgentBackendFailureDetails",
    "AgentBackendRunResult",
    "AgentOutputValidationError",
    "StructuredOutputAgentBackend",
    "build_backend_scaffold_manifest",
    "classify_backend_exception",
    "describe_action",
    "default_backend_id",
    "list_backends",
    "preflight",
    "resolve_backend_id",
    "run_agent",
]
