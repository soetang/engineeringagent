from __future__ import annotations

import sys
import re
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

_AGENTS_TABLE = "agents"
_BACKEND_KEY = "backend"
_CODEX_TABLE = "codex"
_CODEX_PROFILE_KEY = "profile"
_CODEX_MODEL_KEY = "model"

_TOML_TABLE_HEADER_RE = re.compile(r"^\s*\[([^\]]+)\]\s*$")
_TOML_AGENTS_BACKEND_RE = re.compile(rf"^\s*{re.escape(_BACKEND_KEY)}\s*=")


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


def upsert_agents_backend_toml(  # noqa: C901
    *,
    content: str,
    backend_id: str,
    force: bool,
) -> tuple[str, bool]:
    """Insert or update `[agents] backend` in TOML content."""
    lines = _ensure_trailing_newline(content).splitlines()
    table_ranges: dict[str, tuple[int, int]] = {}
    table_order: list[tuple[str, int]] = []

    for index, line in enumerate(lines):
        match = _TOML_TABLE_HEADER_RE.match(line)
        if match is None:
            continue
        table_order.append((match.group(1).strip(), index))

    for table_index, (table_name, start) in enumerate(table_order):
        if table_index + 1 < len(table_order):
            end = table_order[table_index + 1][1]
        else:
            end = len(lines)
        table_ranges[table_name] = (start, end)

    agents_range = table_ranges.get(_AGENTS_TABLE)
    if agents_range is None:
        rendered = _ensure_trailing_newline(content).rstrip("\n")
        if rendered:
            rendered += "\n\n"
        rendered += f'[{_AGENTS_TABLE}]\n{_BACKEND_KEY} = "{backend_id}"\n'
        return rendered, True

    agents_start, agents_end = agents_range
    backend_line_index: int | None = None
    for index in range(agents_start + 1, agents_end):
        if _TOML_AGENTS_BACKEND_RE.match(lines[index]):
            backend_line_index = index
            break

    if backend_line_index is not None:
        current_line = lines[backend_line_index].strip()
        desired_line = f'{_BACKEND_KEY} = "{backend_id}"'
        if current_line == desired_line or not force:
            return _render_toml_lines(lines), False
        lines[backend_line_index] = desired_line
        return _render_toml_lines(lines), True

    insertion_index = agents_end
    while (
        insertion_index > agents_start + 1 and lines[insertion_index - 1].strip() == ""
    ):
        insertion_index -= 1
    lines.insert(insertion_index, f'{_BACKEND_KEY} = "{backend_id}"')
    return _render_toml_lines(lines), True


def write_init_backend_config(
    project_root: Path,
    *,
    backend_id: str,
    force: bool,
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
    if not changed:
        return (0, 1)

    config_path.write_text(rendered, encoding="utf-8")
    return (1, 0)


def _render_toml_lines(lines: list[str]) -> str:
    return _ensure_trailing_newline("\n".join(lines))


def _ensure_trailing_newline(value: str) -> str:
    return value.rstrip("\n") + "\n"


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

    engineeringagent_toml = project_root / "engineeringagent.toml"
    enabled = _harness_bool_from_engineeringagent_toml(
        engineeringagent_toml,
        table=table,
        key=key,
    )
    if enabled is not None:
        return enabled

    pyproject_toml = project_root / "pyproject.toml"
    enabled = _harness_bool_from_pyproject_toml(
        pyproject_toml,
        table=table,
        key=key,
    )
    if enabled is not None:
        return enabled

    return default


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


def resolve_agents_codex_profile(project_root: Path) -> str | None:
    """Resolve configured Codex backend profile.

    Precedence:
    - engineeringagent.toml[agents.codex]
    - pyproject.toml[tool.engineeringagent.agents.codex]
    - default: unset (None)
    """

    engineeringagent_toml = project_root / "engineeringagent.toml"
    profile = _agents_codex_option_from_engineeringagent_toml(
        engineeringagent_toml,
        key=_CODEX_PROFILE_KEY,
    )
    if profile is not None:
        return profile

    pyproject_toml = project_root / "pyproject.toml"
    return _agents_codex_option_from_pyproject_toml(
        pyproject_toml,
        key=_CODEX_PROFILE_KEY,
    )


def resolve_agents_codex_model(project_root: Path) -> str | None:
    """Resolve configured Codex backend model.

    Precedence:
    - engineeringagent.toml[agents.codex]
    - pyproject.toml[tool.engineeringagent.agents.codex]
    - default: unset (None)
    """

    engineeringagent_toml = project_root / "engineeringagent.toml"
    model = _agents_codex_option_from_engineeringagent_toml(
        engineeringagent_toml,
        key=_CODEX_MODEL_KEY,
    )
    if model is not None:
        return model

    pyproject_toml = project_root / "pyproject.toml"
    return _agents_codex_option_from_pyproject_toml(
        pyproject_toml,
        key=_CODEX_MODEL_KEY,
    )


def _docs_root_from_engineeringagent_toml(path: Path) -> Path | None:
    document = _load_toml(path)
    if document is None:
        return None
    return _normalize_docs_root(document.get(_DOCS_ROOT_KEY), source_path=path)


def _harness_bool_from_engineeringagent_toml(
    path: Path,
    *,
    table: str,
    key: str,
) -> bool | None:
    document = _load_toml(path)
    if document is None:
        return None

    harness_table = _maybe_table(document, _HARNESS_TABLE)
    if harness_table is None:
        return None
    setting_table = _maybe_table(harness_table, table)
    if setting_table is None:
        return None

    return _normalize_bool(
        setting_table.get(key),
        key_name=key,
        source_path=path,
        source_scope=f"[{_HARNESS_TABLE}.{table}]",
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


def _agents_codex_option_from_engineeringagent_toml(
    path: Path,
    *,
    key: str,
) -> str | None:
    document = _load_toml(path)
    if document is None:
        return None

    agents_table = _maybe_table(document, _AGENTS_TABLE)
    if agents_table is None:
        return None
    codex_table = _maybe_table(agents_table, _CODEX_TABLE)
    if codex_table is None:
        return None

    return _normalize_nonempty_string(
        codex_table.get(key),
        key_name=key,
        source_path=path,
        source_scope=f"[{_AGENTS_TABLE}.{_CODEX_TABLE}]",
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


def _harness_bool_from_pyproject_toml(
    path: Path,
    *,
    table: str,
    key: str,
) -> bool | None:
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
    setting_table = _maybe_table(harness_table, table)
    if setting_table is None:
        return None

    return _normalize_bool(
        setting_table.get(key),
        key_name=key,
        source_path=path,
        source_scope=f"[tool.engineeringagent.{_HARNESS_TABLE}.{table}]",
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


def _agents_codex_option_from_pyproject_toml(
    path: Path,
    *,
    key: str,
) -> str | None:
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
    codex_table = _maybe_table(agents_table, _CODEX_TABLE)
    if codex_table is None:
        return None

    return _normalize_nonempty_string(
        codex_table.get(key),
        key_name=key,
        source_path=path,
        source_scope=f"[tool.engineeringagent.{_AGENTS_TABLE}.{_CODEX_TABLE}]",
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
