"""Supported checks surface for non-checks production code.

Outside `src/engineeringagent/checks/**`, production modules must only depend on
this stable surface.
"""

from __future__ import annotations

from importlib import import_module
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from typing_extensions import Unpack

from engineeringagent.domain.quality import (
    ChangedPathsResult,
    ChecksRunResult,
    FALLBACK_CHANGE_DISCOVERY_REASON,
    HarnessCheckPhase,
    HarnessChecksDocument,
    list_check_groups,
    normalize_check_groups,
    reviewers_group_selected,
)
from engineeringagent.ports import VersionControlGateway

if TYPE_CHECKING:
    from engineeringagent.adapters.quality.runtime import _RunChecksKwargs
    from engineeringagent.adapters.quality.fitness.contracts import FitnessRuleResult

__all__ = [
    "ChangedPathsResult",
    "ChecksRunResult",
    "FALLBACK_CHANGE_DISCOVERY_REASON",
    "HarnessCheckPhase",
    "collect_changed_paths",
    "custom_rule_manifest_schema_from_model",
    "emit_fitness_result",
    "iter_feature_files",
    "list_check_groups",
    "load_markdown_frontmatter",
    "load_harness_checks_document",
    "normalize_groups",
    "resolve_feature_plan_path",
    "resolve_specifications_root",
    "render_fitness_catalog",
    "reviewer_decision_schema_from_model",
    "reviewers_group_selected",
    "run_checks",
    "validate_repository",
]

normalize_groups = normalize_check_groups


def collect_changed_paths(
    project_root: Path,
    *,
    base: str | None = None,
    head: str | None = None,
    version_control: VersionControlGateway | None = None,
) -> ChangedPathsResult:
    """Proxy to checks-owned changed-path discovery."""

    changed_paths = import_module("engineeringagent.adapters.quality.changed_paths")
    return changed_paths.collect_changed_paths(
        project_root,
        base=base,
        head=head,
        version_control=version_control,
    )


def run_checks(
    project_root: str | Path,
    *,
    phase: str,
    checks: list[str] | None = None,
    **kwargs: Unpack[_RunChecksKwargs],
) -> ChecksRunResult:
    """Proxy to the checks runtime without importing it during package init."""

    runtime = import_module("engineeringagent.adapters.quality.runtime")
    return runtime.run_checks(project_root, phase=phase, checks=checks, **kwargs)


def validate_repository(
    project_root: Path,
    *,
    schema_only: bool = False,
) -> list[str]:
    """Proxy to repository validation without importing checks internals at init."""

    validator = import_module("engineeringagent.adapters.quality.validation.validator")
    return validator.validate(project_root=project_root, schema_only=schema_only)


def load_harness_checks_document(
    project_root: Path,
    *,
    error_prefix: str,
    missing_context: str = "",
) -> tuple[HarnessChecksDocument | None, str | None]:
    """Proxy to config loading without importing specs during package init."""

    loader = import_module("engineeringagent.adapters.documents")
    return loader.load_harness_checks_document(
        project_root,
        error_prefix=error_prefix,
        missing_context=missing_context,
    )


def resolve_harness_bool_setting(
    project_root: Path,
    *,
    table: str,
    key: str,
    default: bool = False,
) -> bool:
    """Proxy to generic harness-bool config loading for harness-owned code."""

    config_runtime = import_module("engineeringagent.adapters.config")
    return config_runtime.resolve_harness_bool_setting(
        project_root,
        table=table,
        key=key,
        default=default,
    )


def emit_fitness_result(result: FitnessRuleResult) -> None:
    """Proxy to the fitness envelope helper without loading it during package init."""

    envelope = import_module("engineeringagent.adapters.quality.fitness.envelope")
    envelope.emit_fitness_result(result)


def custom_rule_manifest_schema_from_model() -> dict[str, Any]:
    """Proxy to the custom fitness manifest schema producer lazily."""

    contracts = import_module("engineeringagent.adapters.quality.fitness.contracts")
    return contracts.custom_rule_manifest_schema_from_model()


def render_fitness_catalog(
    project_root: Path,
    *,
    manifest_path: Path | None = None,
    format: Literal["markdown", "json"] = "markdown",  # pylint: disable=redefined-builtin
) -> str:
    """Proxy to catalog rendering without importing the catalog during package init."""

    catalog = import_module("engineeringagent.checks.catalog")
    return catalog.render_fitness_catalog(
        project_root,
        manifest_path=manifest_path,
        format=format,
    )


def resolve_feature_plan_path(
    spec_path: Path,
    feature: dict[str, Any],
) -> Path | None:
    """Proxy to bundled plan-path resolution without widening harness imports."""

    specification = import_module("engineeringagent.domain.specification")
    return specification.resolve_feature_plan_path(spec_path, feature)


def resolve_specifications_root(project_root: Path) -> Path:
    """Proxy to repository specifications-root resolution for harness code."""

    config_runtime = import_module("engineeringagent.adapters.config")
    return config_runtime.resolve_specifications_root(project_root)


def iter_feature_files(features_root: Path) -> tuple[Path, ...]:
    """Proxy to bundled feature entrypoint discovery for harness code."""

    specification = import_module("engineeringagent.domain.specification")
    return tuple(specification.iter_feature_files(features_root))


def load_markdown_frontmatter(path: Path) -> dict[str, Any]:
    """Proxy to bundled markdown frontmatter loading for harness code."""

    specification = import_module("engineeringagent.domain.specification")
    return specification.load_markdown_frontmatter(path)


def reviewer_decision_schema_from_model() -> dict[str, Any]:
    """Proxy to the reviewer decision schema producer lazily."""

    engine = import_module("engineeringagent.adapters.quality.reviewers.engine")
    return engine.reviewer_decision_schema_from_model()
