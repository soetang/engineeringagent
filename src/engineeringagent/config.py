from __future__ import annotations

import sys
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any, TypeVar, cast

from engineeringagent.adapters.config import load_repository_config

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover - Python < 3.11 fallback
    import tomli as tomllib


DEFAULT_DOCS_ROOT = "docs"
_DOCS_ROOT_KEY = "docs-root"

_HARNESS_TABLE = "harness"
_CHECKS_TABLE = "checks"
_CHECKS_PATH_KEY = "path"
DEFAULT_HARNESS_CHECKS_PATH = "harness/checks.yaml"
_PATHS_TABLE = "paths"
_HARNESS_ROOT_KEY = "harness_root"
_PROGRESS_ROOT_KEY = "progress_root"
_SPECIFICATIONS_ROOT_KEY = "specifications_root"
DEFAULT_HARNESS_ROOT = "harness"
DEFAULT_PROGRESS_ROOT = ".engineeringagent/progress"

_AGENTS_TABLE = "agents"
_BACKEND_KEY = "backend"
_CODEX_TABLE = "codex"
_CODEX_PROFILE_KEY = "profile"
_CODEX_MODEL_KEY = "model"
_PYPROJECT_ENGINEERINGAGENT_TABLE = ("tool", "engineeringagent")

_TOML_TABLE_HEADER_RE = re.compile(r"^\s*\[([^\]]+)\]\s*$")

DEFAULT_CODEX_PROFILE = "engineeringagent"

_ConfigValue = TypeVar("_ConfigValue")


def write_init_docs_root_config(
    project_root: Path,
    docs_dir: str,
    *,
    force: bool,
) -> tuple[int, int]:
    """Persist docs-root config during init when separate docs mode is used."""
    if docs_dir == DEFAULT_DOCS_ROOT:
        return (0, 0)

    config_path = project_root / "engineeringagent.toml"
    config_content = f'{_DOCS_ROOT_KEY} = "{docs_dir}"\n'
    if config_path.exists() and not force:
        return (0, 1)

    config_path.write_text(config_content, encoding="utf-8")
    return (1, 0)


def _upsert_string_key_in_table(
    *,
    content: str,
    table: str,
    key: str,
    value: str,
    force: bool,
) -> tuple[str, bool]:
    """Insert or update a string key in a TOML table."""
    lines = _ensure_trailing_newline(content).splitlines()
    table_ranges = _toml_table_ranges(lines)
    table_range = table_ranges.get(table)
    desired_line = f'{key} = "{value}"'

    if table_range is None:
        rendered = _ensure_trailing_newline(content).rstrip("\n")
        if rendered:
            rendered += "\n\n"
        rendered += f"[{table}]\n{desired_line}\n"
        return rendered, True

    table_start, table_end = table_range
    key_line_re = re.compile(rf"^\s*{re.escape(key)}\s*=")
    key_line_index: int | None = None
    for index in range(table_start + 1, table_end):
        if key_line_re.match(lines[index]):
            key_line_index = index
            break

    if key_line_index is not None:
        current_line = lines[key_line_index].strip()
        if current_line == desired_line or not force:
            return _render_toml_lines(lines), False
        lines[key_line_index] = desired_line
        return _render_toml_lines(lines), True

    insertion_index = table_end
    while insertion_index > table_start + 1 and lines[insertion_index - 1].strip() == "":
        insertion_index -= 1
    lines.insert(insertion_index, desired_line)
    return _render_toml_lines(lines), True


def upsert_agents_backend_toml(
    *,
    content: str,
    backend_id: str,
    force: bool,
) -> tuple[str, bool]:
    """Insert or update `[agents] backend` in TOML content."""
    return _upsert_string_key_in_table(
        content=content,
        table=_AGENTS_TABLE,
        key=_BACKEND_KEY,
        value=backend_id,
        force=force,
    )


def upsert_agents_codex_profile_toml(
    *,
    content: str,
    profile: str,
    force: bool,
) -> tuple[str, bool]:
    """Insert or update `[agents.codex] profile` in TOML content."""
    codex_table = f"{_AGENTS_TABLE}.{_CODEX_TABLE}"
    return _upsert_string_key_in_table(
        content=content,
        table=codex_table,
        key=_CODEX_PROFILE_KEY,
        value=profile,
        force=force,
    )


