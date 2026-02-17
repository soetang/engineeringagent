from __future__ import annotations

from pathlib import Path
from typing import Callable, Sequence

from pydantic import BaseModel, ConfigDict

from .contracts import (
    CustomRuleManifestEntry,
    FitnessRuleMetadata,
    FitnessRuleResult,
    RuleAdapter,
    RuleSource,
    load_custom_rule_manifest,
)

DEFAULT_CUSTOM_RULE_MANIFEST = Path("harness/fitness-functions/rules.yaml")


class FitnessRuleDefinition(BaseModel):
    """Executable definition for one registered fitness rule."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    metadata: FitnessRuleMetadata
    origin: str
    python_callable: Callable[[Path], FitnessRuleResult | dict[str, object]] | None = (
        None
    )
    command: tuple[str, ...] | None = None
    timeout_seconds: int | None = None
    env: dict[str, str] | None = None


def custom_manifest_path(project_root: Path) -> Path:
    """Return the default custom-rule manifest path for a repository."""
    return project_root / DEFAULT_CUSTOM_RULE_MANIFEST


def load_custom_rule_definitions(
    project_root: Path,
    *,
    manifest_path: Path | None = None,
) -> list[FitnessRuleDefinition]:
    """Load command-backed rules declared in the manifest.

    Args:
        project_root: Repository root used to resolve relative manifest paths.
        manifest_path: Optional override path to the custom rules manifest.

    Returns:
        Command-backed rule definitions, or an empty list when the
        manifest file does not exist.
    """
    resolved_manifest = manifest_path or custom_manifest_path(project_root)
    if not resolved_manifest.is_absolute():
        resolved_manifest = project_root / resolved_manifest

    if not resolved_manifest.exists():
        return []

    manifest = load_custom_rule_manifest(resolved_manifest)
    return [
        _definition_from_custom_entry(entry, resolved_manifest, index)
        for index, entry in enumerate(manifest.rules)
    ]


def build_rule_catalog(
    project_root: Path,
    *,
    manifest_path: Path | None = None,
) -> list[FitnessRuleDefinition]:
    """Build the active declaration-driven fitness-rule catalog.

    Catalog entries are sourced only from command-adapter manifest declarations.
    Catalog output is sorted by `rule_id` for deterministic listing and gate
    consumption.
    """
    resolved_manifest = manifest_path or custom_manifest_path(project_root)
    if not resolved_manifest.is_absolute():
        resolved_manifest = project_root / resolved_manifest
    if not resolved_manifest.exists():
        return []

    manifest = load_custom_rule_manifest(resolved_manifest)
    active_definitions = [
        _definition_from_custom_entry(entry, resolved_manifest, index)
        for index, entry in enumerate(manifest.rules)
    ]

    _raise_on_duplicate_rule_ids(active_definitions)
    return sorted(
        active_definitions, key=lambda definition: definition.metadata.rule_id
    )


def _definition_from_custom_entry(
    entry: CustomRuleManifestEntry,
    manifest_path: Path,
    index: int,
) -> FitnessRuleDefinition:
    metadata = FitnessRuleMetadata(
        rule_id=entry.rule_id,
        name=entry.name,
        summary=entry.summary,
        rationale=entry.rationale,
        remediation=entry.remediation,
        scope=entry.scope,
        severity=entry.severity,
        adapter=RuleAdapter.COMMAND,
        source=RuleSource.CUSTOM,
        side_effect_free=True,
    )
    return FitnessRuleDefinition(
        metadata=metadata,
        origin=f"custom:{manifest_path}:rules[{index}]",
        command=tuple(entry.command),
        timeout_seconds=entry.timeout_seconds,
        env=dict(entry.env) if entry.env is not None else None,
    )


def _raise_on_duplicate_rule_ids(definitions: Sequence[FitnessRuleDefinition]) -> None:
    occurrences: dict[str, list[str]] = {}
    for definition in definitions:
        occurrences.setdefault(definition.metadata.rule_id, []).append(
            definition.origin
        )

    duplicates = {
        rule_id: origins for rule_id, origins in occurrences.items() if len(origins) > 1
    }
    if not duplicates:
        return

    duplicate_parts = [
        f"{rule_id} ({', '.join(sorted(origins))})"
        for rule_id, origins in sorted(duplicates.items())
    ]
    raise ValueError(
        "duplicate fitness rule_id detected: " + "; ".join(duplicate_parts)
    )
