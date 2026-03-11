"""Specification progress units derived from bundled feature artifacts."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from pydantic import BaseModel, ConfigDict
import yaml

from engineeringagent.spec_bundles import (
    load_feature_plan_artifact,
    load_markdown_frontmatter,
    resolve_feature_plan_path,
)


class ProgressUnit(BaseModel):
    """One feature- or phase-shaped execution unit."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: str
    id: str
    title: str | None = None
    status: str | None = None
    verification_commands: list[str]


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


def progress_status_snapshot(
    feature_path: Path,
    feature: dict[str, Any] | None,
) -> dict[str, str]:
    """Return the pre/post status snapshot for the active progress surface."""

    return {
        unit.id: unit.status or ""
        for unit in iter_progress_units(feature_path, feature)
    }


def done_transition_verification_commands(
    previous_status_by_progress_id: dict[str, str],
    feature_path: Path,
    post_feature: dict[str, Any] | None,
) -> list[str]:
    """Return verification commands for units that newly transitioned to done."""

    commands: list[str] = []
    seen_commands: set[str] = set()
    for unit in iter_progress_units(feature_path, post_feature):
        previous_status = previous_status_by_progress_id.get(unit.id)
        if _transitioned_to_done(previous_status, unit.status):
            for command in unit.verification_commands:
                if command in seen_commands:
                    continue
                seen_commands.add(command)
                commands.append(command)
    return commands


def current_progress_unit(
    feature_path: Path,
    feature: dict[str, Any] | None,
) -> ProgressUnit | None:
    """Resolve the current execution unit for telemetry and prompts."""

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
    """Yield the active progress units for a feature."""

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


def _iter_plan_progress_units(plan: Any) -> Iterable[ProgressUnit]:
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


def _transitioned_to_done(previous_status: str | None, current_status: Any) -> bool:
    return (
        previous_status is not None
        and previous_status != "done"
        and current_status == "done"
    )