def write_init_backend_config(
    project_root: Path,
    *,
    backend_id: str,
    force: bool,
    codex_profile_force: bool = False,
) -> tuple[int, int]:
    """Persist `[agents] backend = "..."` in engineeringagent.toml."""
    config_path = project_root / "engineeringagent.toml"
    current_content = ""
    if config_path.exists():
        current_content = config_path.read_text(encoding="utf-8")

    rendered, changed = upsert_agents_backend_toml(
        content=current_content,
        backend_id=backend_id,
        force=force,
    )
    if backend_id == _CODEX_TABLE:
        effective_codex_profile_force = force or codex_profile_force
        rendered, codex_changed = upsert_agents_codex_profile_toml(
            content=rendered,
            profile=DEFAULT_CODEX_PROFILE,
            force=effective_codex_profile_force,
        )
        changed = changed or codex_changed

    if not changed:
        return (0, 1)

    config_path.write_text(rendered, encoding="utf-8")
    return (1, 0)


def _render_toml_lines(lines: list[str]) -> str:
    return _ensure_trailing_newline("\n".join(lines))


def _ensure_trailing_newline(value: str) -> str:
    return value.rstrip("\n") + "\n"


def _toml_table_ranges(lines: list[str]) -> dict[str, tuple[int, int]]:
    table_ranges: dict[str, tuple[int, int]] = {}
    table_order: list[tuple[str, int]] = []

    for index, line in enumerate(lines):
        match = _TOML_TABLE_HEADER_RE.match(line)
        if match is None:
            continue
        table_order.append((match.group(1).strip(), index))

    for table_index, (table_name, start) in enumerate(table_order):
        end = table_order[table_index + 1][1] if table_index + 1 < len(table_order) else len(lines)
        table_ranges[table_name] = (start, end)

    return table_ranges


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
    config = load_repository_config(project_root)
    return project_root / config.paths.docs_root


def resolve_harness_bool_setting(
    project_root: Path,
    *,
    table: str,
    key: str,
    default: bool = False,
) -> bool:
    """Resolve a bool setting under the harness table.

    Precedence:
    - engineeringagent.toml[harness.<table>]
    - pyproject.toml[tool.engineeringagent.harness.<table>]
    - default

    Args:
        project_root: Repository root.
        table: Harness sub-table name under ``harness``.
        key: Bool setting key under the selected harness table.
        default: Fallback value when the setting is unset.

    Returns:
        Resolved bool value.

    Raises:
        ValueError: If TOML cannot be parsed or the configured value is invalid.
    """

    return cast(
        bool,
        _resolve_preferred_project_config(
            project_root,
            engineeringagent_reader=lambda path: _harness_bool_from_engineeringagent_toml(
                path,
                table=table,
                key=key,
            ),
            pyproject_reader=lambda path: _harness_bool_from_pyproject_toml(
                path,
                table=table,
                key=key,
            ),
            default=default,
        ),
    )


def resolve_harness_checks_config_path(project_root: Path) -> Path:
    """Resolve checks config path from TOML configuration.

    Precedence:
    - engineeringagent.toml[harness.checks]
    - pyproject.toml[tool.engineeringagent.harness.checks]
    - default: harness/checks.yaml

    Args:
        project_root: Repository root used as the base for relative path values.

    Returns:
        Absolute checks config path under project_root.

    Raises:
        ValueError: If TOML cannot be parsed or the configured value is invalid.
    """

    checks_path = _resolve_preferred_project_config(
        project_root,
        engineeringagent_reader=_harness_checks_path_from_engineeringagent_toml,
        pyproject_reader=_harness_checks_path_from_pyproject_toml,
        default=Path(DEFAULT_HARNESS_CHECKS_PATH),
    )
    return project_root / cast(Path, checks_path)


def resolve_progress_root(project_root: Path) -> Path:
    """Resolve progress root from TOML configuration.

    Precedence:
    - engineeringagent.toml[paths]
    - pyproject.toml[tool.engineeringagent.paths]
    - default: .engineeringagent/progress

    Args:
        project_root: Repository root used as the base for relative path values.

    Returns:
        Absolute progress root path under project_root.

    Raises:
        ValueError: If TOML cannot be parsed or the configured value is invalid.
    """

    config = load_repository_config(project_root)
    return project_root / config.paths.progress_root


