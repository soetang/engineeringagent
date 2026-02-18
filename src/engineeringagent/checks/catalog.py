from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from .fitness.catalog import render_rule_catalog_markdown
from .fitness.registry import FitnessRuleDefinition, build_rule_catalog


def render_fitness_catalog(
    project_root: Path,
    *,
    manifest_path: Path | None = None,
    format: Literal["markdown", "json"] = "markdown",
) -> str:
    """Render the active fitness-rule catalog.

    Args:
        project_root: Repository root used to resolve relative paths.
        manifest_path: Optional custom manifest override.
        format: Render format: markdown|json.

    Returns:
        Rendered catalog content without a trailing newline.
    """

    catalog = build_rule_catalog(project_root, manifest_path=manifest_path)
    if format == "json":
        payload = [_fitness_catalog_entry(definition) for definition in catalog]
        return json.dumps(payload, indent=2, sort_keys=True)

    return render_rule_catalog_markdown(catalog)


def _fitness_catalog_entry(definition: FitnessRuleDefinition) -> dict[str, object]:
    """Serialize rule metadata as deterministic JSON payload."""

    metadata = definition.metadata
    return {
        "adapter": metadata.adapter.value,
        "name": metadata.name,
        "rationale": metadata.rationale,
        "remediation": metadata.remediation,
        "rule_id": metadata.rule_id,
        "scope": metadata.scope,
        "severity": metadata.severity.value,
        "side_effect_free": metadata.side_effect_free,
        "source": metadata.source.value,
        "summary": metadata.summary,
    }
