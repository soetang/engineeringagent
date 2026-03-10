"""Prompt rendering compatibility exports."""

from __future__ import annotations

from importlib import import_module
from pathlib import Path
from types import ModuleType
from typing import Any, Mapping, Sequence

from engineeringagent.ports import PromptDefinitionRepository

__all__ = [
    "build_implementation_prompt",
    "build_selector_prompt",
    "inject_feedback",
]


def _load_adapters_module() -> ModuleType:
    return import_module("engineeringagent.adapters.prompts")


def _load_prompt_builder_module() -> ModuleType:
    return import_module("engineeringagent.application.prompt_builder")


def _load_application_module() -> ModuleType:
    return import_module("engineeringagent.application")


def _default_prompt_definitions(
    project_root: Path | None = None,
) -> PromptDefinitionRepository:
    adapters_module = _load_adapters_module()

    if project_root is not None:
        return adapters_module.ProjectPromptDefinitionRepository(project_root)
    return adapters_module.BundledPromptDefinitionRepository()


def build_selector_prompt(
    pending: Sequence[tuple[Path, Mapping[str, Any]]],
    *,
    project_root: Path | None = None,
) -> str:
    """Render the selector prompt through the application layer."""

    return _load_prompt_builder_module().build_selector_prompt(
        pending,
        prompt_definitions=_default_prompt_definitions(project_root),
    )


def inject_feedback(
    prompt: str,
    feedback: str | None,
    *,
    project_root: Path | None = None,
) -> str:
    """Inject retry feedback through the application layer."""

    return _load_prompt_builder_module().inject_feedback(
        prompt,
        feedback,
        prompt_definitions=_default_prompt_definitions(project_root),
    )


def build_implementation_prompt(
    *,
    feature: Mapping[str, Any],
    feature_path: Path,
    feedback: str | None,
    project_root: Path | None = None,
) -> str:
    """Render the implementation prompt through the application layer."""

    application_module = _load_application_module()

    return application_module.build_implementation_prompt(
        feature=feature,
        feature_path=feature_path,
        feedback=feedback,
        prompt_builder=application_module.DefaultPromptBuilder(
            _default_prompt_definitions(project_root)
        ),
    )
