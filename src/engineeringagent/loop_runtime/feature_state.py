"""Loop runtime feature state helpers."""

from __future__ import annotations

import errno
import shutil
from pathlib import Path
from typing import Any, Sequence

import yaml

from engineeringagent.application import (
    InitialFeatureLoadOutcome,
    PostImplementFeatureOutcome,
)
from engineeringagent.application import feature_plan_progress
from engineeringagent.application.feature_plan_progress import (
    archived_bundled_feature_is_done as _archived_bundled_feature_is_done,
)
from engineeringagent.application.feature_plan_progress import (
    normalize_done_plan,
    sync_active_plan_after_implement,
    touch_active_plan_for_iteration,
)
from engineeringagent.domain.shared import utc_now_iso
from engineeringagent.config import resolve_docs_root
from engineeringagent.specs import (
    _is_bundled_feature_spec_path,
    dump_yaml,
    feature_storage_root,
    iter_feature_files,
    load_yaml,
    resolve_feature_package_paths,
)

FEATURE_TRANSITIONS: dict[str, set[str]] = {
    "backlog": {"backlog", "in_progress", "done"},
    "in_progress": {"in_progress", "blocked", "done"},
    "blocked": {"blocked", "in_progress", "done"},
    "done": {"done"},
}

RUN_ALL_RUNNABLE_STATUSES: set[str] = {"backlog", "in_progress"}

# Keep the extracted bundled-plan loader available on this module for tests and
# any remaining compatibility callers.
_load_plan_document_and_frontmatter = (
    feature_plan_progress.load_plan_document_and_frontmatter
)


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


def set_status(entity: dict[str, Any], target: str, kind: str = "feature") -> None:
    """Transition a feature or progress entity status with guardrails."""
    current = str(entity.get("status", ""))
    allowed = FEATURE_TRANSITIONS.get(current)
    if not allowed:
        raise ValueError(f"{kind} has unknown status: {current}")
    if target not in allowed:
        raise ValueError(f"illegal {kind} status transition: {current} -> {target}")
    entity["status"] = target


def resolve_feature_paths(
    project_root: Path, feature_paths: Sequence[str | Path]
) -> list[Path]:
    """Resolve and validate user-supplied feature spec paths."""
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
        if not _is_bundled_feature_spec_path(candidate):
            raise ValueError(
                "feature specs must use bundled spec.yaml entrypoints: "
                f"{raw_path}"
            )

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


def discover_active_feature_paths(project_root: Path) -> list[Path]:
    """Discover runnable feature specs from docs/spec/features."""
    features_dir, _ = _resolve_spec_directories(project_root)
    resolved: list[Path] = []
    for feature_path in iter_feature_files(features_dir):
        try:
            feature = load_yaml(feature_path)
        except Exception as exc:  # noqa: BLE001
            raise ValueError(
                f"failed to load feature YAML at {feature_path}: {exc}"
            ) from exc

        if str(feature.get("status", "")) in RUN_ALL_RUNNABLE_STATUSES:
            resolved.append(feature_path)

    return resolved


def pending_features(
    feature_paths: Sequence[Path],
) -> list[tuple[Path, dict[str, Any]]]:
    """Load non-done feature specs from an explicit path list."""
    pending: list[tuple[Path, dict[str, Any]]] = []
    for feature_path in feature_paths:
        feature = load_yaml(feature_path)
        if feature.get("status") == "done":
            continue
        pending.append((feature_path, feature))
    return pending


def done_features_pending_archive(
    feature_paths: Sequence[Path],
) -> list[tuple[Path, dict[str, Any]]]:
    """Load done feature specs that are candidates for archive flow."""
    done_features: list[tuple[Path, dict[str, Any]]] = []
    for feature_path in feature_paths:
        feature = load_yaml(feature_path)
        if feature.get("status") != "done":
            continue
        done_features.append((feature_path, feature))
    return done_features


def _resolve_archive_path(project_root: Path, feature_path: Path) -> Path:
    active_dir, done_dir = _resolve_spec_directories(project_root)
    return resolve_feature_package_paths(
        active_dir,
        done_dir,
        feature_path,
    ).archive_spec_path


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
        active_dir, done_dir = _resolve_spec_directories(project_root)
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
