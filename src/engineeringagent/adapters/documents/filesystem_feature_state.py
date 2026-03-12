"""Filesystem-backed feature state helpers for loop runtime coordination."""

from __future__ import annotations

import errno
import shutil
from pathlib import Path
from typing import Any, Callable, Sequence

from pydantic import BaseModel, ConfigDict
import yaml

from engineeringagent.adapters.documents.filesystem_feature_selection import (
    resolve_spec_directories,
)
from engineeringagent.domain.specification import (
    InitialFeatureLoadOutcome,
    PostImplementFeatureOutcome,
)
from engineeringagent.domain.shared import utc_now_iso
from engineeringagent.specs import (
    dump_yaml,
    feature_storage_root,
    load_markdown_frontmatter,
    load_yaml,
    resolve_feature_package_paths,
    resolve_feature_plan_path,
)

FEATURE_TRANSITIONS: dict[str, set[str]] = {
    "backlog": {"backlog", "in_progress", "done"},
    "in_progress": {"in_progress", "blocked", "done"},
    "blocked": {"blocked", "in_progress", "done"},
    "done": {"done"},
}


class _PlanProgressUpdateConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    allow_done_feature: bool
    feature_transitions: dict[str, set[str]]
    mutate_frontmatter: Callable[[dict[str, Any]], bool]
    sync_feature_status: bool = False


def _move_path(source: Path, destination: Path) -> None:
    """Move a path while handling cross-device boundaries."""
    try:
        source.rename(destination)
    except OSError as exc:
        if exc.errno != errno.EXDEV:
            raise
        shutil.move(str(source), str(destination))


def _normalize_done_progress_artifacts(feature: dict[str, Any], feature_path: Path) -> bool:
    return normalize_done_plan(feature, feature_path, FEATURE_TRANSITIONS)


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


