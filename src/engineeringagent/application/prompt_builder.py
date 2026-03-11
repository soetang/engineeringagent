"""Application service for deterministic prompt assembly."""

from __future__ import annotations
from pathlib import Path
from typing import Any, Literal, Mapping, Protocol, Sequence

from pydantic import BaseModel, ConfigDict, ValidationError
import yaml

from engineeringagent.domain.specification import (
    feature_progress_reference,
)
from engineeringagent.ports import PromptDefinitionRepository
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


class ImplementationPromptFeature(BaseModel):
    """Explicit feature fields allowed into the implementation prompt."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    feature_id: str
    title: str = ""
    objective: str = ""
    context: str = ""


class ImplementationPromptRequest(BaseModel):
    """Typed input for implementation prompt rendering."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    feature: ImplementationPromptFeature
    artifacts: PromptArtifactPaths
    handoff_path: str | None
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
        implementation_definition = self._prompt_definitions.get(
            "loop_implementation"
        )
        prompt = implementation_definition.render(
            {
                "feature_id": request.feature.feature_id,
                "feature_title": request.feature.title,
                "objective": request.feature.objective,
                "context": request.feature.context,
                "artifact_paths": _artifact_paths_prompt_block(request),
                "handoff_path": request.handoff_path or "",
                "progress_unit": _progress_unit_prompt_label(request.progress_kind),
                "current_progress_reference": _current_progress_reference_line(
                    request.progress_kind,
                    request.current_progress,
                ),
                "progress_context_instruction": _progress_context_instruction(),
                "progress_update_instruction": _progress_update_instruction(
                    request.progress_kind
                ),
            }
        )
        return inject_feedback(
            prompt,
            request.feedback,
            prompt_definitions=self._prompt_definitions,
        )


def build_implementation_prompt_request(
    *,
    feature: Mapping[str, Any],
    feature_path: Path,
    feedback: str | None,
    handoff_path: str | None = None,
) -> ImplementationPromptRequest:
    """Resolve explicit application prompt inputs from feature artifacts."""

    feature_payload = dict(feature)
    raw_progress_kind = _feature_progress_kind(feature_path, feature_payload)
    progress_unit = _current_progress_unit(feature_path, feature_payload)
    progress_kind = _normalize_prompt_progress_kind(raw_progress_kind)
    current_progress = _current_progress_reference(
        progress_unit=progress_unit,
        feature=feature_payload,
        progress_kind=raw_progress_kind,
    )
    return ImplementationPromptRequest(
        feature=_feature_prompt_context(feature_payload),
        artifacts=PromptArtifactPaths(
            specification=feature_path,
            plan=_resolved_artifact_reference(feature_path, feature_payload, "plan"),
            research=_resolved_artifact_reference(
                feature_path,
                feature_payload,
                "research",
            ),
        ),
        handoff_path=handoff_path,
        feedback=feedback,
        progress_kind=progress_kind,
        current_progress=current_progress,
    )


def build_implementation_prompt(
    *,
    feature: Mapping[str, Any],
    feature_path: Path,
    feedback: str | None,
    handoff_path: str | None = None,
    prompt_builder: PromptBuilder,
) -> str:
    """Render the implementation prompt from application-owned inputs."""

    request = build_implementation_prompt_request(
        feature=feature,
        feature_path=feature_path,
        feedback=feedback,
        handoff_path=handoff_path,
    )
    return prompt_builder.build_implementation_prompt(request)


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

    selector_definition = prompt_definitions.get("loop_selector")
    return selector_definition.render(
        {
            "choices": "\n".join(choices),
        }
    )


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

    feedback_definition = prompt_definitions.get("loop_feedback")
    return prompt + feedback_definition.render(
        {
            "feedback": normalized_feedback,
        }
    )


def _resolved_artifact_reference(
    feature_path: Path,
    feature: Mapping[str, Any],
    artifact_kind: str,
) -> str | None:
    artifact_path = _resolve_bundled_artifact_path(
        feature_path,
        dict(feature),
        artifact_kind=artifact_kind,
    )
    if artifact_path is None:
        return None
    return str(artifact_path)


def _normalize_feedback(feedback: str) -> str:
    """Normalize feedback for prompt injection."""

    try:
        envelope = parse_feedback_envelope(feedback)
    except ValidationError:
        normalized = _normalize_plain_prompt_feedback(feedback)
        return normalized or ""

    return serialize_feedback_envelope(envelope)


def _normalize_plain_prompt_feedback(value: str | None) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None


def _feature_prompt_context(
    feature: Mapping[str, Any],
) -> ImplementationPromptFeature:
    return ImplementationPromptFeature(
        feature_id=_string_field(feature, "id", fallback="unknown-feature"),
        title=_string_field(feature, "title"),
        objective=_string_field(feature, "objective"),
        context=_string_field(feature, "context"),
    )


