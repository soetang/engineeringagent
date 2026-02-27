"""Supported checks surface for non-checks production code.

Outside `src/engineeringagent/checks/**`, production modules must only depend on
this stable surface.
"""

from .api import ChecksRunResult, run_checks
from .catalog import render_fitness_catalog
from .config_loader import load_harness_checks_document
from .fitness.envelope import emit_fitness_result
from .request_normalization import GROUP_ORDER, normalize_groups


def list_check_groups() -> tuple[str, ...]:
    """Return supported checks groups in deterministic CLI order."""
    return GROUP_ORDER


__all__ = [
    "ChecksRunResult",
    "emit_fitness_result",
    "list_check_groups",
    "load_harness_checks_document",
    "normalize_groups",
    "render_fitness_catalog",
    "run_checks",
]
