"""Filesystem-backed feature selection and path discovery helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence

from engineeringagent.adapters.config import resolve_specifications_root
from engineeringagent.domain.specification import (
    iter_feature_files,
    load_yaml,
)
from engineeringagent.domain.specification.bundles import is_bundled_feature_spec_path

RUN_ALL_RUNNABLE_STATUSES: set[str] = {"backlog", "in_progress"}


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
        if not is_bundled_feature_spec_path(candidate):
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
    """Discover runnable feature specs from the active feature package root."""
    features_dir, _ = resolve_spec_directories(project_root)
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


def resolve_spec_directories(project_root: Path) -> tuple[Path, Path]:
    """Resolve active and archived feature package roots for the repository."""
    spec_root = resolve_specifications_root(project_root)
    return (
        (spec_root / "features").resolve(),
        (spec_root / "features_done").resolve(),
    )
