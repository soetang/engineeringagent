from __future__ import annotations

from pathlib import Path
from typing import Callable, Sequence

from pydantic import BaseModel, ConfigDict

from .contracts import (
    CustomRuleManifest,
    CustomRuleManifestEntry,
    FitnessRuleMetadata,
    FitnessRuleResult,
    RuleAdapter,
    RuleSource,
    load_custom_rule_manifest,
)

DEFAULT_CUSTOM_RULE_MANIFEST = Path("harness/fitness_functions/rules.yaml")


class FitnessRuleDefinition(BaseModel):
    """Executable definition for one registered fitness rule."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    metadata: FitnessRuleMetadata
    origin: str
    python_callable: Callable[[Path], FitnessRuleResult | dict[str, object]] | None = (
        None
    )
    command: tuple[str, ...] | None = None
    config_file: Path | None = None
    timeout_seconds: int | None = None
    env: dict[str, str] | None = None


def custom_manifest_path(project_root: Path) -> Path:
    """Return the default custom-rule manifest path for a repository."""
    return project_root / DEFAULT_CUSTOM_RULE_MANIFEST


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
    active_definitions = load_custom_rule_definitions(
        project_root,
        manifest_path=manifest_path,
    )

    _raise_on_duplicate_rule_ids(active_definitions)
    return sorted(
        active_definitions, key=lambda definition: definition.metadata.rule_id
    )


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
    manifest = _load_manifest(project_root, manifest_path=manifest_path)
    if manifest is None:
        return []

    resolved_manifest, custom_manifest = manifest
    resolved_project_root = project_root.resolve()
    resolved_manifest_dir = resolved_manifest.resolve().parent
    return [
        _definition_from_custom_entry(
            entry,
            manifest_path=resolved_manifest,
            resolved_project_root=resolved_project_root,
            resolved_manifest_dir=resolved_manifest_dir,
            index=index,
        )
        for index, entry in enumerate(custom_manifest.rules)
    ]


def _definition_from_custom_entry(
    entry: CustomRuleManifestEntry,
    *,
    manifest_path: Path,
    resolved_project_root: Path,
    resolved_manifest_dir: Path,
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
        config_file=_resolve_config_file_path(
            entry.config_file,
            resolved_project_root=resolved_project_root,
            resolved_manifest_dir=resolved_manifest_dir,
            manifest_path=manifest_path,
        ),
        timeout_seconds=entry.timeout_seconds,
        env=dict(entry.env) if entry.env is not None else None,
    )


def _load_manifest(
    project_root: Path,
    *,
    manifest_path: Path | None = None,
) -> tuple[Path, CustomRuleManifest] | None:
    resolved_manifest = manifest_path or custom_manifest_path(project_root)
    if not resolved_manifest.is_absolute():
        resolved_manifest = project_root / resolved_manifest
    if not resolved_manifest.exists():
        return None

    return resolved_manifest, load_custom_rule_manifest(resolved_manifest)


def _resolve_config_file_path(
    config_file: str | None,
    *,
    resolved_project_root: Path,
    resolved_manifest_dir: Path,
    manifest_path: Path,
) -> Path | None:
    if config_file is None:
        return None

    resolved_config_path = (resolved_manifest_dir / config_file).resolve()
    try:
        resolved_config_path.relative_to(resolved_project_root)
    except ValueError as exc:
        raise ValueError(
            "config_file must resolve within project root: "
            f"{config_file} (manifest: {manifest_path})"
        ) from exc

    return resolved_config_path


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
