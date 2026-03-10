"""Adapter helpers for assembling implementation prompt requests."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from engineeringagent.loop_runtime.progress_units import (
    current_progress_unit,
    feature_progress_reference,
)
from engineeringagent.progress import paths as progress_paths
from engineeringagent.specs import (
    feature_progress_kind,
    resolve_feature_plan_path,
    resolve_feature_research_path,
)

from .prompt_builder import (
    ImplementationPromptRequest,
    PromptBuilder,
    PromptArtifactPaths,
    PromptProgressKind,
)


def build_implementation_prompt_request(
    *,
    feature: Mapping[str, Any],
    feature_path: Path,
    feedback: str | None,
    handoff_path: str | None = None,
) -> ImplementationPromptRequest:
    """Resolve explicit implementation-prompt inputs from feature state."""

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
    """Render the implementation prompt via the application prompt builder."""

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
