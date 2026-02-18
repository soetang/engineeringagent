from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover - Python < 3.11 fallback
    import tomli as tomllib


DEFAULT_DOCS_ROOT = "docs"
_DOCS_ROOT_KEY = "docs-root"

_SPECS_TABLE = "specs"
_ALLOW_DUPLICATE_DONE_BASE_IDS_BELOW_KEY = "allow-duplicate-done-base-ids-below"

_HARNESS_TABLE = "harness"
_HARNESS_FITNESS_TABLE = "fitness"
_HARNESS_PYTEST_TABLE = "pytest"

_AGENTS_TABLE = "agents"
_BACKEND_KEY = "backend"

_OPENCODE_REAL_SMOKE_KEY = "opencode-real-smoke"
_OPENCODE_INTEGRATION_KEY = "opencode-integration"


def resolve_docs_root(project_root: Path) -> Path:
    """Resolve docs root from TOML configuration with deterministic precedence.

    Precedence: engineeringagent.toml -> pyproject.toml[tool.engineeringagent] -> docs.

    Args:
        project_root: Repository root used as the base for relative docs-root values.

    Returns:
        Absolute docs-root path under project_root.

    Raises:
        ValueError: If TOML cannot be parsed or docs-root value is invalid.
    """
    engineeringagent_toml = project_root / "engineeringagent.toml"
    docs_root_value = _docs_root_from_engineeringagent_toml(engineeringagent_toml)
    if docs_root_value is not None:
        return project_root / docs_root_value

    pyproject_toml = project_root / "pyproject.toml"
    docs_root_value = _docs_root_from_pyproject_toml(pyproject_toml)
    if docs_root_value is not None:
        return project_root / docs_root_value

    return project_root / DEFAULT_DOCS_ROOT


def resolve_allow_duplicate_done_base_ids_below(project_root: Path) -> int | None:
    """Resolve legacy done-spec duplicate-id opt-out threshold.

    Precedence:
    - engineeringagent.toml[specs]
    - pyproject.toml[tool.engineeringagent.specs]
    - default: unset (None)

    Args:
        project_root: Repository root.

    Returns:
        Threshold integer or None when unset.

    Raises:
        ValueError: If TOML cannot be parsed or the configured value is invalid.
    """

    engineeringagent_toml = project_root / "engineeringagent.toml"
    threshold = _allow_duplicate_done_base_ids_below_from_engineeringagent_toml(
        engineeringagent_toml
    )
    if threshold is not None:
        return threshold

    pyproject_toml = project_root / "pyproject.toml"
    threshold = _allow_duplicate_done_base_ids_below_from_pyproject_toml(pyproject_toml)
    if threshold is not None:
        return threshold

    return None


def resolve_harness_fitness_opencode_real_smoke_enabled(project_root: Path) -> bool:
    """Resolve whether the real OpenCode smoke fitness rule is enabled.

    Precedence:
    - engineeringagent.toml[harness.fitness]
    - pyproject.toml[tool.engineeringagent.harness.fitness]
    - default: false

    Args:
        project_root: Repository root.

    Returns:
        True if enabled, otherwise False.

    Raises:
        ValueError: If TOML cannot be parsed or the configured value is invalid.
    """

    engineeringagent_toml = project_root / "engineeringagent.toml"
    enabled = _opencode_real_smoke_from_engineeringagent_toml(engineeringagent_toml)
    if enabled is not None:
        return enabled

    pyproject_toml = project_root / "pyproject.toml"
    enabled = _opencode_real_smoke_from_pyproject_toml(pyproject_toml)
    if enabled is not None:
        return enabled

    return False


def resolve_agents_backend_id(project_root: Path) -> str | None:
    """Resolve configured default agent backend id.

    Precedence:
    - engineeringagent.toml[agents]
    - pyproject.toml[tool.engineeringagent.agents]
    - default: unset (None)

    Args:
        project_root: Repository root.

    Returns:
        Backend id string when configured, otherwise None.

    Raises:
        ValueError: If TOML cannot be parsed or the configured value is invalid.
    """

    engineeringagent_toml = project_root / "engineeringagent.toml"
    backend_id = _agents_backend_id_from_engineeringagent_toml(engineeringagent_toml)
    if backend_id is not None:
        return backend_id

    pyproject_toml = project_root / "pyproject.toml"
    backend_id = _agents_backend_id_from_pyproject_toml(pyproject_toml)
    if backend_id is not None:
        return backend_id

    return None


