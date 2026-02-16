"""Loop runtime feature state helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence

from engineeringagent.config import resolve_docs_root
from engineeringagent.loop_runtime.models import (
    InitialFeatureLoadOutcome,
    PostImplementFeatureOutcome,
)
from engineeringagent.loop_runtime.telemetry import now_iso
from engineeringagent.specs import dump_yaml, load_yaml

FEATURE_TRANSITIONS: dict[str, set[str]] = {
    "backlog": {"backlog", "in_progress", "done"},
    "in_progress": {"in_progress", "blocked", "done"},
    "blocked": {"blocked", "in_progress", "done"},
    "done": {"done"},
}

RUN_ALL_RUNNABLE_STATUSES: set[str] = {"backlog", "in_progress"}


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


def _load_selected_feature_with_archive_fallback(
    project_root: Path,
    feature_path: Path,
) -> tuple[dict[str, Any] | None, bool, str | None]:
    try:
        return (load_yaml(feature_path), False, None)
    except FileNotFoundError:
        try:
            archive_path = _resolve_archive_path(project_root, feature_path)
        except ValueError:
            return (
                None,
                False,
                (
                    "selected feature path disappeared during loop iteration and "
                    f"cannot be archive-resolved: {feature_path}"
                ),
            )

        if not archive_path.exists():
            return (
                None,
                False,
                (
                    "selected feature path disappeared during loop iteration: "
                    f"{feature_path}. Expected archived counterpart at {archive_path}."
                ),
            )

        try:
            archived_feature = load_yaml(archive_path)
        except Exception as exc:  # noqa: BLE001
            return (
                None,
                False,
                f"failed to load archived feature YAML at {archive_path}: {exc}",
            )

        print(
            "Selected feature path missing after iteration; "
            f"using archived counterpart at {archive_path}."
        )
        return (archived_feature, True, None)


def _archived_feature_mismatch_feedback(
    feature: dict[str, Any] | None,
    feature_path: Path,
    *,
    missing_message: str,
    done_message: str,
) -> str:
    if feature is None:
        return f"{missing_message} path={feature_path}"
    if feature.get("status") != "done":
        return _archived_status_not_done_feedback(feature_path)
    return f"{done_message} path={feature_path}"


def _archived_status_not_done_feedback(feature_path: Path) -> str:
    return (
        "selected feature was archived but archived status is not done; "
        "restore the active spec path and rerun. "
        f"path={feature_path}"
    )


def _post_implement_failed(
    *,
    feature: dict[str, Any] | None,
    loaded_from_archive: bool,
    failed_gate: str,
    hook_feedback: str,
) -> PostImplementFeatureOutcome:
    return PostImplementFeatureOutcome(
        feature=feature,
        loaded_from_archive=loaded_from_archive,
        archived_in_iteration=False,
        archived_path=None,
        result="failed",
        failed_gate=failed_gate,
        hook_feedback=hook_feedback,
    )


def _post_implement_passed(
    *,
    feature: dict[str, Any] | None,
    loaded_from_archive: bool,
    archived_in_iteration: bool = False,
    archived_path: Path | None = None,
) -> PostImplementFeatureOutcome:
    return PostImplementFeatureOutcome(
        feature=feature,
        loaded_from_archive=loaded_from_archive,
        archived_in_iteration=archived_in_iteration,
        archived_path=archived_path,
        result="passed",
        failed_gate=None,
        hook_feedback=None,
    )


def _initial_feature_load_outcome(
    *,
    feature: dict[str, Any] | None,
    loaded_from_archive: bool,
    result: str,
    failed_gate: str | None,
    hook_feedback: str | None,
) -> InitialFeatureLoadOutcome:
    return InitialFeatureLoadOutcome(
        feature=feature,
        loaded_from_archive=loaded_from_archive,
        result=result,
        failed_gate=failed_gate,
        hook_feedback=hook_feedback,
    )


def _evaluate_initial_feature_load(
    project_root: Path,
    feature_path: Path,
) -> InitialFeatureLoadOutcome:
    feature, loaded_from_archive, load_error = (
        _load_selected_feature_with_archive_fallback(project_root, feature_path)
    )
    if load_error:
        return _initial_feature_load_outcome(
            feature=feature,
            loaded_from_archive=loaded_from_archive,
            result="failed",
            failed_gate="feature_missing",
            hook_feedback=load_error,
        )
    if loaded_from_archive:
        return _initial_feature_load_outcome(
            feature=feature,
            loaded_from_archive=loaded_from_archive,
            result="failed",
            failed_gate="feature_missing",
            hook_feedback=_archived_feature_mismatch_feedback(
                feature,
                feature_path,
                missing_message=(
                    "selected feature path is missing and only archived fallback was "
                    "found without a same-iteration completion commit; restore the "
                    "active spec path and rerun."
                ),
                done_message=(
                    "selected feature path is already archived with status=done, but "
                    "this iteration did not create a completion commit for that "
                    "feature; restore the active feature spec or commit the intended "
                    "completion changes, then rerun."
                ),
            ),
        )
    return _initial_feature_load_outcome(
        feature=feature,
        loaded_from_archive=loaded_from_archive,
        result="passed",
        failed_gate=None,
        hook_feedback=None,
    )


def _refresh_feature_after_implement(
    project_root: Path,
    feature_path: Path,
    *,
    selected_started_active: bool,
) -> PostImplementFeatureOutcome:
    post_feature, loaded_post_from_archive, post_load_error = (
        _load_selected_feature_with_archive_fallback(project_root, feature_path)
    )

    def _failed(failed_gate: str, hook_feedback: str) -> PostImplementFeatureOutcome:
        return _post_implement_failed(
            feature=post_feature,
            loaded_from_archive=loaded_post_from_archive,
            failed_gate=failed_gate,
            hook_feedback=hook_feedback,
        )

    if post_load_error:
        return _failed(
            failed_gate="feature_missing",
            hook_feedback=post_load_error,
        )

    if loaded_post_from_archive:
        if selected_started_active and post_feature is not None:
            if post_feature.get("status") == "done":
                try:
                    archived_path = _resolve_archive_path(project_root, feature_path)
                except ValueError:
                    return _failed(
                        failed_gate="feature_archive",
                        hook_feedback=(
                            "selected feature path moved to archive during loop "
                            "iteration but archive path could not be resolved; "
                            "restore the active spec path and rerun. "
                            f"path={feature_path}"
                        ),
                    )
                return _post_implement_passed(
                    feature=post_feature,
                    loaded_from_archive=loaded_post_from_archive,
                    archived_in_iteration=True,
                    archived_path=archived_path,
                )
            return _failed(
                failed_gate="feature_missing",
                hook_feedback=_archived_status_not_done_feedback(feature_path),
            )

        return _failed(
            failed_gate="feature_missing",
            hook_feedback=_archived_feature_mismatch_feedback(
                post_feature,
                feature_path,
                missing_message=(
                    "selected feature path disappeared during loop iteration and only "
                    "archived fallback was found without a same-iteration completion "
                    "commit; restore the active spec path and rerun."
                ),
                done_message=(
                    "selected feature path was moved to docs/spec/features_done with "
                    "status=done before completion commit in this iteration; restore "
                    "the active feature spec or commit the intended completion "
                    "changes, then rerun."
                ),
            ),
        )

    return _post_implement_passed(
        feature=post_feature,
        loaded_from_archive=loaded_post_from_archive,
    )


def _ready_for_active_iteration(
    *,
    result: str,
    feature: dict[str, Any] | None,
    loaded_from_archive: bool,
) -> bool:
    return result == "passed" and feature is not None and not loaded_from_archive


def _should_archive_selected_feature(
    *,
    result: str,
    selected_feature: dict[str, Any] | None,
    loaded_from_archive: bool,
) -> bool:
    return (
        result == "passed"
        and selected_feature is not None
        and selected_feature.get("status") == "done"
        and not loaded_from_archive
    )


def _touch_active_feature_for_iteration(
    feature: dict[str, Any],
    feature_path: Path,
) -> None:
    if feature.get("status") == "backlog":
        set_status(feature, "in_progress")
    feature["updated_at"] = now_iso()
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

    archive_path.parent.mkdir(parents=True, exist_ok=True)
    feature_path.rename(archive_path)
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
    archived_path.rename(original_feature_path)
    return (True, "")
