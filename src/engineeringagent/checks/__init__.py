"""Supported checks surface for non-checks production code.

Outside `src/engineeringagent/checks/**`, production modules must only depend on
this stable surface.
"""

from .api import ChecksRunResult, run_checks
from .catalog import render_fitness_catalog
from .fitness_api import emit_fitness_result

emit_result_envelope = emit_fitness_result

__all__ = [
    "ChecksRunResult",
    "emit_fitness_result",
    "emit_result_envelope",
    "render_fitness_catalog",
    "run_checks",
]
