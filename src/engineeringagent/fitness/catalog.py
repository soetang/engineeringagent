from __future__ import annotations

from pathlib import Path
from typing import Sequence

from .registry import FitnessRuleDefinition


def render_rule_catalog_markdown(definitions: Sequence[FitnessRuleDefinition]) -> str:
    """Render the active fitness-rule catalog as deterministic markdown."""
    lines: list[str] = [
        "# Fitness Rule Catalog",
        "",
        "This file is generated from the active fitness-rule registry.",
        "",
    ]

    if not definitions:
        lines.extend(["No active fitness rules found.", ""])
        return "\n".join(lines)

    lines.extend(
        [
            "## Active Rules",
            "",
            "| Rule ID | Severity | Adapter | Source | Scope | Summary |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for definition in definitions:
        metadata = definition.metadata
        lines.append(
            "| "
            f"`{metadata.rule_id}` | "
            f"{metadata.severity.value} | "
            f"{metadata.adapter.value} | "
            f"{metadata.source.value} | "
            f"`{metadata.scope}` | "
            f"{_escape_table_cell(metadata.summary)} |"
        )

    lines.extend(["", "## Rule Details", ""])
    for definition in definitions:
        metadata = definition.metadata
        lines.extend(
            [
                f"### `{metadata.rule_id}`",
                "",
                f"- Name: {metadata.name}",
                f"- Side-effect free: `{str(metadata.side_effect_free).lower()}`",
                f"- Rationale: {metadata.rationale}",
                f"- Remediation: {metadata.remediation}",
                "",
            ]
        )

    return "\n".join(lines)


def write_rule_catalog_markdown(output_path: Path, markdown: str) -> None:
    """Write markdown catalog output to disk."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(markdown, encoding="utf-8")


def _escape_table_cell(value: str) -> str:
    return value.replace("|", "\\|").strip()
