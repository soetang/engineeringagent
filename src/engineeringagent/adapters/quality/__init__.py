"""Quality-system adapters."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

from .changed_paths import collect_changed_paths
from .repository_validator import ChecksRepositoryValidator

if TYPE_CHECKING:
    from .runtime_checks_runner import RuntimeChecksRunner

__all__ = ["collect_changed_paths", "ChecksRepositoryValidator", "RuntimeChecksRunner"]


def __getattr__(name: str) -> Any:
    if name == "RuntimeChecksRunner":
        module = import_module("engineeringagent.adapters.quality.runtime_checks_runner")
        return module.RuntimeChecksRunner
    raise AttributeError(name)
