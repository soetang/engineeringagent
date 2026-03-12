"""Adapter-owned runtime for configured agent execution."""

from __future__ import annotations

from pathlib import Path
from typing import Any, TypeVar, overload

from engineeringagent.agents.contracts import AgentRunRequest, RequestRunAgentBackend

from .registry import get_backend_factory, resolve_backend_id

T = TypeVar("T")


def resolve_agent_strategy(project_root: Path) -> RequestRunAgentBackend:
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
    """Execute one normalized agent request."""
    if request.max_validation_retries < 0:
        raise ValueError("max_validation_retries must be >= 0")

    backend = resolve_agent_strategy(request.project_root)
    return backend.run_request(request)


@overload
def run_agent(
    project_root: Path,
    prompt: str,
    *,
    output_type: type[str] = str,
    max_validation_retries: int = 2,
) -> str: ...


@overload
def run_agent(
    project_root: Path,
    prompt: str,
    *,
    output_type: type[T],
    max_validation_retries: int = 2,
) -> T: ...


@overload
def run_agent(
    project_root: Path,
    prompt: str,
    *,
    output_type: Any,
    max_validation_retries: int = 2,
) -> Any: ...


def run_agent(
    project_root: Path,
    prompt: str,
    *,
    output_type: Any = str,
    max_validation_retries: int = 2,
) -> Any:
    """Run an agent through the adapter-owned runtime boundary."""
    request = AgentRunRequest(
        project_root=project_root,
        prompt=prompt,
        output_type=output_type,
        max_validation_retries=max_validation_retries,
    )
    return run_agent_request(request)
