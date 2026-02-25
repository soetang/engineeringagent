from __future__ import annotations

from pathlib import Path
from typing import Any

from engineeringagent.agents.contracts import (
    AgentRunRequest,
    RequestRunAgentBackend,
)
from engineeringagent.agents.registry import get_backend_factory, resolve_backend_id


def resolve_agent_strategy(
    project_root: Path,
) -> RequestRunAgentBackend:
    """Resolve and construct the configured agent backend strategy once."""
    backend_id = resolve_backend_id(project_root)
    create_backend = get_backend_factory(backend_id)
    backend = create_backend()
    if not isinstance(backend, RequestRunAgentBackend):
        raise TypeError(
            f"agent backend {backend_id!r} must implement run_request(request)"
        )
    return backend


def run_agent_request(request: AgentRunRequest) -> Any:
    """Execute one normalized run-agent request."""
    if request.max_validation_retries < 0:
        raise ValueError("max_validation_retries must be >= 0")

    backend = resolve_agent_strategy(request.project_root)
    return backend.run_request(request)
