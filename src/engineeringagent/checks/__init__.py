"""Canonical checks surface.

This package is introduced as part of a staged refactor to centralize all check
planning and execution behind a stable import surface.
"""

from .api import run_checks
from .fitness_api import emit_fitness_result

emit_result_envelope = emit_fitness_result

__all__ = [
    "emit_fitness_result",
    "emit_result_envelope",
    "run_checks",
]
