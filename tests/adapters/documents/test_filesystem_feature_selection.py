from __future__ import annotations

from pathlib import Path

import pytest

from engineeringagent.adapters.documents.filesystem_feature_selection import (
    discover_active_feature_paths,
    done_features_pending_archive,
    pending_features,
    resolve_feature_paths,
)


def test_resolve_feature_paths_validates_bundled_yaml_entrypoints(
    tmp_path: Path,
) -> None:
    """Reject non-bundled paths and deduplicate valid spec entrypoints."""
    with pytest.raises(ValueError, match="at least one feature"):
        resolve_feature_paths(tmp_path, [])

    txt_path = tmp_path / "feature.txt"
    txt_path.write_text("id: FEAT-001\n", encoding="utf-8")
    with pytest.raises(ValueError, match="must end with .yaml"):
        resolve_feature_paths(tmp_path, [txt_path])

    directory_path = tmp_path / "feature.yaml"
    directory_path.mkdir()
    with pytest.raises(ValueError, match="is not a file"):
        resolve_feature_paths(tmp_path, [directory_path])

    flat_yaml = tmp_path / "flat.yaml"
    flat_yaml.write_text("id: FEAT-001\nstatus: backlog\n", encoding="utf-8")
    with pytest.raises(
        ValueError, match="feature specs must use bundled spec.yaml entrypoints"
    ):
        resolve_feature_paths(tmp_path, [flat_yaml])

    bad_yaml_root = tmp_path / "docs" / "spec" / "features" / "FEAT-000-bad"
    bad_yaml_root.mkdir(parents=True)
    bad_yaml = bad_yaml_root / "spec.yaml"
    bad_yaml.write_text("[", encoding="utf-8")
    with pytest.raises(ValueError, match="failed to load feature YAML"):
        resolve_feature_paths(tmp_path, [bad_yaml])

    bundled_root = tmp_path / "docs" / "spec" / "features" / "FEAT-001-good"
    bundled_root.mkdir(parents=True)
    good_yaml = bundled_root / "spec.yaml"
    good_yaml.write_text("id: FEAT-001\nstatus: backlog\n", encoding="utf-8")

    resolved = resolve_feature_paths(
        tmp_path,
        [good_yaml.relative_to(tmp_path), good_yaml],
    )

    assert resolved == [good_yaml.resolve()]


def test_discover_active_feature_paths_filters_to_runnable_statuses(
    tmp_path: Path,
) -> None:
    """Return only backlog and in-progress feature specs."""
    features_dir = tmp_path / "docs" / "spec" / "features"
    backlog_spec = features_dir / "FEAT-001" / "spec.yaml"
    backlog_spec.parent.mkdir(parents=True, exist_ok=True)
    backlog_spec.write_text("id: FEAT-001\nstatus: backlog\n", encoding="utf-8")

    done_spec = features_dir / "FEAT-002" / "spec.yaml"
    done_spec.parent.mkdir(parents=True, exist_ok=True)
    done_spec.write_text("id: FEAT-002\nstatus: done\n", encoding="utf-8")

    assert discover_active_feature_paths(tmp_path) == [backlog_spec]


def test_discover_active_feature_paths_surfaces_yaml_load_failures(
    tmp_path: Path,
) -> None:
    """Surface invalid YAML while scanning the active feature root."""
    broken_spec = (
        tmp_path / "docs" / "spec" / "features" / "FEAT-999-broken" / "spec.yaml"
    )
    broken_spec.parent.mkdir(parents=True, exist_ok=True)
    broken_spec.write_text("[", encoding="utf-8")

    with pytest.raises(ValueError, match="failed to load feature YAML"):
        discover_active_feature_paths(tmp_path)


def test_pending_and_done_feature_helpers_partition_loaded_specs(
    tmp_path: Path,
) -> None:
    """Split loaded specs into pending and done archive candidates."""
    feature_one = tmp_path / "feature-one.yaml"
    feature_one.write_text("id: FEAT-010\nstatus: backlog\n", encoding="utf-8")
    feature_two = tmp_path / "feature-two.yaml"
    feature_two.write_text("id: FEAT-011\nstatus: done\n", encoding="utf-8")

    assert pending_features([feature_one, feature_two]) == [
        (feature_one, {"id": "FEAT-010", "status": "backlog"})
    ]
    assert done_features_pending_archive([feature_one, feature_two]) == [
        (feature_two, {"id": "FEAT-011", "status": "done"})
    ]
