"""Loop runtime feature state helpers."""

from __future__ import annotations

import errno
from pathlib import Path
import shutil
from typing import Any, Sequence

import yaml

from engineeringagent.config import resolve_docs_root
from engineeringagent.loop_runtime.models import (
    InitialFeatureLoadOutcome,
    PostImplementFeatureOutcome,
)
from engineeringagent.progress import handoff as progress_handoff
from engineeringagent.specs import dump_yaml, load_yaml

FEATURE_TRANSITIONS: dict[str, set[str]] = {
    "backlog": {"backlog", "in_progress", "done"},
    "in_progress": {"in_progress", "blocked", "done"},
    "blocked": {"blocked", "in_progress", "done"},
    "done": {"done"},
}

RUN_ALL_RUNNABLE_STATUSES: set[str] = {"backlog", "in_progress"}


def _move_path(source: Path, destination: Path) -> None:
    """Move a path while handling cross-device boundaries."""
    try:
        source.rename(destination)
    except OSError as exc:
        if exc.errno != errno.EXDEV:
            raise
        shutil.move(str(source), str(destination))


def _normalize_done_subtasks(feature: dict[str, Any]) -> bool:
    if feature.get("status") != "done":
        return False
    subtasks = feature.get("subtasks")
    if not isinstance(subtasks, list) or not subtasks:
        return False
    mutated = False
    for subtask in subtasks:
        if not isinstance(subtask, dict):
            continue
        if subtask.get("status") == "done":
            continue
        subtask["status"] = "done"
        mutated = True
    return mutated


def set_status(entity: dict[str, Any], target: str, kind: str = "feature") -> None:
    """Transition a feature or subtask status with guardrails."""
    current = str(entity.get("status", ""))
    allowed = FEATURE_TRANSITIONS.get(current)
    if not allowed:
        raise ValueError(f"{kind} has unknown status: {current}")
    if target not in allowed:
        raise ValueError(f"illegal {kind} status transition: {current} -> {target}")
    entity["status"] = target


def _resolve_feature_paths(
    project_root: Path, feature_paths: Sequence[str | Path]
) -> list[Path]:
    if not feature_paths:
        raise ValueError("at least one feature spec path is required")

    resolved: list[Path] = []
    seen: set[Path] = set()
    for raw_path in feature_paths:
        candidate = Path(raw_path)
        if not candidate.is_absolute():
            candidate = (project_root / candidate).resolve()
        else:
            candidate = candidate.resolve()

        if candidate.suffix not in {".yaml", ".yml"}:
            raise ValueError(f"feature path must end with .yaml or .yml: {raw_path}")
        if not candidate.exists():
            raise ValueError(f"feature path does not exist: {raw_path}")
        if not candidate.is_file():
            raise ValueError(f"feature path is not a file: {raw_path}")

        try:
            load_yaml(candidate)
        except Exception as exc:  # noqa: BLE001
            raise ValueError(
                f"failed to load feature YAML at {raw_path}: {exc}"
            ) from exc

        if candidate in seen:
            continue
        seen.add(candidate)
        resolved.append(candidate)

    return resolved


def _discover_active_feature_paths(project_root: Path) -> list[Path]:
    features_dir, _ = _resolve_spec_directories(project_root)
    resolved: list[Path] = []
    for feature_path in sorted(features_dir.glob("*.yaml")):
        try:
            feature = load_yaml(feature_path)
        except Exception as exc:  # noqa: BLE001
            raise ValueError(
                f"failed to load feature YAML at {feature_path}: {exc}"
            ) from exc

        if str(feature.get("status", "")) in RUN_ALL_RUNNABLE_STATUSES:
            resolved.append(feature_path)

    return resolved


def _pending_features(
    feature_paths: Sequence[Path],
) -> list[tuple[Path, dict[str, Any]]]:
    pending: list[tuple[Path, dict[str, Any]]] = []
    for feature_path in feature_paths:
        feature = load_yaml(feature_path)
        if feature.get("status") == "done":
            continue
        pending.append((feature_path, feature))
    return pending


def _done_features_pending_archive(
    feature_paths: Sequence[Path],
) -> list[tuple[Path, dict[str, Any]]]:
    done_features: list[tuple[Path, dict[str, Any]]] = []
    for feature_path in feature_paths:
        feature = load_yaml(feature_path)
        if feature.get("status") != "done":
            continue
        done_features.append((feature_path, feature))
    return done_features


def _resolve_archive_path(project_root: Path, feature_path: Path) -> Path:
    active_dir, done_dir = _resolve_spec_directories(project_root)
    resolved_feature = feature_path.resolve()

    if resolved_feature.parent != active_dir:
        raise ValueError(
            "completed feature archive source must be under docs/spec/features"
        )
    return done_dir / resolved_feature.name


def _resolve_spec_directories(project_root: Path) -> tuple[Path, Path]:
    docs_root = resolve_docs_root(project_root)
    spec_root = docs_root / "spec"
    return (
        (spec_root / "features").resolve(),
        (spec_root / "features_done").resolve(),
    )


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

    if _normalize_done_subtasks(archived_feature):
        dump_yaml(archive_path, archived_feature)

    return (archived_feature, archive_path)


def _post_implement_failed(
    *,
    feature: dict[str, Any] | None,
    failed_gate: str,
    hook_feedback: str,
) -> PostImplementFeatureOutcome:
    return PostImplementFeatureOutcome(
        feature=feature,
        archived_in_iteration=False,
        archived_path=None,
        result="failed",
        failed_gate=failed_gate,
        hook_feedback=hook_feedback,
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
        hook_feedback=None,
    )


