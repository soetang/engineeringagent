from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from engineeringagent.domain.specification import bundles


def _write_bundled_feature(feature_root: Path) -> tuple[Path, dict[str, object]]:
    spec_path = feature_root / "spec.yaml"
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, object] = {
        "id": "FEAT-181",
        "title": "Bundled feature",
        "type": "spec",
        "expected_commit_subject": "spec: bundled feature contract",
        "planning_tier": "planned",
        "status": "backlog",
        "priority": "high",
        "objective": "Validate bundled feature packages.",
        "acceptance": ["Validator enforces bundled feature contracts."],
        "artifacts": {"plan": "plan.md"},
    }
    spec_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    (feature_root / "plan.md").write_text(
        "---\n"
        "plan_id: FEAT-181\n"
        "feature_id: FEAT-181\n"
        "status: backlog\n"
        "source_spec: spec.yaml\n"
        "planning_tier: planned\n"
        "phases:\n"
        "  - id: P1\n"
        "    title: First phase\n"
        "    status: pending\n"
        "    verification:\n"
        "      - uv run pytest -q\n"
        "---\n"
        "# Plan\n",
        encoding="utf-8",
    )
    return spec_path, payload


def test_feature_progress_kind_tracks_plan_artifacts(tmp_path: Path) -> None:
    bundled_spec_path, bundled_feature_payload = _write_bundled_feature(
        tmp_path / "docs" / "spec" / "features" / "FEAT-181-bundled-feature-contract"
    )

    assert (
        bundles.feature_progress_kind(bundled_spec_path, bundled_feature_payload)
        == "phase"
    )


def test_feature_progress_kind_uses_feature_surface_for_direct_bundles(
    tmp_path: Path,
) -> None:
    feature_root = tmp_path / "docs" / "spec" / "features" / "FEAT-182-direct-bundle"
    spec_path = feature_root / "spec.yaml"
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, object] = {
        "id": "FEAT-182",
        "title": "Direct bundled feature",
        "type": "spec",
        "expected_commit_subject": "spec: direct bundled feature contract",
        "planning_tier": "direct",
        "status": "backlog",
        "priority": "high",
        "objective": "Validate bundled direct feature progress wording.",
        "acceptance": ["Bundled direct features do not fall back to subtasks."],
        "artifacts": {},
    }
    spec_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    assert bundles.feature_progress_kind(spec_path, payload) == "feature"


def test_plan_artifact_issues_validate_plan_linkage(tmp_path: Path) -> None:
    spec_path, feature_payload = _write_bundled_feature(
        tmp_path / "docs" / "spec" / "features" / "FEAT-181-bundled-feature-contract"
    )

    issues = bundles.plan_artifact_issues(spec_path, feature_payload, "plan.md")

    assert issues == []


def test_iter_feature_files_returns_only_bundled_specs(tmp_path: Path) -> None:
    features_dir = tmp_path / "docs" / "spec" / "features"
    bundled_spec_path, _payload = _write_bundled_feature(
        features_dir / "FEAT-181-example"
    )
    (features_dir / "FEAT-181-example.yaml").write_text(
        "id: FEAT-181\n",
        encoding="utf-8",
    )

    assert bundles.iter_feature_files(features_dir) == [bundled_spec_path]


def test_feature_storage_root_rejects_flat_entrypoints() -> None:
    with pytest.raises(ValueError, match="bundled spec.yaml"):
        bundles.feature_storage_root(Path("docs/spec/features/FEAT-181-example.yaml"))


def test_resolve_feature_package_paths_reports_configured_active_root(
    tmp_path: Path,
) -> None:
    active_dir = tmp_path / "docs" / "specifications" / "features"
    done_dir = tmp_path / "docs" / "specifications" / "features_done"
    outside_spec = tmp_path / "elsewhere" / "FEAT-181-example" / "spec.yaml"
    outside_spec.parent.mkdir(parents=True)
    outside_spec.write_text("id: FEAT-181\n", encoding="utf-8")

    with pytest.raises(
        ValueError,
        match=(
            "completed feature archive source must be under "
            f"{active_dir.as_posix()}"
        ),
    ):
        bundles.resolve_feature_package_paths(active_dir, done_dir, outside_spec)
