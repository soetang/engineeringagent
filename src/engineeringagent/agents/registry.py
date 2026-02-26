from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from engineeringagent.agents.backends.codex import CodexAgentBackend
from engineeringagent.agents.backends.codex.scaffold import (
    build_codex_scaffold_manifest,
)
from engineeringagent.agents.backends.opencode import OpenCodeAgentBackend
from engineeringagent.agents.backends.opencode.scaffold import (
    build_opencode_scaffold_manifest,
)
from engineeringagent.agents.contracts import RequestRunAgentBackend
from engineeringagent.config import resolve_agents_backend_id

BackendFactory = Callable[[], RequestRunAgentBackend]
BackendScaffoldManifestFactory = Callable[[str], dict[str, str]]
_DEFAULT_BACKEND_ID = "opencode"
_BACKEND_FACTORIES: dict[str, BackendFactory] = {
    "codex": CodexAgentBackend,
    "opencode": OpenCodeAgentBackend,
}

_BACKEND_SCAFFOLD_MANIFEST_FACTORIES: dict[str, BackendScaffoldManifestFactory] = {
    "codex": build_codex_scaffold_manifest,
    "opencode": build_opencode_scaffold_manifest,
}


def default_backend_id() -> str:
    """Return the deterministic registry default backend id."""
    if _DEFAULT_BACKEND_ID not in _BACKEND_FACTORIES:
        available_backends = ", ".join(list_backends())
        raise ValueError(
            "default agent backend id is not registered "
            f"({_DEFAULT_BACKEND_ID!r}); available backends: {available_backends}"
        )
    return _DEFAULT_BACKEND_ID


def list_backends() -> tuple[str, ...]:
    """Return stable backend ids for selection UIs and validation."""
    return tuple(sorted(_BACKEND_FACTORIES))


def resolve_backend_id(project_root: Path) -> str:
    """Resolve active backend id from repo config and registry defaults."""
    configured_backend_id = resolve_agents_backend_id(project_root)
    backend_id = configured_backend_id or default_backend_id()

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


def build_backend_scaffold_manifest(
    *,
    backend_id: str,
    agent_model: str,
) -> dict[str, str]:
    """Build backend-contributed init scaffold files for `backend_id`."""
    try:
        build_manifest = _BACKEND_SCAFFOLD_MANIFEST_FACTORIES[backend_id]
    except KeyError as exc:
        available_backends = ", ".join(list_backends())
        raise ValueError(
            f"unknown agent backend id {backend_id!r}; "
            f"available backends: {available_backends}"
        ) from exc
    return build_manifest(agent_model)
