from __future__ import annotations

from pathlib import Path
from string import Template
from typing import Any, Mapping, Sequence

from engineeringagent.adapters.prompts import BundledPromptDefinitionRepository
from engineeringagent.application.prompt_builder import (
    DefaultPromptBuilder,
    build_implementation_prompt as _build_implementation_prompt,
    inject_feedback as _inject_feedback,
)
from engineeringagent.ports import PromptDefinitionRepository


def _default_prompt_definitions() -> PromptDefinitionRepository:
    return BundledPromptDefinitionRepository()


def _load_template(
    prompt_definitions: PromptDefinitionRepository,
    prompt_id: str,
) -> Template:
    return Template(prompt_definitions.get(prompt_id).template_text)


def build_selector_prompt(pending: Sequence[tuple[Path, Mapping[str, Any]]]) -> str:
    """Render selector prompt from template text.

    Args:
        pending: Pending feature tuples of path and feature payload.

    Returns:
        Rendered selector prompt text.
    """
    choices = []
    for feature_path, feature in pending:
        choices.append(
            f"- id={feature.get('id')} status={feature.get('status')} "
            f"priority={feature.get('priority')} path={feature_path}"
        )

    selector_template = _load_template(
        _default_prompt_definitions(),
        "loop_selector",
    )
    return selector_template.substitute(choices="\n".join(choices))


def inject_feedback(prompt: str, feedback: str | None) -> str:
    """Compatibility facade for application-owned feedback injection."""

    return _inject_feedback(
        prompt,
        feedback,
        prompt_definitions=_default_prompt_definitions(),
    )


def build_implementation_prompt(
    *,
    feature: Mapping[str, Any],
    feature_path: Path,
    feedback: str | None,
) -> str:
    """Compatibility facade for application-owned implementation prompts."""

    return _build_implementation_prompt(
        feature=feature,
        feature_path=feature_path,
        feedback=feedback,
        prompt_builder=DefaultPromptBuilder(_default_prompt_definitions()),
    )
