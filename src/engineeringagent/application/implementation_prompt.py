"""Application-owned implementation prompt request assembly."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, Mapping

from pydantic import BaseModel, ConfigDict
import yaml

from engineeringagent.specs import (
    FeaturePlanArtifact,
    load_feature_plan_artifact,
    load_markdown_frontmatter,
)
from engineeringagent.progress import paths as progress_paths
from engineeringagent.specs import (
    feature_progress_kind,
    resolve_feature_plan_path,
    resolve_feature_research_path,
)

from .prompt_builder import (
    ImplementationPromptRequest,
    PromptArtifactPaths,
    PromptBuilder,
    PromptProgressKind,
)


class ProgressUnit(BaseModel):
    """One feature- or phase-shaped execution unit."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: str
    id: str
    title: str | None = None
    status: str | None = None
    verification_commands: list[str]


def build_implementation_prompt_request(
    *,
    feature: Mapping[str, Any],
    feature_path: Path,
    feedback: str | None,
    handoff_path: str | None = None,
) -> ImplementationPromptRequest:
    """Resolve explicit application prompt inputs from feature artifacts."""

    feature_id = str(feature.get("id", "unknown-feature"))
    raw_progress_kind = feature_progress_kind(feature_path, dict(feature))
    progress_unit = current_progress_unit(feature_path, dict(feature))
    progress_kind = _normalize_prompt_progress_kind(raw_progress_kind)
    current_progress = _current_progress_reference(
        progress_unit=progress_unit,
        feature=feature,
        progress_kind=raw_progress_kind,
    )
    return ImplementationPromptRequest(
        feature=feature,
        artifacts=PromptArtifactPaths(
            specification=feature_path,
            plan=_resolved_artifact_reference(feature_path, feature, "plan"),
            research=_resolved_artifact_reference(feature_path, feature, "research"),
        ),
        handoff_path=handoff_path
        or progress_paths.handoff_markdown_reference(Path(), feature_id),
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


def _normalize_prompt_progress_kind(progress_kind: str) -> PromptProgressKind:
    if progress_kind == "phase":
        return "phase"
    return "feature"


def feature_progress_reference(
    feature: dict[str, Any] | None,
) -> tuple[str | None, str | None]:
    """Return the feature-level progress reference used by direct bundled specs."""

    if not isinstance(feature, dict):
        return None, None

    progress_id = feature.get("id")
    normalized_id = progress_id.strip() if isinstance(progress_id, str) else ""
    progress_title = feature.get("title")
    normalized_title = (
        progress_title.strip() if isinstance(progress_title, str) else ""
    )
    return (
        normalized_id or None,
        normalized_title or None,
    )


def current_progress_unit(
    feature_path: Path,
    feature: dict[str, Any] | None,
) -> ProgressUnit | None:
    """Resolve the current execution unit for prompt context."""

    units = list(iter_progress_units(feature_path, feature))
    if not units:
        return None

    for unit in units:
        if unit.status == "in_progress":
            return unit
    for unit in units:
        if unit.status != "done":
            return unit
    return units[-1]


def iter_progress_units(
    feature_path: Path,
    feature: dict[str, Any] | None,
) -> Iterable[ProgressUnit]:
    """Yield the active prompt progress units for a feature."""

    plan_path = resolve_feature_plan_path(feature_path, feature)
    if plan_path is not None:
        plan = load_feature_plan_artifact(feature_path, feature)
        if plan is not None:
            yield from _iter_plan_progress_units(plan)
            return

        raw_plan_frontmatter = _load_raw_plan_frontmatter(feature_path, feature)
        if raw_plan_frontmatter is not None:
            yield from _iter_raw_plan_progress_units(raw_plan_frontmatter)
        return

    if feature_path.name == "spec.yaml":
        feature_unit = _feature_progress_unit(feature)
        if feature_unit is not None:
            yield feature_unit


def _feature_progress_unit(feature: dict[str, Any] | None) -> ProgressUnit | None:
    progress_id, progress_title = feature_progress_reference(feature)
    if progress_id is None:
        return None

    return ProgressUnit(
        kind="feature",
        id=progress_id,
        title=progress_title,
        status=_normalized_text(
            feature.get("status") if isinstance(feature, dict) else None
        ),
        verification_commands=[],
    )


def _iter_plan_progress_units(plan: FeaturePlanArtifact) -> Iterable[ProgressUnit]:
    yield from _iter_mapping_progress_units(
        plan.phases,
        kind="phase",
        get_value=lambda phase, field: getattr(phase, field, None),
    )


def _load_raw_plan_frontmatter(
    feature_path: Path,
    feature: dict[str, Any] | None,
) -> dict[str, Any] | None:
    plan_path = resolve_feature_plan_path(feature_path, feature)
    if plan_path is None or not plan_path.is_file():
        return None
    try:
        frontmatter = load_markdown_frontmatter(plan_path)
    except (ValueError, yaml.YAMLError):
        return None
    return frontmatter if isinstance(frontmatter, dict) else None


def _iter_raw_plan_progress_units(
    frontmatter: dict[str, Any],
) -> Iterable[ProgressUnit]:
    raw_phases = frontmatter.get("phases")
    if not isinstance(raw_phases, list):
        return

    yield from _iter_mapping_progress_units(
        raw_phases,
        kind="phase",
        get_value=lambda phase, field: phase.get(field) if isinstance(phase, dict) else None,
    )


def _iter_mapping_progress_units(
    items: Iterable[Any],
    *,
    kind: str,
    get_value: Any,
) -> Iterable[ProgressUnit]:
    seen_ids: set[str] = set()
    for item in items:
        progress_id = _normalized_text(get_value(item, "id"))
        if progress_id is None or progress_id in seen_ids:
            continue
        seen_ids.add(progress_id)
        verification = get_value(item, "verification")
        yield ProgressUnit(
            kind=kind,
            id=progress_id,
            title=_normalized_text(get_value(item, "title")),
            status=_normalized_text(get_value(item, "status")),
            verification_commands=list(
                _iter_verification_commands(
                    verification if isinstance(verification, list) else []
                )
            ),
        )


def _iter_verification_commands(verification: list[Any]) -> Iterable[str]:
    for command in verification:
        if not isinstance(command, str):
            continue
        normalized_command = command.strip()
        if normalized_command:
            yield normalized_command


def _normalized_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized_value = value.strip()
    return normalized_value or None
