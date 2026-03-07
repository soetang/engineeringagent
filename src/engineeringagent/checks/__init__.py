"""Supported checks surface for non-checks production code.

Outside `src/engineeringagent/checks/**`, production modules must only depend on
this stable surface.
"""

from __future__ import annotations

from importlib import import_module
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from typing_extensions import Unpack

from .contracts import HarnessCheckPhase
from .results import ChecksRunResult
from .request_normalization import (
    list_check_groups,
    normalize_groups,
    reviewers_group_selected,
)

if TYPE_CHECKING:
    from engineeringagent.specs import HarnessChecksDocument

    from .api import _RunChecksKwargs
    from .fitness.contracts import FitnessRuleResult

__all__ = [
    "ChecksRunResult",
    "HarnessCheckPhase",
    "custom_rule_manifest_schema_from_model",
    "emit_fitness_result",
    "list_check_groups",
    "load_harness_checks_document",
    "normalize_groups",
    "render_fitness_catalog",
    "reviewer_decision_schema_from_model",
    "reviewers_group_selected",
    "run_checks",
]


def run_checks(
    project_root: str | Path,
    *,
    phase: str,
    checks: list[str] | None = None,
    **kwargs: Unpack[_RunChecksKwargs],
) -> ChecksRunResult:
    """Proxy to the checks runtime without importing it during package init."""

    runtime = import_module("engineeringagent.checks.api")
    return runtime.run_checks(project_root, phase=phase, checks=checks, **kwargs)


def load_harness_checks_document(
    project_root: Path,
    *,
    error_prefix: str,
    missing_context: str = "",
) -> tuple[HarnessChecksDocument | None, str | None]:
    """Proxy to config loading without importing specs during package init."""

    config_loader = import_module("engineeringagent.checks.config_loader")
    return config_loader.load_harness_checks_document(
        project_root,
        error_prefix=error_prefix,
        missing_context=missing_context,
    )


def emit_fitness_result(result: FitnessRuleResult) -> None:
    """Proxy to the fitness envelope helper without loading it during package init."""

    envelope = import_module("engineeringagent.checks.fitness.envelope")
    envelope.emit_fitness_result(result)


def custom_rule_manifest_schema_from_model() -> dict[str, Any]:
    """Proxy to the custom fitness manifest schema producer lazily."""

    contracts = import_module("engineeringagent.checks.fitness.contracts")
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


def reviewer_decision_schema_from_model() -> dict[str, Any]:
    """Proxy to the reviewer decision schema producer lazily."""

    engine = import_module("engineeringagent.checks.reviewers.engine")
    return engine.reviewer_decision_schema_from_model()
