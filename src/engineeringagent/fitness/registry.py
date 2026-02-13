from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence

from .contracts import (
    FitnessRuleResult,
    CustomRuleManifestEntry,
    FitnessRuleMetadata,
    RuleAdapter,
    RuleSeverity,
    RuleSource,
    load_custom_rule_manifest,
)
from .builtin_rules import (
    DEPENDENCY_DIRECTIONALITY_RULE_ID,
    LOOP_SUBPROCESS_BOUNDARY_RULE_ID,
    evaluate_dependency_directionality,
    evaluate_loop_subprocess_boundary,
)

DEFAULT_CUSTOM_RULE_MANIFEST = Path("harness/fitness-functions/rules.yaml")


@dataclass(frozen=True)
class FitnessRuleDefinition:
    """Executable definition for one registered fitness rule."""

    metadata: FitnessRuleMetadata
    origin: str
    python_callable: Callable[[Path], FitnessRuleResult | dict[str, object]] | None = (
        None
    )
    command: tuple[str, ...] | None = None
    timeout_seconds: int | None = None
    env: dict[str, str] | None = None


BUILTIN_RULE_DEFINITIONS: tuple[FitnessRuleDefinition, ...] = (
    FitnessRuleDefinition(
        metadata=FitnessRuleMetadata(
            rule_id=DEPENDENCY_DIRECTIONALITY_RULE_ID,
            name="Dependency directionality",
            summary="Enforce core module import direction boundaries.",
            rationale="Keeps orchestration and contracts layered for reviewability.",
            remediation="Refactor imports to follow the declared architecture boundaries.",
            scope="src/engineeringagent",
            severity=RuleSeverity.ERROR,
            adapter=RuleAdapter.PYTHON,
            source=RuleSource.BUILTIN,
            side_effect_free=True,
        ),
        origin=f"builtin:{DEPENDENCY_DIRECTIONALITY_RULE_ID}",
        python_callable=evaluate_dependency_directionality,
    ),
    FitnessRuleDefinition(
        metadata=FitnessRuleMetadata(
            rule_id=LOOP_SUBPROCESS_BOUNDARY_RULE_ID,
            name="Loop subprocess boundary",
            summary="Disallow direct subprocess calls in loop orchestration modules.",
            rationale="Centralizes command execution paths for consistent control.",
            remediation="Route command execution through approved adapter modules.",
            scope="src/engineeringagent/loop.py",
            severity=RuleSeverity.ERROR,
            adapter=RuleAdapter.PYTHON,
            source=RuleSource.BUILTIN,
            side_effect_free=True,
        ),
        origin=f"builtin:{LOOP_SUBPROCESS_BOUNDARY_RULE_ID}",
        python_callable=evaluate_loop_subprocess_boundary,
    ),
)


def builtin_rule_definitions() -> list[FitnessRuleDefinition]:
    """Return built-in fitness rule definitions."""
    return list(BUILTIN_RULE_DEFINITIONS)


def custom_manifest_path(project_root: Path) -> Path:
    """Return the default custom-rule manifest path for a repository."""
    return project_root / DEFAULT_CUSTOM_RULE_MANIFEST


def load_custom_rule_definitions(
    project_root: Path,
    *,
    manifest_path: Path | None = None,
) -> list[FitnessRuleDefinition]:
    """Load custom command-backed rules declared in the manifest.

    Args:
        project_root: Repository root used to resolve relative manifest paths.
        manifest_path: Optional override path to the custom rules manifest.

    Returns:
        Command-backed custom rule definitions, or an empty list when the
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
    builtin_rules: Sequence[FitnessRuleDefinition] | None = None,
    manifest_path: Path | None = None,
) -> list[FitnessRuleDefinition]:
    """Build the merged active fitness-rule catalog.

    The merged catalog includes built-in rules plus custom command-backed rules
    from the configured manifest. Catalog output is sorted by `rule_id` for
    deterministic listing and gate consumption.
    """
    builtins = (
        list(builtin_rules) if builtin_rules is not None else builtin_rule_definitions()
    )
    custom_rules = load_custom_rule_definitions(
        project_root,
        manifest_path=manifest_path,
    )
    merged = builtins + custom_rules
    _raise_on_duplicate_rule_ids(merged)
    return sorted(merged, key=lambda definition: definition.metadata.rule_id)


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
