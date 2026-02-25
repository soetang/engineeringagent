from __future__ import annotations

from importlib.resources import files
from pathlib import Path
from string import Template
from typing import Any, Mapping, Sequence

from pydantic import ValidationError

from engineeringagent.prompt_feedback import normalize_prompt_feedback
from engineeringagent.prompts.retry_feedback import (
    parse_retry_feedback_envelope,
    serialize_retry_feedback_envelope,
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


def _normalize_retry_feedback(hook_feedback: str) -> str:
    """Normalize retry feedback for prompt injection.

    Legacy runtime phases still emit serialized v1 envelopes. Checks strategies now
    own prompt feedback rendering and can return plain markdown text. Accept both:
    canonicalize envelopes when present and otherwise forward plain text as-is.
    """

    try:
        envelope = parse_retry_feedback_envelope(hook_feedback)
    except ValidationError:
        normalized = normalize_prompt_feedback(hook_feedback)
        return normalized or ""

    return serialize_retry_feedback_envelope(envelope)


def inject_retry_feedback(prompt: str, hook_feedback: str | None) -> str:
    """Append canonical retry feedback block to a prompt.

    Args:
        prompt: Base prompt text.
        hook_feedback: Optional previous-failure feedback for retries.

    Returns:
        Prompt with canonical retry section appended when feedback exists.
    """
    if not hook_feedback:
        return prompt

    normalized_feedback = _normalize_retry_feedback(hook_feedback)
    if not normalized_feedback:
        return prompt

    retry_feedback_template = _load_template("loop_retry_feedback.md")
    return prompt + retry_feedback_template.substitute(
        feedback=normalized_feedback,
    )


def build_implementation_prompt(
    *,
    feature: Mapping[str, Any],
    feature_path: Path,
    hook_feedback: str | None,
) -> str:
    """Render default implementation prompt from template text.

    Args:
        feature: Loaded feature mapping.
        feature_path: Absolute path to feature YAML.
        hook_feedback: Optional previous-failure feedback for retries.

    Returns:
        Rendered implementation prompt text.
    """
    implementation_template = _load_template("loop_implementation.md")
    prompt = implementation_template.substitute(
        feature_path=str(feature_path),
        feature_id=str(feature.get("id", "unknown-feature")),
        feature_title=str(feature.get("title", "")),
        objective=str(feature.get("objective", "")),
        context=str(feature.get("context", "")),
    )

    return inject_retry_feedback(prompt, hook_feedback)