def resolve_harness_pytest_opencode_integration_enabled(project_root: Path) -> bool:
    """Resolve whether OpenCode integration tests are enabled.

    Precedence:
    - engineeringagent.toml[harness.pytest]
    - pyproject.toml[tool.engineeringagent.harness.pytest]
    - default: false

    Args:
        project_root: Repository root.

    Returns:
        True if enabled, otherwise False.

    Raises:
        ValueError: If TOML cannot be parsed or the configured value is invalid.
    """

    engineeringagent_toml = project_root / "engineeringagent.toml"
    enabled = _opencode_integration_from_engineeringagent_toml(engineeringagent_toml)
    if enabled is not None:
        return enabled

    pyproject_toml = project_root / "pyproject.toml"
    enabled = _opencode_integration_from_pyproject_toml(pyproject_toml)
    if enabled is not None:
        return enabled

    return False


def _docs_root_from_engineeringagent_toml(path: Path) -> Path | None:
    document = _load_toml(path)
    if document is None:
        return None
    return _normalize_docs_root(document.get(_DOCS_ROOT_KEY), source_path=path)


def _opencode_real_smoke_from_engineeringagent_toml(path: Path) -> bool | None:
    document = _load_toml(path)
    if document is None:
        return None

    harness_table = _maybe_table(document, _HARNESS_TABLE)
    if harness_table is None:
        return None
    fitness_table = _maybe_table(harness_table, _HARNESS_FITNESS_TABLE)
    if fitness_table is None:
        return None

    return _normalize_bool(
        fitness_table.get(_OPENCODE_REAL_SMOKE_KEY),
        key_name=_OPENCODE_REAL_SMOKE_KEY,
        source_path=path,
        source_scope=f"[{_HARNESS_TABLE}.{_HARNESS_FITNESS_TABLE}]",
    )


def _opencode_integration_from_engineeringagent_toml(path: Path) -> bool | None:
    document = _load_toml(path)
    if document is None:
        return None

    harness_table = _maybe_table(document, _HARNESS_TABLE)
    if harness_table is None:
        return None
    pytest_table = _maybe_table(harness_table, _HARNESS_PYTEST_TABLE)
    if pytest_table is None:
        return None

    return _normalize_bool(
        pytest_table.get(_OPENCODE_INTEGRATION_KEY),
        key_name=_OPENCODE_INTEGRATION_KEY,
        source_path=path,
        source_scope=f"[{_HARNESS_TABLE}.{_HARNESS_PYTEST_TABLE}]",
    )


def _agents_backend_id_from_engineeringagent_toml(path: Path) -> str | None:
    document = _load_toml(path)
    if document is None:
        return None

    agents_table = _maybe_table(document, _AGENTS_TABLE)
    if agents_table is None:
        return None

    return _normalize_backend_id(
        agents_table.get(_BACKEND_KEY),
        source_path=path,
        source_scope=f"[{_AGENTS_TABLE}]",
    )


def _allow_duplicate_done_base_ids_below_from_engineeringagent_toml(
    path: Path,
) -> int | None:
    document = _load_toml(path)
    if document is None:
        return None

    specs_table = document.get(_SPECS_TABLE)
    if not isinstance(specs_table, dict):
        return None

    return _normalize_allow_duplicate_done_base_ids_below(
        specs_table.get(_ALLOW_DUPLICATE_DONE_BASE_IDS_BELOW_KEY),
        source_path=path,
        source_scope=f"[{_SPECS_TABLE}]",
    )


def _docs_root_from_pyproject_toml(path: Path) -> Path | None:
    document = _load_toml(path)
    if document is None:
        return None

    tool_config = document.get("tool")
    if not isinstance(tool_config, dict):
        return None

    engineeringagent_config = tool_config.get("engineeringagent")
    if not isinstance(engineeringagent_config, dict):
        return None

    return _normalize_docs_root(
        engineeringagent_config.get(_DOCS_ROOT_KEY),
        source_path=path,
        source_scope="[tool.engineeringagent]",
    )


def _opencode_real_smoke_from_pyproject_toml(path: Path) -> bool | None:
    document = _load_toml(path)
    if document is None:
        return None

    tool_config = _maybe_table(document, "tool")
    if tool_config is None:
        return None
    engineeringagent_config = _maybe_table(tool_config, "engineeringagent")
    if engineeringagent_config is None:
        return None

    harness_table = _maybe_table(engineeringagent_config, _HARNESS_TABLE)
    if harness_table is None:
        return None
    fitness_table = _maybe_table(harness_table, _HARNESS_FITNESS_TABLE)
    if fitness_table is None:
        return None

    return _normalize_bool(
        fitness_table.get(_OPENCODE_REAL_SMOKE_KEY),
        key_name=_OPENCODE_REAL_SMOKE_KEY,
        source_path=path,
        source_scope=f"[tool.engineeringagent.{_HARNESS_TABLE}.{_HARNESS_FITNESS_TABLE}]",
    )


