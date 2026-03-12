"""Application-owned bundled plan progress mutation helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Sequence

from pydantic import BaseModel, ConfigDict
import yaml

from engineeringagent.specs import dump_yaml, load_markdown_frontmatter, resolve_feature_plan_path


class _PlanProgressUpdateConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    allow_done_feature: bool
    feature_transitions: dict[str, set[str]]
    mutate_frontmatter: Callable[[dict[str, Any]], bool]
    sync_feature_status: bool = False


def load_plan_document_and_frontmatter(
    plan_path: Path,
) -> tuple[str, dict[str, Any]] | None:
    """Load a bundled plan document and its parsed YAML frontmatter."""

    try:
        document = plan_path.read_text(encoding="utf-8")
        frontmatter = load_markdown_frontmatter(plan_path)
    except (OSError, ValueError, yaml.YAMLError):
        return None
    return (document, frontmatter)


def _normalized_status(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized_value = value.strip()
    return normalized_value or None


def _iter_phase_mappings(frontmatter: dict[str, Any]) -> Sequence[dict[str, Any]]:
    phases = frontmatter.get("phases")
    if not isinstance(phases, list):
        return ()
    return tuple(phase for phase in phases if isinstance(phase, dict))


def _phase_statuses(frontmatter: dict[str, Any]) -> list[str]:
    return [
        normalized_status
        for phase in _iter_phase_mappings(frontmatter)
        if (normalized_status := _normalized_status(phase.get("status"))) is not None
    ]


def _write_plan_frontmatter(
    plan_path: Path,
    document: str,
    frontmatter: dict[str, Any],
) -> bool:
    frontmatter_end = document.find("\n---", 4)
    if frontmatter_end < 0:
        return False
    plan_path.write_text(
        "---\n"
        + yaml.safe_dump(frontmatter, sort_keys=False, allow_unicode=False)
        + "---\n"
        + document[frontmatter_end + 4 :],
        encoding="utf-8",
    )
    return True


def _sync_feature_status_from_plan(
    feature: dict[str, Any],
    frontmatter: dict[str, Any],
    feature_transitions: dict[str, set[str]],
) -> bool:
    plan_status = _normalized_status(frontmatter.get("status"))
    if plan_status not in feature_transitions or feature.get("status") == plan_status:
        return False
    feature["status"] = plan_status
    return True


def _update_plan_progress_artifact(
    feature: dict[str, Any],
    feature_path: Path,
    config: _PlanProgressUpdateConfig,
) -> bool:
    if not config.allow_done_feature and feature.get("status") == "done":
        return False
    plan_path = resolve_feature_plan_path(feature_path, feature)
    if plan_path is None or not plan_path.is_file():
        return False
    loaded_plan = load_plan_document_and_frontmatter(plan_path)
    if loaded_plan is None:
        return False

    document, frontmatter = loaded_plan
    plan_mutated = config.mutate_frontmatter(frontmatter)
    feature_mutated = config.sync_feature_status and _sync_feature_status_from_plan(
        feature,
        frontmatter,
        config.feature_transitions,
    )
    if not plan_mutated and not feature_mutated:
        return False
    if plan_mutated:
        _write_plan_frontmatter(plan_path, document, frontmatter)
    if feature_mutated:
        dump_yaml(feature_path, feature)
    return True


def _mark_plan_frontmatter_done(frontmatter: dict[str, Any]) -> bool:
    mutated = False
    if _normalized_status(frontmatter.get("status")) != "done":
        frontmatter["status"] = "done"
        mutated = True
    for phase in _iter_phase_mappings(frontmatter):
        if _normalized_status(phase.get("status")) == "done":
            continue
        phase["status"] = "done"
        mutated = True
    return mutated


def _mark_plan_frontmatter_in_progress(frontmatter: dict[str, Any]) -> bool:
    phases = _iter_phase_mappings(frontmatter)
    if not phases:
        return False

    phase_statuses = _phase_statuses(frontmatter)
    if any(status == "blocked" for status in phase_statuses):
        if _normalized_status(frontmatter.get("status")) == "blocked":
            return False
        frontmatter["status"] = "blocked"
        return True
    if any(status == "in_progress" for status in phase_statuses):
        if _normalized_status(frontmatter.get("status")) == "in_progress":
            return False
        frontmatter["status"] = "in_progress"
        return True

    for phase in phases:
        if _normalized_status(phase.get("status")) == "done":
            continue
        phase["status"] = "in_progress"
        break
    else:
        return False

    if _normalized_status(frontmatter.get("status")) != "in_progress":
        frontmatter["status"] = "in_progress"
    return True


def _sync_plan_frontmatter_status(frontmatter: dict[str, Any]) -> bool:
    phases = _iter_phase_mappings(frontmatter)
    if not phases:
        return False
    phase_statuses = [_normalized_status(phase.get("status")) for phase in phases]
    normalized_statuses = [status for status in phase_statuses if status is not None]
    if (
        len(normalized_statuses) == len(phase_statuses)
        and all(status == "done" for status in normalized_statuses)
    ):
        target_status = "done"
    elif any(status == "blocked" for status in normalized_statuses):
        target_status = "blocked"
    elif any(status in {"in_progress", "done"} for status in normalized_statuses):
        target_status = "in_progress"
    else:
        return False
    if _normalized_status(frontmatter.get("status")) == target_status:
        return False
    frontmatter["status"] = target_status
    return True


def normalize_done_plan(
    feature: dict[str, Any],
    feature_path: Path,
    feature_transitions: dict[str, set[str]],
) -> bool:
    """Normalize bundled plan state when the owning feature has reached `done`."""

    if feature.get("status") != "done":
        return False
    return _update_plan_progress_artifact(
        feature,
        feature_path,
        _PlanProgressUpdateConfig(
            allow_done_feature=True,
            feature_transitions=feature_transitions,
            mutate_frontmatter=_mark_plan_frontmatter_done,
        ),
    )


def touch_active_plan_for_iteration(
    feature: dict[str, Any],
    feature_path: Path,
    feature_transitions: dict[str, set[str]],
) -> bool:
    """Promote the active bundled plan into the next runnable iteration state."""

    return _update_plan_progress_artifact(
        feature,
        feature_path,
        _PlanProgressUpdateConfig(
            allow_done_feature=False,
            feature_transitions=feature_transitions,
            mutate_frontmatter=_mark_plan_frontmatter_in_progress,
            sync_feature_status=True,
        ),
    )


def sync_active_plan_after_implement(
    feature: dict[str, Any],
    feature_path: Path,
    feature_transitions: dict[str, set[str]],
) -> bool:
    """Sync bundled plan and feature statuses after an implement step finishes."""

    return _update_plan_progress_artifact(
        feature,
        feature_path,
        _PlanProgressUpdateConfig(
            allow_done_feature=False,
            feature_transitions=feature_transitions,
            mutate_frontmatter=_sync_plan_frontmatter_status,
            sync_feature_status=True,
        ),
    )


def archived_bundled_feature_is_done(
    archived_feature: dict[str, Any],
    archive_path: Path,
) -> bool:
    """Allow stale archived `in_progress` phases, but reject still-open phase work."""

    plan_path = resolve_feature_plan_path(archive_path, archived_feature)
    if plan_path is None or not plan_path.is_file():
        return True
    loaded_plan = load_plan_document_and_frontmatter(plan_path)
    if loaded_plan is None:
        return True

    _document, frontmatter = loaded_plan
    phase_statuses = _phase_statuses(frontmatter)
    if not phase_statuses:
        return True
    return all(status in {"done", "in_progress"} for status in phase_statuses)
