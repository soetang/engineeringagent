from __future__ import annotations

from pathlib import Path
from typing import Sequence

from .registry import FitnessRuleDefinition


def render_rule_catalog_markdown(
    definitions: Sequence[FitnessRuleDefinition],
    *,
    project_root: Path,
) -> str:
    """Render the active fitness-rule catalog as deterministic markdown."""
    lines: list[str] = [
        "# Fitness Rule Catalog",
        "",
        "This file is generated from active manifest-declared fitness rules.",
        "",
    ]

    if not definitions:
        lines.extend(["No active fitness rules found.", ""])
        return _join_markdown_lines(lines)

    lines.extend(
        [
            "## Active Rules",
            "",
            "| Rule ID | Severity | Adapter | Source | Scope | Config File | Summary |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for definition in definitions:
        metadata = definition.metadata
        table_config_file = _format_table_config_file(
            definition.config_file,
            project_root=project_root,
        )
        lines.append(
            "| "
            f"`{metadata.rule_id}` | "
            f"{metadata.severity.value} | "
            f"{metadata.adapter.value} | "
            f"{metadata.source.value} | "
            f"`{metadata.scope}` | "
            f"{table_config_file} | "
            f"{_escape_table_cell(metadata.summary)} |"
        )

    lines.extend(["", "## Rule Details", ""])
    for definition in definitions:
        metadata = definition.metadata
        config_file = format_config_file(
            definition.config_file, project_root=project_root
        )
        detail_lines = [
            f"### `{metadata.rule_id}`",
            "",
            f"- Name: {metadata.name}",
        ]
        if config_file is not None:
            detail_lines.append(f"- Config file: `{config_file}`")
        detail_lines.extend(
            [
                f"- Side-effect free: `{str(metadata.side_effect_free).lower()}`",
                f"- Rationale: {metadata.rationale}",
                f"- Remediation: {metadata.remediation}",
                "",
            ]
        )
        lines.extend(detail_lines)

    return _join_markdown_lines(lines)


def _escape_table_cell(value: str) -> str:
    return value.replace("|", "\\|").strip()


def _join_markdown_lines(lines: list[str]) -> str:
    return "\n".join(lines).rstrip("\n")


def _format_table_config_file(config_file: Path | None, *, project_root: Path) -> str:
    formatted_path = format_config_file(config_file, project_root=project_root)
    if formatted_path is None:
        return "-"
    return f"`{formatted_path}`"


def format_config_file(config_file: Path | None, *, project_root: Path) -> str | None:
    """Return a config-file path string, preferring a project-root-relative path."""
    if config_file is None:
        return None

    resolved_project_root = project_root.resolve()
    resolved_config_path = config_file.resolve()
    try:
        return resolved_config_path.relative_to(resolved_project_root).as_posix()
    except ValueError:
        return resolved_config_path.as_posix()