def resolve_specifications_root(project_root: Path) -> Path:
    """Resolve the specifications root from TOML configuration.

    Precedence:
    - engineeringagent.toml[paths].specifications_root
    - pyproject.toml[tool.engineeringagent.paths].specifications_root
    - fallback: <docs_root>/spec

    Args:
        project_root: Repository root used as the base for relative path values.

    Returns:
        Absolute specifications root path under project_root.

    Raises:
        ValueError: If TOML cannot be parsed or the configured value is invalid.
    """

    config = load_repository_config(project_root)
    return project_root / config.paths.specifications_root


def resolve_harness_root(project_root: Path) -> Path:
    """Resolve harness root from TOML configuration.

    Precedence:
    - engineeringagent.toml[paths]
    - pyproject.toml[tool.engineeringagent.paths]
    - default: harness

    Args:
        project_root: Repository root used as the base for relative path values.

    Returns:
        Absolute harness root path under project_root.

    Raises:
        ValueError: If TOML cannot be parsed or the configured value is invalid.
    """

    config = load_repository_config(project_root)
    return project_root / config.paths.harness_root


def repo_relative_label(project_root: Path, target_path: Path) -> str:
    """Render target_path relative to project_root when possible."""
    try:
        return target_path.relative_to(project_root).as_posix()
    except ValueError:
        return str(target_path)


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

    return load_repository_config(project_root).agents.backend


def resolve_agents_codex_profile(project_root: Path) -> str | None:
    """Resolve configured Codex backend profile.

    Precedence:
    - engineeringagent.toml[agents.codex]
    - pyproject.toml[tool.engineeringagent.agents.codex]
    - default: unset (None)
    """

    return load_repository_config(project_root).agents.codex.profile


def resolve_agents_codex_profile_in_engineeringagent_toml(
    project_root: Path,
) -> str | None:
    """Resolve Codex profile configured only in engineeringagent.toml."""

    engineeringagent_toml = project_root / "engineeringagent.toml"
    if not engineeringagent_toml.exists():
        return None
    document = _read_engineeringagent_document(engineeringagent_toml)
    codex_table = _table_at_path(document, (_AGENTS_TABLE, _CODEX_TABLE))
    if codex_table is None:
        return None
    return _normalize_nonempty_string(
        codex_table.get(_CODEX_PROFILE_KEY),
        key_name=_CODEX_PROFILE_KEY,
        source_path=engineeringagent_toml,
        source_scope=_toml_scope((_AGENTS_TABLE, _CODEX_TABLE)),
    )


def resolve_agents_codex_model(project_root: Path) -> str | None:
    """Resolve configured Codex backend model.

    Precedence:
    - engineeringagent.toml[agents.codex]
    - pyproject.toml[tool.engineeringagent.agents.codex]
    - default: unset (None)
    """

    return load_repository_config(project_root).agents.codex.model


def _resolve_preferred_project_config(
    project_root: Path,
    *,
    engineeringagent_reader: Callable[[Path], _ConfigValue],
    pyproject_reader: Callable[[Path], _ConfigValue],
    default: _ConfigValue,
) -> _ConfigValue:
    engineeringagent_value = engineeringagent_reader(
        project_root / "engineeringagent.toml"
    )
    if engineeringagent_value is not None:
        return engineeringagent_value

    pyproject_value = pyproject_reader(project_root / "pyproject.toml")
    if pyproject_value is not None:
        return pyproject_value

    return default


def _toml_scope(table_path: tuple[str, ...], *, default: str = "top-level") -> str:
    if not table_path:
        return default
    return f"[{'.'.join(table_path)}]"


def _table_at_path(
    document: dict[str, Any],
    table_path: tuple[str, ...],
) -> dict[str, Any] | None:
    current: dict[str, Any] | None = document
    for key in table_path:
        if current is None:
            return None
        current = _maybe_table(current, key)
    return current


def _read_toml_value(
    path: Path,
    *,
    table_path: tuple[str, ...] = (),
    key: str,
    top_level_scope: str = "top-level",
) -> tuple[Any, str] | None:
    document = _load_toml(path)
    if document is None:
        return None

    if table_path:
        table = _table_at_path(document, table_path)
        if table is None:
            return None
    else:
        table = document

    return table.get(key), _toml_scope(table_path, default=top_level_scope)


def _read_engineeringagent_document(path: Path) -> dict[str, Any]:
    document = _load_toml(path)
    if document is None:
        return {}
    return document