def _initial_feature_load_outcome(
    *,
    feature: dict[str, Any] | None,
    result: str,
    failed_gate: str | None,
    hook_feedback: str | None,
) -> InitialFeatureLoadOutcome:
    return InitialFeatureLoadOutcome(
        feature=feature,
        result=result,
        failed_gate=failed_gate,
        hook_feedback=hook_feedback,
    )


def _evaluate_initial_feature_load(
    feature_path: Path,
) -> InitialFeatureLoadOutcome:
    feature, load_error = _load_selected_feature(feature_path)
    if load_error:
        return _initial_feature_load_outcome(
            feature=feature,
            result="failed",
            failed_gate="feature_missing",
            hook_feedback=load_error,
        )
    return _initial_feature_load_outcome(
        feature=feature,
        result="passed",
        failed_gate=None,
        hook_feedback=None,
    )


def _refresh_feature_after_implement(
    project_root: Path,
    feature_path: Path,
) -> PostImplementFeatureOutcome:
    post_feature, post_load_error = _load_selected_feature(feature_path)

    if post_load_error is None:
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
        hook_feedback=post_load_error,
    )


def _ready_for_active_iteration(
    *,
    result: str,
    feature: dict[str, Any] | None,
) -> bool:
    return result == "passed" and feature is not None


def _should_archive_selected_feature(
    *,
    result: str,
    selected_feature: dict[str, Any] | None,
) -> bool:
    return (
        result == "passed"
        and selected_feature is not None
        and selected_feature.get("status") == "done"
    )


def _touch_active_feature_for_iteration(
    feature: dict[str, Any],
    feature_path: Path,
) -> None:
    if feature.get("status") == "backlog":
        set_status(feature, "in_progress")
    feature["updated_at"] = progress_handoff.now_iso()
    dump_yaml(feature_path, feature)


def _archive_completed_feature(
    project_root: Path, feature_path: Path
) -> tuple[bool, Path | None, str]:
    try:
        archive_path = _resolve_archive_path(project_root, feature_path)
    except ValueError as exc:
        return (False, None, str(exc))

    if not feature_path.exists():
        return (False, None, f"completed feature spec not found: {feature_path}")
    if archive_path.exists():
        return (
            False,
            None,
            f"archive destination already exists: {archive_path}",
        )

    try:
        feature = load_yaml(feature_path)
    except (OSError, ValueError, yaml.YAMLError) as exc:
        return (
            False,
            None,
            f"failed to load completed feature spec for archive: {exc}",
        )

    if _normalize_done_subtasks(feature):
        dump_yaml(feature_path, feature)

    archive_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        _move_path(feature_path, archive_path)
    except OSError as exc:
        return (False, None, f"failed to archive completed feature spec: {exc}")
    return (True, archive_path, "")


def _restore_archived_feature(
    archived_path: Path, original_feature_path: Path
) -> tuple[bool, str]:
    if not archived_path.exists():
        return (True, "")
    if original_feature_path.exists():
        return (
            False,
            "cannot restore archived feature path because source already exists",
        )
    original_feature_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        _move_path(archived_path, original_feature_path)
    except OSError as exc:
        return (False, f"failed to restore archived feature spec: {exc}")
    return (True, "")


def resolve_feature_paths(
    project_root: Path, feature_paths: Sequence[str | Path]
) -> list[Path]:
    """Public service seam for resolving explicit feature spec paths."""
    return _resolve_feature_paths(project_root, feature_paths)


def discover_active_feature_paths(project_root: Path) -> list[Path]:
    """Public service seam for discovering runnable active feature specs."""
    return _discover_active_feature_paths(project_root)


def pending_features(
    feature_paths: Sequence[Path],
) -> list[tuple[Path, dict[str, Any]]]:
    """Public service seam returning non-done features for loop selection."""
    return _pending_features(feature_paths)


def done_features_pending_archive(
    feature_paths: Sequence[Path],
) -> list[tuple[Path, dict[str, Any]]]:
    """Public service seam returning done features that can still be archived."""
    return _done_features_pending_archive(feature_paths)


def evaluate_initial_feature_load(
    feature_path: Path,
) -> InitialFeatureLoadOutcome:
    """Public service seam for loading selected feature state."""
    return _evaluate_initial_feature_load(feature_path)


def refresh_feature_after_implement(
    project_root: Path,
    feature_path: Path,
) -> PostImplementFeatureOutcome:
    """Public service seam for reloading feature state after implement."""
    return _refresh_feature_after_implement(project_root, feature_path)


def ready_for_active_iteration(
    result: str,
    feature: dict[str, Any] | None,
) -> bool:
    """Public service seam for checking active-iteration eligibility."""
    return _ready_for_active_iteration(
        result=result,
        feature=feature,
    )


def should_archive_selected_feature(
    result: str,
    selected_feature: dict[str, Any] | None,
) -> bool:
    """Public service seam for deciding whether a selected feature should archive."""
    return _should_archive_selected_feature(
        result=result,
        selected_feature=selected_feature,
    )


def touch_active_feature_for_iteration(
    feature: dict[str, Any],
    feature_path: Path,
) -> None:
    """Public service seam for status/timestamp updates before iteration work."""
    _touch_active_feature_for_iteration(feature, feature_path)


def archive_completed_feature(
    project_root: Path, feature_path: Path
) -> tuple[bool, Path | None, str]:
    """Public service seam for archiving a completed feature spec."""
    return _archive_completed_feature(project_root, feature_path)


def restore_archived_feature(
    archived_path: Path, original_feature_path: Path
) -> tuple[bool, str]:
    """Public service seam for restoring archived spec on gate/reviewer failures."""
    return _restore_archived_feature(archived_path, original_feature_path)
