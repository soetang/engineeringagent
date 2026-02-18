from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from engineeringagent.agents.backends.opencode import OpenCodeAgentBackend
from engineeringagent.agents.contracts import AgentBackend
from engineeringagent.config import resolve_agents_backend_id

BackendFactory = Callable[[bool], AgentBackend]
_DEFAULT_BACKEND_ID = "opencode"


def _create_opencode_backend(structured_output: bool) -> AgentBackend:
    return OpenCodeAgentBackend(format="json" if structured_output else None)


_BACKEND_FACTORIES: dict[str, BackendFactory] = {
    "opencode": _create_opencode_backend,
}


def list_backends() -> tuple[str, ...]:
    """Return stable backend ids for selection UIs and validation."""
    return tuple(sorted(_BACKEND_FACTORIES))


def resolve_backend_id(project_root: Path) -> str:
    """Resolve active backend id from repo config and registry defaults."""
    configured_backend_id = resolve_agents_backend_id(project_root)
    backend_id = configured_backend_id or _DEFAULT_BACKEND_ID

    if backend_id not in _BACKEND_FACTORIES:
        available_backends = ", ".join(list_backends())
        raise ValueError(
            "unknown agent backend id "
            f"{backend_id!r} configured at [agents].backend; "
            f"available backends: {available_backends}"
        )

    return backend_id


def get_backend_factory(backend_id: str) -> BackendFactory:
    """Return backend factory for the provided backend id."""
    try:
        return _BACKEND_FACTORIES[backend_id]
    except KeyError as exc:
        available_backends = ", ".join(list_backends())
        raise ValueError(
            f"unknown agent backend id {backend_id!r}; "
            f"available backends: {available_backends}"
        ) from exc
