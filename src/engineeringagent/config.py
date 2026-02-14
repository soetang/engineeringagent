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


def _docs_root_from_engineeringagent_toml(path: Path) -> Path | None:
    document = _load_toml(path)
    if document is None:
        return None
    return _normalize_docs_root(document.get(_DOCS_ROOT_KEY), source_path=path)


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
