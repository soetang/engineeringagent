from __future__ import annotations

from importlib.resources import files
from pathlib import Path
from string import Template
from typing import Any, Mapping, Sequence

from pydantic import ValidationError

from engineeringagent.loop_runtime.progress_units import current_progress_unit
from engineeringagent.prompt_feedback import normalize_prompt_feedback
from engineeringagent.specs import feature_progress_kind
from engineeringagent.prompts.feedback_envelope import (
    parse_feedback_envelope,
    serialize_feedback_envelope,
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


def _normalize_feedback(feedback: str) -> str:
    """Normalize feedback for prompt injection.

    Legacy runtime phases still emit serialized v1 envelopes. Checks strategies now
    own feedback rendering and can return plain markdown text. Accept both:
    canonicalize envelopes when present and otherwise forward plain text as-is.
    """

    try:
        envelope = parse_feedback_envelope(feedback)
    except ValidationError:
        normalized = normalize_prompt_feedback(feedback)
        return normalized or ""

    return serialize_feedback_envelope(envelope)


def inject_feedback(prompt: str, feedback: str | None) -> str:
    """Append canonical feedback block to a prompt.

    Args:
        prompt: Base prompt text.
        feedback: Optional previous-failure feedback.

    Returns:
        Prompt with canonical feedback section appended when feedback exists.
    """
    if not feedback:
        return prompt

    normalized_feedback = _normalize_feedback(feedback)
    if not normalized_feedback:
        return prompt

    feedback_template = _load_template("loop_feedback.md")
    return prompt + feedback_template.substitute(
        feedback=normalized_feedback,
    )


def build_implementation_prompt(
    *,
    feature: Mapping[str, Any],
    feature_path: Path,
    feedback: str | None,
) -> str:
    """Render default implementation prompt from template text.

    Args:
        feature: Loaded feature mapping.
        feature_path: Absolute path to feature YAML.
        feedback: Optional previous-failure feedback.

    Returns:
        Rendered implementation prompt text.
    """
    implementation_template = _load_template("loop_implementation.md")
    progress_kind = feature_progress_kind(feature_path, dict(feature))
    current_progress = current_progress_unit(feature_path, dict(feature))
    prompt = implementation_template.substitute(
        feature_path=str(feature_path),
        feature_id=str(feature.get("id", "unknown-feature")),
        feature_title=str(feature.get("title", "")),
        objective=str(feature.get("objective", "")),
        context=str(feature.get("context", "")),
        progress_unit=_progress_unit_prompt_label(progress_kind),
        current_progress_reference=_current_progress_reference_line(current_progress),
        progress_context_instruction=_progress_context_instruction(progress_kind),
        progress_update_instruction=_progress_update_instruction(progress_kind),
    )

    return inject_feedback(prompt, feedback)


def _progress_update_instruction(progress_kind: str) -> str:
    """Return progress-update instructions for the active execution surface."""

    if progress_kind == "phase":
        return (
            "Update progress in the bundled feature package, including "
            "`plan.md` by setting relevant phase status fields, `spec.yaml` "
            "feature status fields, and `updated_at`."
        )
    if progress_kind == "feature":
        return (
            "Update progress in the bundled feature package by setting "
            "`spec.yaml` feature status fields and `updated_at`."
        )
    return (
        "Update progress in the same feature YAML by setting relevant "
        "subtask/feature status fields and `updated_at`."
    )


def _progress_context_instruction(progress_kind: str) -> str:
    """Return prompt guidance for the active canonical working set."""

    if progress_kind == "subtask":
        return (
            "Treat the compatibility wrapper as a temporary shim and follow its "
            "canonical bundled package references as the source of truth."
        )
    return (
        "Treat this bundled feature package as canonical: keep lifecycle status "
        "in `spec.yaml` and sequencing in `plan.md` when present."
    )


def _progress_unit_prompt_label(progress_kind: str) -> str:
    """Return the prompt wording for the active progress surface."""

    if progress_kind == "subtask":
        return "compatibility-wrapper subtask"
    if progress_kind == "feature":
        return "implementation step"
    return progress_kind


def _current_progress_reference_line(progress_unit: Any) -> str:
    """Return an optional prompt line naming the active progress unit."""

    if progress_unit is None:
        return ""

    progress_kind = _progress_unit_prompt_label(str(progress_unit.kind))
    reference = str(progress_unit.id)
    if progress_unit.title:
        reference = f"{reference} - {progress_unit.title}"
    return f"Current {progress_kind}: {reference}\n"