def _current_progress_reference(
    *,
    progress_unit: object,
    feature: Mapping[str, Any],
    progress_kind: str,
) -> str | None:
    unit_id = getattr(progress_unit, "id", None)
    if isinstance(unit_id, str) and unit_id.strip():
        title = getattr(progress_unit, "title", None)
        if isinstance(title, str) and title.strip():
            return f"{unit_id} - {title}"
        return unit_id

    if progress_kind != "feature":
        return None

    progress_id, progress_title = feature_progress_reference(dict(feature))
    if progress_id is None:
        return None
    if progress_title:
        return f"{progress_id} - {progress_title}"
    return progress_id


def _feature_progress_kind(
    feature_path: Path,
    feature: Mapping[str, Any],
) -> str:
    if _resolve_bundled_artifact_path(feature_path, dict(feature), artifact_kind="plan"):
        return "phase"
    return "feature"


def _current_progress_unit(
    feature_path: Path,
    feature: Mapping[str, Any],
) -> _PromptProgressUnit | None:
    progress_units = list(_iter_progress_units(feature_path, feature))
    if not progress_units:
        return None

    for unit in progress_units:
        if unit.status == "in_progress":
            return unit
    for unit in progress_units:
        if unit.status != "done":
            return unit
    return progress_units[-1]


class _PromptProgressUnit(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: str
    id: str
    title: str | None = None
    status: str | None = None


def _iter_progress_units(
    feature_path: Path,
    feature: Mapping[str, Any],
) -> Sequence[_PromptProgressUnit]:
    plan_path = _resolve_bundled_artifact_path(
        feature_path,
        dict(feature),
        artifact_kind="plan",
    )
    if plan_path is not None:
        return tuple(_iter_plan_progress_units(plan_path))

    feature_unit = _feature_progress_unit(feature_path, feature)
    if feature_unit is None:
        return ()
    return (feature_unit,)


def _feature_progress_unit(
    feature_path: Path,
    feature: Mapping[str, Any],
) -> _PromptProgressUnit | None:
    if feature_path.name != "spec.yaml":
        return None

    progress_id, progress_title = feature_progress_reference(dict(feature))
    if progress_id is None:
        return None
    return _PromptProgressUnit(
        kind="feature",
        id=progress_id,
        title=progress_title,
        status=_normalized_text(feature.get("status")),
    )


def _iter_plan_progress_units(plan_path: Path) -> Sequence[_PromptProgressUnit]:
    frontmatter = _load_markdown_frontmatter(plan_path)
    if frontmatter is None:
        return ()
    raw_phases = frontmatter.get("phases")
    if not isinstance(raw_phases, list):
        return ()

    progress_units: list[_PromptProgressUnit] = []
    seen_ids: set[str] = set()
    for phase in raw_phases:
        if not isinstance(phase, dict):
            continue
        progress_id = _normalized_text(phase.get("id"))
        if progress_id is None or progress_id in seen_ids:
            continue
        seen_ids.add(progress_id)
        progress_units.append(
            _PromptProgressUnit(
                kind="phase",
                id=progress_id,
                title=_normalized_text(phase.get("title")),
                status=_normalized_text(phase.get("status")),
            )
        )
    return tuple(progress_units)


def _load_markdown_frontmatter(path: Path) -> dict[str, Any] | None:
    try:
        document = path.read_text(encoding="utf-8")
    except OSError:
        return None
    if not document.startswith("---\n"):
        return None

    frontmatter_end = document.find("\n---", 4)
    if frontmatter_end < 0:
        return None

    frontmatter_block = document[4:frontmatter_end].strip()
    if not frontmatter_block:
        return None

    try:
        parsed = yaml.safe_load(frontmatter_block)
    except yaml.YAMLError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _resolve_bundled_artifact_path(
    feature_path: Path,
    feature: Mapping[str, Any],
    *,
    artifact_kind: str,
) -> Path | None:
    if feature_path.name != "spec.yaml":
        return None
    artifacts = feature.get("artifacts")
    if not isinstance(artifacts, dict):
        return None
    artifact_ref = artifacts.get(artifact_kind)
    if not isinstance(artifact_ref, str):
        return None
    normalized_ref = artifact_ref.strip()
    if not normalized_ref:
        return None
    return feature_path.parent / normalized_ref


def _normalized_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized_value = value.strip()
    return normalized_value or None


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


def _progress_context_instruction() -> str:
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


def _normalize_prompt_progress_kind(progress_kind: str) -> PromptProgressKind:
    if progress_kind == "phase":
        return "phase"
    return "feature"


def _string_field(
    feature: Mapping[str, Any],
    field_name: str,
    *,
    fallback: str = "",
) -> str:
    value = feature.get(field_name)
    if isinstance(value, str):
        return value
    return fallback