def _archived_bundled_feature_is_done(
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


def set_status(entity: dict[str, Any], target: str, kind: str = "feature") -> None:
    """Transition a feature or progress entity status with guardrails."""
    current = str(entity.get("status", ""))
    allowed = FEATURE_TRANSITIONS.get(current)
    if not allowed:
        raise ValueError(f"{kind} has unknown status: {current}")
    if target not in allowed:
        raise ValueError(f"illegal {kind} status transition: {current} -> {target}")
    entity["status"] = target


def _resolve_archive_path(project_root: Path, feature_path: Path) -> Path:
    active_dir, done_dir = resolve_spec_directories(project_root)
    return resolve_feature_package_paths(
        active_dir,
        done_dir,
        feature_path,
    ).archive_spec_path


def _load_selected_feature(
    feature_path: Path,
) -> tuple[dict[str, Any] | None, str | None]:
    try:
        return (load_yaml(feature_path), None)
    except FileNotFoundError:
        return (
            None,
            f"selected feature path disappeared during loop iteration: {feature_path}",
        )
    except (OSError, ValueError, yaml.YAMLError) as exc:
        return (None, f"failed to load selected feature YAML: {exc}")


def _load_archived_selected_feature_after_implement(
    project_root: Path,
    feature_path: Path,
) -> tuple[dict[str, Any] | None, Path | None]:
    try:
        archive_path = _resolve_archive_path(project_root, feature_path)
    except ValueError:
        return (None, None)

    if not archive_path.exists():
        return (None, None)

    try:
        archived_feature = load_yaml(archive_path)
    except (OSError, ValueError, yaml.YAMLError):
        return (None, None)

    if archived_feature.get("status") != "done":
        return (None, None)
    if not _archived_bundled_feature_is_done(archived_feature, archive_path):
        return (None, None)

    if _normalize_done_progress_artifacts(archived_feature, archive_path):
        dump_yaml(archive_path, archived_feature)

    return (archived_feature, archive_path)


def _post_implement_failed(
    *,
    feature: dict[str, Any] | None,
    failed_gate: str,
    feedback: str,
) -> PostImplementFeatureOutcome:
    return PostImplementFeatureOutcome(
        feature=feature,
        archived_in_iteration=False,
        archived_path=None,
        result="failed",
        failed_gate=failed_gate,
        feedback=feedback,
    )


def _post_implement_passed(
    *,
    feature: dict[str, Any] | None,
    archived_in_iteration: bool = False,
    archived_path: Path | None = None,
) -> PostImplementFeatureOutcome:
    return PostImplementFeatureOutcome(
        feature=feature,
        archived_in_iteration=archived_in_iteration,
        archived_path=archived_path,
        result="passed",
        failed_gate=None,
        feedback=None,
    )


def evaluate_initial_feature_load(
    feature_path: Path,
) -> InitialFeatureLoadOutcome:
    """Load the selected feature and map file/load errors to gate feedback."""
    feature, load_error = _load_selected_feature(feature_path)
    if load_error:
        return InitialFeatureLoadOutcome(
            feature=feature,
            result="failed",
            failed_gate="feature_missing",
            feedback=load_error,
        )
    return InitialFeatureLoadOutcome(
        feature=feature,
        result="passed",
        failed_gate=None,
        feedback=None,
    )


def refresh_feature_after_implement(
    project_root: Path,
    feature_path: Path,
) -> PostImplementFeatureOutcome:
    """Reload selected feature after implement; fallback to done archive path."""
    post_feature, post_load_error = _load_selected_feature(feature_path)

    if post_load_error is None:
        if post_feature is not None:
            sync_active_plan_after_implement(
                post_feature,
                feature_path,
                FEATURE_TRANSITIONS,
            )
        return _post_implement_passed(
            feature=post_feature,
        )

    if not feature_path.exists():
        archived_feature, archived_path = (
            _load_archived_selected_feature_after_implement(
                project_root,
                feature_path,
            )
        )
        if archived_feature is not None and archived_path is not None:
            return _post_implement_passed(
                feature=archived_feature,
                archived_in_iteration=True,
                archived_path=archived_path,
            )

    return _post_implement_failed(
        feature=post_feature,
        failed_gate="feature_missing",
        feedback=post_load_error,
    )


def archive_completed_feature(
    project_root: Path, feature_path: Path
) -> tuple[bool, Path | None, str]:
    """Move a done feature spec to docs/spec/features_done safely."""
    try:
        active_dir, done_dir = resolve_spec_directories(project_root)
        package_paths = resolve_feature_package_paths(active_dir, done_dir, feature_path)
    except ValueError as exc:
        return (False, None, str(exc))

    if not feature_path.exists():
        return (False, None, f"completed feature spec not found: {feature_path}")
    if package_paths.archive_root.exists():
        return (
            False,
            None,
            f"archive destination already exists: {package_paths.archive_spec_path}",
        )

    try:
        feature = load_yaml(feature_path)
    except (OSError, ValueError, yaml.YAMLError) as exc:
        return (
            False,
            None,
            f"failed to load completed feature spec for archive: {exc}",
        )

    if _normalize_done_progress_artifacts(feature, feature_path):
        dump_yaml(feature_path, feature)

    package_paths.archive_root.parent.mkdir(parents=True, exist_ok=True)
    try:
        _move_path(package_paths.active_root, package_paths.archive_root)
    except OSError as exc:
        return (False, None, f"failed to archive completed feature spec: {exc}")
    return (True, package_paths.archive_spec_path, "")


def restore_archived_feature(
    archived_path: Path, original_feature_path: Path
) -> tuple[bool, str]:
    """Restore an archived feature spec to its original active location."""
    if not archived_path.exists():
        return (True, "")
    archived_root = feature_storage_root(archived_path)
    original_root = feature_storage_root(original_feature_path)
    if original_root.exists():
        return (
            False,
            "cannot restore archived feature path because source already exists",
        )
    original_root.parent.mkdir(parents=True, exist_ok=True)
    try:
        _move_path(archived_root, original_root)
    except OSError as exc:
        return (False, f"failed to restore archived feature spec: {exc}")
    return (True, "")


def ready_for_active_iteration(
    result: str,
    feature: dict[str, Any] | None,
) -> bool:
    """Check active-iteration eligibility."""
    return result == "passed" and feature is not None


def should_archive_selected_feature(
    result: str,
    selected_feature: dict[str, Any] | None,
) -> bool:
    """Decide whether the selected feature should be archived."""
    return (
        result == "passed"
        and selected_feature is not None
        and selected_feature.get("status") == "done"
    )


def touch_active_feature_for_iteration(
    feature: dict[str, Any],
    feature_path: Path,
) -> None:
    """Apply status/timestamp updates before iteration work."""
    if feature.get("status") == "backlog":
        set_status(feature, "in_progress")
    feature["updated_at"] = utc_now_iso()
    dump_yaml(feature_path, feature)
    touch_active_plan_for_iteration(feature, feature_path, FEATURE_TRANSITIONS)
