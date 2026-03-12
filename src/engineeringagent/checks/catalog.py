from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from engineeringagent.adapters.quality.fitness.catalog import (
    format_config_file,
    render_rule_catalog_markdown,
)
from engineeringagent.adapters.quality.fitness.registry import (
    FitnessRuleDefinition,
    build_rule_catalog,
)


def render_fitness_catalog(
    project_root: Path,
    *,
    manifest_path: Path | None = None,
    format: Literal["markdown", "json"] = "markdown",  # pylint: disable=redefined-builtin
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
        payload = [
            _fitness_catalog_entry(definition, project_root=project_root)
            for definition in catalog
        ]
        return json.dumps(payload, indent=2, sort_keys=True)

    return render_rule_catalog_markdown(catalog, project_root=project_root)


def _fitness_catalog_entry(
    definition: FitnessRuleDefinition,
    *,
    project_root: Path,
) -> dict[str, object]:
    """Serialize rule metadata as deterministic JSON payload."""

    metadata = definition.metadata
    return {
        "adapter": metadata.adapter.value,
        "config_file": format_config_file(
            definition.config_file, project_root=project_root
        ),
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
