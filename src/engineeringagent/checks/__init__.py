"""Supported checks surface for non-checks production code.

Outside `src/engineeringagent/checks/**`, production modules must only depend on
this stable surface.
"""

from .api import ChecksRunResult, run_checks
from .catalog import render_fitness_catalog
from .config_loader import load_harness_checks_document
from .fitness_api import emit_fitness_result
from .request_normalization import GROUP_ORDER, normalize_groups

emit_result_envelope = emit_fitness_result


def list_check_groups() -> tuple[str, ...]:
    """Return supported checks groups in deterministic CLI order."""
    return GROUP_ORDER


def normalize_check_groups(checks: list[str] | None) -> tuple[str, ...]:
    """Normalize checks-group selection for external callers."""
    return normalize_groups(checks)


__all__ = [
    "ChecksRunResult",
    "emit_fitness_result",
    "emit_result_envelope",
    "list_check_groups",
    "load_harness_checks_document",
    "normalize_check_groups",
    "render_fitness_catalog",
    "run_checks",
]
