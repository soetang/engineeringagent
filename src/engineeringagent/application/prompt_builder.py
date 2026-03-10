"""Application service for deterministic prompt assembly."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from string import Template
from typing import Any, Mapping, Protocol

from pydantic import ValidationError

from engineeringagent.adapters.prompts import BundledPromptDefinitionRepository
from engineeringagent.loop_runtime.progress_units import current_progress_unit
from engineeringagent.ports import PromptDefinitionRepository
from engineeringagent.prompt_feedback import normalize_prompt_feedback
from engineeringagent.prompts.feedback_envelope import (
    parse_feedback_envelope,
    serialize_feedback_envelope,
)
from engineeringagent.progress import paths as progress_paths
from engineeringagent.specs import (
    feature_progress_kind,
    resolve_feature_plan_path,
    resolve_feature_research_path,
)
@dataclass(frozen=True)
class ImplementationPromptRequest:
    """Typed input for implementation prompt rendering."""

    feature: Mapping[str, Any]
    feature_path: Path
    plan_path: str | None
    research_path: str | None
    handoff_path: str
    feedback: str | None


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
        progress_kind = feature_progress_kind(
            request.feature_path,
            dict(request.feature),
        )
        current_progress = current_progress_unit(
            request.feature_path,
            dict(request.feature),
        )
        prompt = implementation_template.substitute(
            feature_path=str(request.feature_path),
            artifact_paths=_artifact_paths_prompt_block(request),
            feature_id=str(request.feature.get("id", "unknown-feature")),
            handoff_path=request.handoff_path,
            feature_title=str(request.feature.get("title", "")),
            objective=str(request.feature.get("objective", "")),
            context=str(request.feature.get("context", "")),
            progress_unit=_progress_unit_prompt_label(progress_kind),
            current_progress_reference=_current_progress_reference_line(
                current_progress
            ),
            progress_context_instruction=_progress_context_instruction(progress_kind),
            progress_update_instruction=_progress_update_instruction(progress_kind),
        )
        return inject_feedback(prompt, request.feedback)


def build_implementation_prompt(
    *,
    feature: Mapping[str, Any],
    feature_path: Path,
    feedback: str | None,
    handoff_path: str | None = None,
    prompt_builder: PromptBuilder,
) -> str:
    """Compatibility helper for rendering implementation prompts."""

    feature_id = str(feature.get("id", "unknown-feature"))
    return prompt_builder.build_implementation_prompt(
        ImplementationPromptRequest(
            feature=feature,
            feature_path=feature_path,
            plan_path=_resolved_artifact_reference(feature_path, feature, "plan"),
            research_path=_resolved_artifact_reference(
                feature_path, feature, "research"
            ),
            handoff_path=handoff_path
            or progress_paths.handoff_markdown_reference(Path(), feature_id),
            feedback=feedback,
        )
    )


def inject_feedback(prompt: str, feedback: str | None) -> str:
    """Append canonical feedback block to a prompt."""

    if not feedback:
        return prompt

    normalized_feedback = _normalize_feedback(feedback)
    if not normalized_feedback:
        return prompt

    feedback_template = _load_template(
        BundledPromptDefinitionRepository(),
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
    lines = ["Read and follow these files:", f"- specification: {request.feature_path}"]
    if request.plan_path:
        lines.append(f"- plan: {request.plan_path}")
    if request.research_path:
        lines.append(f"- research: {request.research_path}")
    return "\n".join(lines)


def _resolved_artifact_reference(
    feature_path: Path,
    feature: Mapping[str, Any],
    artifact_kind: str,
) -> str | None:
    feature_payload = dict(feature)
    resolver = (
        resolve_feature_plan_path
        if artifact_kind == "plan"
        else resolve_feature_research_path
    )
    artifact_path = resolver(feature_path, feature_payload)
    if artifact_path is None:
        return None
    return str(artifact_path)


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
        "Update progress in the same feature YAML by setting relevant "
        "subtask/feature status fields and `updated_at`."
    )


def _progress_context_instruction(progress_kind: str) -> str:
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
    if progress_kind == "subtask":
        return "compatibility-wrapper subtask"
    if progress_kind == "feature":
        return "implementation step"
    return progress_kind


def _current_progress_reference_line(progress_unit: Any) -> str:
    if progress_unit is None:
        return ""

    progress_kind = _progress_unit_prompt_label(str(progress_unit.kind))
    reference = str(progress_unit.id)
    if progress_unit.title:
        reference = f"{reference} - {progress_unit.title}"
    return f"Current {progress_kind}: {reference}\n"