def _opencode_integration_from_pyproject_toml(path: Path) -> bool | None:
    document = _load_toml(path)
    if document is None:
        return None

    tool_config = _maybe_table(document, "tool")
    if tool_config is None:
        return None
    engineeringagent_config = _maybe_table(tool_config, "engineeringagent")
    if engineeringagent_config is None:
        return None

    harness_table = _maybe_table(engineeringagent_config, _HARNESS_TABLE)
    if harness_table is None:
        return None
    pytest_table = _maybe_table(harness_table, _HARNESS_PYTEST_TABLE)
    if pytest_table is None:
        return None

    return _normalize_bool(
        pytest_table.get(_OPENCODE_INTEGRATION_KEY),
        key_name=_OPENCODE_INTEGRATION_KEY,
        source_path=path,
        source_scope=f"[tool.engineeringagent.{_HARNESS_TABLE}.{_HARNESS_PYTEST_TABLE}]",
    )


def _agents_backend_id_from_pyproject_toml(path: Path) -> str | None:
    document = _load_toml(path)
    if document is None:
        return None

    tool_config = _maybe_table(document, "tool")
    if tool_config is None:
        return None
    engineeringagent_config = _maybe_table(tool_config, "engineeringagent")
    if engineeringagent_config is None:
        return None

    agents_table = _maybe_table(engineeringagent_config, _AGENTS_TABLE)
    if agents_table is None:
        return None

    return _normalize_backend_id(
        agents_table.get(_BACKEND_KEY),
        source_path=path,
        source_scope=f"[tool.engineeringagent.{_AGENTS_TABLE}]",
    )


def _allow_duplicate_done_base_ids_below_from_pyproject_toml(path: Path) -> int | None:
    document = _load_toml(path)
    if document is None:
        return None

    tool_config = document.get("tool")
    if not isinstance(tool_config, dict):
        return None

    engineeringagent_config = tool_config.get("engineeringagent")
    if not isinstance(engineeringagent_config, dict):
        return None

    specs_config = engineeringagent_config.get(_SPECS_TABLE)
    if not isinstance(specs_config, dict):
        return None

    return _normalize_allow_duplicate_done_base_ids_below(
        specs_config.get(_ALLOW_DUPLICATE_DONE_BASE_IDS_BELOW_KEY),
        source_path=path,
        source_scope=f"[tool.engineeringagent.{_SPECS_TABLE}]",
    )


def _maybe_table(parent: dict[str, Any], key: str) -> dict[str, Any] | None:
    value = parent.get(key)
    if not isinstance(value, dict):
        return None
    return value


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


def _normalize_docs_root(
    raw_value: Any,
    *,
    source_path: Path,
    source_scope: str = "top-level",
) -> Path | None:
    if raw_value is None:
        return None

    if not isinstance(raw_value, str):
        raise ValueError(
            f"invalid docs-root in {source_path} ({source_scope}): expected string"
        )

    stripped = raw_value.strip()
    if not stripped:
        raise ValueError(
            f"invalid docs-root in {source_path} ({source_scope}): cannot be empty"
        )

    candidate = Path(stripped)
    if candidate.is_absolute():
        raise ValueError(
            f"invalid docs-root in {source_path} ({source_scope}): must be relative"
        )
    if any(part == ".." for part in candidate.parts):
        raise ValueError(
            f"invalid docs-root in {source_path} ({source_scope}): cannot contain '..'"
        )

    normalized_parts = [part for part in candidate.parts if part not in {"", "."}]
    if not normalized_parts:
        raise ValueError(
            f"invalid docs-root in {source_path} ({source_scope}): cannot be '.'"
        )

    return Path(*normalized_parts)


def _normalize_allow_duplicate_done_base_ids_below(
    raw_value: Any,
    *,
    source_path: Path,
    source_scope: str,
) -> int | None:
    if raw_value is None:
        return None

    if isinstance(raw_value, bool) or not isinstance(raw_value, int):
        raise ValueError(
            f"invalid allow-duplicate-done-base-ids-below in {source_path} ({source_scope}): expected int"
        )

    if raw_value < 0:
        raise ValueError(
            f"invalid allow-duplicate-done-base-ids-below in {source_path} ({source_scope}): must be >= 0"
        )

    return raw_value


def _normalize_bool(
    raw_value: Any,
    *,
    key_name: str,
    source_path: Path,
    source_scope: str,
) -> bool | None:
    if raw_value is None:
        return None

    if not isinstance(raw_value, bool):
        raise ValueError(
            f"invalid {key_name} in {source_path} ({source_scope}): expected bool"
        )

    return raw_value


def _normalize_backend_id(
    raw_value: Any,
    *,
    source_path: Path,
    source_scope: str,
) -> str | None:
    if raw_value is None:
        return None

    if not isinstance(raw_value, str):
        raise ValueError(
            f"invalid {_BACKEND_KEY} in {source_path} ({source_scope}): expected string"
        )

    backend_id = raw_value.strip()
    if not backend_id:
        raise ValueError(
            f"invalid {_BACKEND_KEY} in {source_path} ({source_scope}): cannot be empty"
        )

    return backend_id
