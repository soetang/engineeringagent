"""Agent execution adapters and their direct import surface."""

import importlib
from collections.abc import Callable

from engineeringagent.ports import AgentRunRequest, AgentRunner
from .contracts import (
    AgentBackend,
    AgentBackendError,
    AgentBackendFailureDetails,
    AgentBackendRunResult,
    AgentOutputValidationError,
    RequestRunAgentBackend,
)
from .helpers import classify_backend_exception, describe_action, preflight
from .registry import (
    build_backend_scaffold_manifest,
    default_backend_id,
    list_backends,
    resolve_backend_id,
)
from .runtime import resolve_agent_strategy, run_agent, run_agent_request


class ConfiguredAgentRunner(AgentRunner):
    """Delegate agent execution to the configured adapter runtime."""

    def __init__(
        self,
        *,
        run_agent_fn: Callable[..., object] | None = None,
    ) -> None:
        if run_agent_fn is None:
            self._run_agent_fn = _default_run_agent
        else:
            self._run_agent_fn = run_agent_fn

    def run(self, request: AgentRunRequest) -> object:
        """Execute one configured agent request."""
        return self._run_agent_fn(
            request.project_root,
            request.prompt,
            output_type=request.output_type,
            max_validation_retries=request.max_validation_retries,
        )


def _default_run_agent(*args: object, **kwargs: object) -> object:
    runtime = importlib.import_module("engineeringagent.adapters.agents.runtime")
    return runtime.run_agent(*args, **kwargs)

__all__ = [
    "AgentBackend",
    "AgentBackendError",
    "AgentBackendFailureDetails",
    "AgentBackendRunResult",
    "AgentOutputValidationError",
    "ConfiguredAgentRunner",
    "RequestRunAgentBackend",
    "build_backend_scaffold_manifest",
    "classify_backend_exception",
    "default_backend_id",
    "describe_action",
    "list_backends",
    "preflight",
    "resolve_agent_strategy",
    "resolve_backend_id",
    "run_agent",
    "run_agent_request",
]
