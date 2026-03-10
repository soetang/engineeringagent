"""Prompt rendering compatibility exports."""

from __future__ import annotations

from functools import lru_cache
from importlib import import_module
from pathlib import Path
from types import ModuleType
from typing import Any, Mapping, Sequence

__all__ = [
    "build_implementation_prompt",
    "build_selector_prompt",
    "inject_feedback",
]

@lru_cache(maxsize=1)
def _load_renderer() -> ModuleType:
    """Load the renderer module lazily to avoid import cycles."""
    return import_module("engineeringagent.prompts.renderer")


def build_selector_prompt(
    pending: Sequence[tuple[Path, Mapping[str, Any]]],
    *,
    project_root: Path | None = None,
) -> str:
    """Render the selector prompt through the renderer module."""
    return _load_renderer().build_selector_prompt(pending, project_root=project_root)


def inject_feedback(
    prompt: str,
    feedback: str | None,
    *,
    project_root: Path | None = None,
) -> str:
    """Inject retry feedback through the renderer compatibility layer."""
    return _load_renderer().inject_feedback(
        prompt,
        feedback,
        project_root=project_root,
    )


def build_implementation_prompt(
    *,
    feature: Mapping[str, Any],
    feature_path: Path,
    feedback: str | None,
    project_root: Path | None = None,
) -> str:
    """Render the implementation prompt through the renderer module."""
    return _load_renderer().build_implementation_prompt(
        feature=feature,
        feature_path=feature_path,
        feedback=feedback,
        project_root=project_root,
    )
