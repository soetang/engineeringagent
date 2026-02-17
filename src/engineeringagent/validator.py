"""Compatibility wrapper for legacy validator module.

FEAT-098 migrates production callers to the canonical checks surface.
This module remains for backward compatibility and test coverage.
"""

from __future__ import annotations

from engineeringagent.checks.validate.validator import (
    _append_legacy_harness_contract_file_issues,
    _iter_agents_docs_map_references,
    git_client,
    validate,
)

from engineeringagent.checks.validate import validator as _impl

__all__ = [
    "_append_legacy_harness_contract_file_issues",
    "_iter_agents_docs_map_references",
    "git_client",
    "validate",
]


def __getattr__(name: str) -> object:
    return getattr(_impl, name)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(dir(_impl)))
