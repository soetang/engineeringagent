from __future__ import annotations

from importlib.resources import files
from pathlib import Path
from string import Template
from typing import Any, Mapping, Sequence

from engineeringagent.application.prompt_builder import (
    build_implementation_prompt as _build_implementation_prompt,
    inject_feedback as _inject_feedback,
)

_TEMPLATE_PACKAGE = "engineeringagent.prompts.templates"


def _load_template(name: str) -> Template:
    template_text = files(_TEMPLATE_PACKAGE).joinpath(name).read_text(encoding="utf-8")
    return Template(template_text)


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

    selector_template = _load_template("loop_selector.md")
    return selector_template.substitute(choices="\n".join(choices))


def inject_feedback(prompt: str, feedback: str | None) -> str:
    """Compatibility facade for application-owned feedback injection."""

    return _inject_feedback(prompt, feedback)


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
    )
