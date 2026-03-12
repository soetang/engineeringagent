"""Load effective repository configuration from filesystem-backed TOML sources."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from engineeringagent.domain.shared.repository_config import RepositoryConfig

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover - Python < 3.11 fallback
    import tomli as tomllib

_PYPROJECT_ENGINEERINGAGENT_TABLE = ("tool", "engineeringagent")
_PATHS_TABLE = "paths"
_AGENTS_TABLE = "agents"
_CODEX_TABLE = "codex"
_HARNESS_TABLE = "harness"
_CHECKS_TABLE = "checks"
_CHECKS_PATH_KEY = "path"
_DOCS_ROOT_KEY = "docs-root"


def load_repository_config(project_root: Path) -> RepositoryConfig:
    """Return effective repository config using dedicated-file precedence."""
    resolved_project_root = project_root.resolve()
    engineeringagent_path = resolved_project_root / "engineeringagent.toml"
    engineeringagent_local_path = resolved_project_root / "engineeringagent.local.toml"
    pyproject_path = resolved_project_root / "pyproject.toml"

    defaults_payload = RepositoryConfig().model_dump()
    merged_payload: dict[str, Any] = {}
    dedicated_present = engineeringagent_path.exists() or engineeringagent_local_path.exists()

    if engineeringagent_path.exists():
        merged_payload = _merge_dicts(
            merged_payload,
            _read_engineeringagent_document(engineeringagent_path),
        )
    if engineeringagent_local_path.exists():
        merged_payload = _merge_dicts(
            merged_payload,
            _read_engineeringagent_document(engineeringagent_local_path),
        )
    if not dedicated_present and pyproject_path.exists():
        merged_payload = _merge_dicts(
            merged_payload,
            _read_pyproject_document(pyproject_path),
        )

    paths_payload = dict(merged_payload.get(_PATHS_TABLE, {}))
    if _DOCS_ROOT_KEY in merged_payload:
        paths_payload.setdefault("docs_root", merged_payload[_DOCS_ROOT_KEY])
    checks_payload = _nested_table(merged_payload, (_HARNESS_TABLE, _CHECKS_TABLE))
    if _CHECKS_PATH_KEY in checks_payload:
        paths_payload.setdefault("harness_checks_path", checks_payload[_CHECKS_PATH_KEY])
    if "specifications_root" not in paths_payload and "docs_root" in paths_payload:
        paths_payload["specifications_root"] = (
            Path(str(paths_payload["docs_root"])) / "specifications"
        ).as_posix()

    agents_payload = dict(merged_payload.get(_AGENTS_TABLE, {}))
    if _CODEX_TABLE not in agents_payload:
        codex_payload = _nested_table(merged_payload, (_AGENTS_TABLE, _CODEX_TABLE))
        if codex_payload:
            agents_payload[_CODEX_TABLE] = codex_payload

    return RepositoryConfig.model_validate(
        {
            "paths": {**defaults_payload["paths"], **paths_payload},
            "agents": {**defaults_payload["agents"], **agents_payload},
        }
    )


def _read_engineeringagent_document(path: Path) -> dict[str, Any]:
    document = _load_toml(path)
    if document is None:
        return {}
    return document


def _read_pyproject_document(path: Path) -> dict[str, Any]:
    document = _load_toml(path)
    if document is None:
        return {}
    scoped = _nested_table(document, _PYPROJECT_ENGINEERINGAGENT_TABLE)
    return dict(scoped) if scoped else {}


def _load_toml(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        with path.open("rb") as handle:
            loaded = tomllib.load(handle)
    except tomllib.TOMLDecodeError as exc:
        raise ValueError(f"invalid TOML in {path}: {exc}") from exc
    if isinstance(loaded, dict):
        return loaded
    return None


def _nested_table(document: dict[str, Any], path: tuple[str, ...]) -> dict[str, Any]:
    current: Any = document
    for key in path:
        if not isinstance(current, dict):
            return {}
        current = current.get(key)
    return dict(current) if isinstance(current, dict) else {}


def _merge_dicts(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge_dicts(merged[key], value)
            continue
        merged[key] = value
    return merged
