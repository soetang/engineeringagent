"""Application service for deterministic prompt assembly."""

from __future__ import annotations

from pathlib import Path
from string import Template
from typing import Any, Literal, Mapping, Protocol, Sequence

from pydantic import BaseModel, ConfigDict, ValidationError

from engineeringagent.ports import PromptDefinitionRepository
from engineeringagent.prompt_feedback import normalize_prompt_feedback
from engineeringagent.prompts.feedback_envelope import (
    parse_feedback_envelope,
    serialize_feedback_envelope,
)


class PromptArtifactPaths(BaseModel):
    """Explicit prompt artifact references resolved before rendering."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    specification: Path
    plan: str | None = None
    research: str | None = None


PromptProgressKind = Literal["phase", "feature"]


class ImplementationPromptRequest(BaseModel):
    """Typed input for implementation prompt rendering."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    feature: Mapping[str, Any]
    artifacts: PromptArtifactPaths
    handoff_path: str
    feedback: str | None
    progress_kind: PromptProgressKind
    current_progress: str | None = None


class PromptBuilder(Protocol):
    """Application seam for prompt assembly."""

    def build_implementation_prompt(self, request: ImplementationPromptRequest) -> str:
        """Render the implementation prompt for one iteration."""
        raise NotImplementedError


class DefaultPromptBuilder:
    """Deterministic prompt builder backed by bundled templates."""

    def __init__(self, prompt_definitions: PromptDefinitionRepository) -> None:
        self._prompt_definitions = prompt_definitions

    def build_implementation_prompt(self, request: ImplementationPromptRequest) -> str:
        """Render the implementation prompt for one iteration."""
        implementation_template = _load_template(
            self._prompt_definitions,
            "loop_implementation",
        )
        prompt = implementation_template.substitute(
            feature_path=str(request.artifacts.specification),
            artifact_paths=_artifact_paths_prompt_block(request),
            feature_id=str(request.feature.get("id", "unknown-feature")),
            handoff_path=request.handoff_path,
            feature_title=str(request.feature.get("title", "")),
            objective=str(request.feature.get("objective", "")),
            context=str(request.feature.get("context", "")),
            progress_unit=_progress_unit_prompt_label(request.progress_kind),
            current_progress_reference=_current_progress_reference_line(
                request.progress_kind,
                request.current_progress,
            ),
            progress_context_instruction=_progress_context_instruction(
                request.progress_kind
            ),
            progress_update_instruction=_progress_update_instruction(
                request.progress_kind
            ),
        )
        return inject_feedback(
            prompt,
            request.feedback,
            prompt_definitions=self._prompt_definitions,
        )


def build_selector_prompt(
    pending: Sequence[tuple[Path, Mapping[str, Any]]],
    *,
    prompt_definitions: PromptDefinitionRepository,
) -> str:
    """Render the selector prompt from deterministic feature summaries."""

    choices = []
    for feature_path, feature in pending:
        choices.append(
            f"- id={feature.get('id')} status={feature.get('status')} "
            f"priority={feature.get('priority')} path={feature_path}"
        )

    selector_template = _load_template(
        prompt_definitions,
        "loop_selector",
    )
    return selector_template.substitute(choices="\n".join(choices))


def inject_feedback(
    prompt: str,
    feedback: str | None,
    *,
    prompt_definitions: PromptDefinitionRepository,
) -> str:
    """Append canonical feedback block to a prompt."""

    if not feedback:
        return prompt

    normalized_feedback = _normalize_feedback(feedback)
    if not normalized_feedback:
        return prompt

    feedback_template = _load_template(
        prompt_definitions,
        "loop_feedback",
    )
    return prompt + feedback_template.substitute(
        feedback=normalized_feedback,
    )


def _load_template(
    prompt_definitions: PromptDefinitionRepository,
    prompt_id: str,
) -> Template:
    return Template(prompt_definitions.get(prompt_id).template_text)


def _normalize_feedback(feedback: str) -> str:
    """Normalize feedback for prompt injection."""

    try:
        envelope = parse_feedback_envelope(feedback)
    except ValidationError:
        normalized = normalize_prompt_feedback(feedback)
        return normalized or ""

    return serialize_feedback_envelope(envelope)


def _artifact_paths_prompt_block(request: ImplementationPromptRequest) -> str:
    lines = [
        "Read and follow these files:",
        f"- specification: {request.artifacts.specification}",
    ]
    if request.artifacts.plan:
        lines.append(f"- plan: {request.artifacts.plan}")
    if request.artifacts.research:
        lines.append(f"- research: {request.artifacts.research}")
    return "\n".join(lines)


def _progress_update_instruction(progress_kind: str) -> str:
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
        "Update progress in the bundled feature package by setting "
        "`spec.yaml` feature status fields and `updated_at`."
    )


def _progress_context_instruction(progress_kind: str) -> str:
    return (
        "Treat this bundled feature package as canonical: keep lifecycle status "
        "in `spec.yaml` and sequencing in `plan.md` when present."
    )


def _progress_unit_prompt_label(progress_kind: str) -> str:
    if progress_kind == "phase":
        return "phase"
    if progress_kind == "feature":
        return "implementation step"
    return "implementation step"


def _current_progress_reference_line(
    progress_kind: str,
    current_progress: str | None,
) -> str:
    if not current_progress:
        return ""

    return (
        f"Current {_progress_unit_prompt_label(progress_kind)}: "
        f"{current_progress}\n"
    )