def _normalize_toml_value(
    path: Path,
    *,
    table_path: tuple[str, ...] = (),
    key: str,
    normalizer: Callable[[Any, str], _ConfigValue | None],
    top_level_scope: str = "top-level",
) -> _ConfigValue | None:
    resolved = _read_toml_value(
        path,
        table_path=table_path,
        key=key,
        top_level_scope=top_level_scope,
    )
    if resolved is None:
        return None
    raw_value, source_scope = resolved
    return normalizer(raw_value, source_scope)


def _docs_root_from_engineeringagent_toml(path: Path) -> Path | None:
    return _normalize_toml_value(
        path,
        key=_DOCS_ROOT_KEY,
        normalizer=lambda raw_value, source_scope: _normalize_docs_root(
            raw_value,
            source_path=path,
            source_scope=source_scope,
        ),
    )


def _harness_bool_from_engineeringagent_toml(
    path: Path,
    *,
    table: str,
    key: str,
) -> bool | None:
    return _normalize_toml_value(
        path,
        table_path=(_HARNESS_TABLE, table),
        key=key,
        normalizer=lambda raw_value, source_scope: _normalize_bool(
            raw_value,
            key_name=key,
            source_path=path,
            source_scope=source_scope,
        ),
    )


def _harness_checks_path_from_engineeringagent_toml(path: Path) -> Path | None:
    return _normalize_toml_value(
        path,
        table_path=(_HARNESS_TABLE, _CHECKS_TABLE),
        key=_CHECKS_PATH_KEY,
        normalizer=lambda raw_value, source_scope: _normalize_repo_local_path(
            raw_value,
            source_path=path,
            source_scope=source_scope,
        ),
    )


def _docs_root_from_pyproject_toml(path: Path) -> Path | None:
    return _normalize_toml_value(
        path,
        table_path=_PYPROJECT_ENGINEERINGAGENT_TABLE,
        key=_DOCS_ROOT_KEY,
        normalizer=lambda raw_value, source_scope: _normalize_docs_root(
            raw_value,
            source_path=path,
            source_scope=source_scope,
        ),
    )


def _harness_bool_from_pyproject_toml(
    path: Path,
    *,
    table: str,
    key: str,
) -> bool | None:
    return _normalize_toml_value(
        path,
        table_path=(*_PYPROJECT_ENGINEERINGAGENT_TABLE, _HARNESS_TABLE, table),
        key=key,
        normalizer=lambda raw_value, source_scope: _normalize_bool(
            raw_value,
            key_name=key,
            source_path=path,
            source_scope=source_scope,
        ),
    )


def _harness_checks_path_from_pyproject_toml(path: Path) -> Path | None:
    return _normalize_toml_value(
        path,
        table_path=(*_PYPROJECT_ENGINEERINGAGENT_TABLE, _HARNESS_TABLE, _CHECKS_TABLE),
        key=_CHECKS_PATH_KEY,
        normalizer=lambda raw_value, source_scope: _normalize_repo_local_path(
            raw_value,
            source_path=path,
            source_scope=source_scope,
        ),
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


def _normalize_nonempty_string(
    raw_value: Any,
    *,
    key_name: str,
    source_path: Path,
    source_scope: str,
) -> str | None:
    if raw_value is None:
        return None

    if not isinstance(raw_value, str):
        raise ValueError(
            f"invalid {key_name} in {source_path} ({source_scope}): expected string"
        )

    normalized = raw_value.strip()
    if not normalized:
        raise ValueError(
            f"invalid {key_name} in {source_path} ({source_scope}): cannot be empty"
        )

    return normalized


def _normalize_repo_local_path(
    raw_value: Any,
    *,
    source_path: Path,
    source_scope: str,
) -> Path | None:
    if raw_value is None:
        return None
    if not isinstance(raw_value, str):
        raise ValueError(
            f"invalid path in {source_path} ({source_scope}): expected string"
        )

    stripped = raw_value.strip()
    if not stripped:
        raise ValueError(
            f"invalid path in {source_path} ({source_scope}): cannot be empty"
        )

    candidate = Path(stripped)
    if candidate.is_absolute():
        raise ValueError(
            f"invalid path in {source_path} ({source_scope}): must be relative"
        )
    if any(part == ".." for part in candidate.parts):
        raise ValueError(
            f"invalid path in {source_path} ({source_scope}): cannot contain '..'"
        )

    normalized_parts = [part for part in candidate.parts if part not in {"", "."}]
    if not normalized_parts:
        raise ValueError(
            f"invalid path in {source_path} ({source_scope}): cannot be '.'"
        )

    return Path(*normalized_parts)
