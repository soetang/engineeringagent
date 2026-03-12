from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from engineeringagent.adapters.documents import FilesystemFeatureSpecificationRepository
from engineeringagent.adapters.documents.filesystem_feature_specification_repository import (
    discover_active_feature_paths,
    load_selection_candidates,
    resolve_feature_paths,
)
from engineeringagent.domain.specification import (
    FeatureArtifacts,
    FeaturePriority,
    FeatureSelectionCandidate,
    FeatureSpecification,
    FeatureStatus,
    FeatureType,
    PlanningTier,
)
from engineeringagent.ports import ValidationFailure


def test_filesystem_feature_specification_repository_lists_selection_candidates(
    tmp_path: Path,
) -> None:
    """The adapter should derive selection candidates from active feature packages."""

    _write_feature_package(
        tmp_path,
        {
            "directory_name": "FEAT-200-build-repository",
            "feature_id": "FEAT-200",
            "priority": "medium",
            "planning_tier": "planned",
            "artifacts": {"plan": "plan.md"},
        },
    )
    _write_plan(
        tmp_path,
        directory_name="FEAT-200-build-repository",
        body="\n".join(
            [
                "---",
                "plan_id: FEAT-200",
                "feature_id: FEAT-200",
                "status: in_progress",
                "source_spec: spec.yaml",
                "planning_tier: planned",
                "phases:",
                "  - id: P1",
                "    title: First phase",
                "    status: done",
                "  - id: P2",
                "    title: Second phase",
                "    status: pending",
                "---",
                "",
            ]
        ),
    )
    _write_feature_package(
        tmp_path,
        {
            "directory_name": "FEAT-100-current-priority",
            "feature_id": "FEAT-100",
            "priority": "high",
        },
    )

    candidates = FilesystemFeatureSpecificationRepository().list_selection_candidates(
        tmp_path
    )

    assert [candidate.feature_id for candidate in candidates] == [
        "FEAT-100",
        "FEAT-200",
    ]
    assert candidates[1].next_phase_id == "P2"
    assert candidates[1].phase_dependencies_satisfied is True


def test_filesystem_feature_specification_repository_loads_and_saves_feature(
    tmp_path: Path,
) -> None:
    """The adapter should round-trip a feature specification through YAML."""

    _write_feature_package(
        tmp_path,
        {
            "directory_name": "FEAT-300-save",
            "feature_id": "FEAT-300",
        },
    )
    repository = FilesystemFeatureSpecificationRepository()

    loaded = repository.load(tmp_path, "FEAT-300")
    updated = FeatureSpecification(
        feature_id=loaded.feature_id,
        title=loaded.title,
        feature_type=FeatureType.FEATURE,
        expected_commit_subject=loaded.expected_commit_subject,
        planning_tier=PlanningTier.DIRECT,
        status=FeatureStatus.IN_PROGRESS,
        priority=FeaturePriority.HIGH,
        objective=loaded.objective,
        context="Repository port is active.",
        acceptance=loaded.acceptance,
        artifacts=FeatureArtifacts(),
        updated_at="2026-03-11T00:00:00Z",
    )

    repository.save(tmp_path, "FEAT-300", updated)

    payload = yaml.safe_load(
        (
            tmp_path
            / "docs"
            / "specifications"
            / "features"
            / "FEAT-300-save"
            / "spec.yaml"
        ).read_text(encoding="utf-8")
    )
    assert payload["status"] == "in_progress"
    assert payload["context"] == "Repository port is active."


def test_filesystem_feature_specification_repository_archives_feature_package(
    tmp_path: Path,
) -> None:
    """The adapter should move one bundled feature package into the archive root."""

    _write_feature_package(
        tmp_path,
        {
            "directory_name": "FEAT-400-archive",
            "feature_id": "FEAT-400",
        },
    )
    repository = FilesystemFeatureSpecificationRepository()

    repository.archive(tmp_path, "FEAT-400")

    assert not (
        tmp_path / "docs" / "specifications" / "features" / "FEAT-400-archive"
    ).exists()
    assert (
        tmp_path
        / "docs"
        / "specifications"
        / "features_done"
        / "FEAT-400-archive"
        / "spec.yaml"
    ).is_file()


def test_filesystem_feature_specification_repository_rejects_invalid_feature_package(
    tmp_path: Path,
) -> None:
    """The adapter should fail deterministically on invalid bundled feature specs."""

    invalid_dir = (
        tmp_path / "docs" / "specifications" / "features" / "FEAT-500-invalid"
    )
    invalid_dir.mkdir(parents=True, exist_ok=True)
    (invalid_dir / "spec.yaml").write_text("id: FEAT-500\n", encoding="utf-8")

    with pytest.raises(
        ValidationFailure,
        match="feature specification error: invalid feature package:",
    ):
        FilesystemFeatureSpecificationRepository().list_selection_candidates(tmp_path)


def test_filesystem_feature_specification_repository_uses_configured_specifications_root(
    tmp_path: Path,
) -> None:
    """The adapter should load features from the configured specifications root."""

    (tmp_path / "engineeringagent.toml").write_text(
        '[paths]\nspecifications_root = "docs/specifications"\n',
        encoding="utf-8",
    )
    feature_dir = (
        tmp_path
        / "docs"
        / "specifications"
        / "features"
        / "FEAT-600-configured-root"
    )
    feature_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / "spec.yaml").write_text(
        yaml.safe_dump(
            {
                "id": "FEAT-600",
                "title": "Configured specifications root",
                "type": "feature",
                "expected_commit_subject": "feat: implement feat-600",
                "planning_tier": "direct",
                "status": "backlog",
                "priority": "high",
                "objective": "Load from docs/specifications.",
                "acceptance": ["Configured root works."],
                "artifacts": {},
                "updated_at": "2026-03-12T00:00:00Z",
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    loaded = FilesystemFeatureSpecificationRepository().load(tmp_path, "FEAT-600")

    assert loaded.feature_id == "FEAT-600"
    assert loaded.title == "Configured specifications root"


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
    features_dir = tmp_path / "docs" / "specifications" / "features"
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
        tmp_path
        / "docs"
        / "specifications"
        / "features"
        / "FEAT-999-broken"
        / "spec.yaml"
    )
    broken_spec.parent.mkdir(parents=True, exist_ok=True)
    broken_spec.write_text("[", encoding="utf-8")

    with pytest.raises(ValueError, match="failed to load feature YAML"):
        discover_active_feature_paths(tmp_path)


def test_load_selection_candidates_returns_typed_entries_for_explicit_paths(
    tmp_path: Path,
) -> None:
    """Load explicit spec paths into typed selection candidates."""
    feature_one_dir = (
        tmp_path / "docs" / "specifications" / "features" / "FEAT-010-first"
    )
    feature_two_dir = (
        tmp_path / "docs" / "specifications" / "features" / "FEAT-011-second"
    )
    feature_one_dir.mkdir(parents=True)
    feature_two_dir.mkdir(parents=True)
    feature_one = feature_one_dir / "spec.yaml"
    feature_two = feature_two_dir / "spec.yaml"
    feature_one.write_text(
        yaml.safe_dump(
            {
                "id": "FEAT-010",
                "title": "First",
                "type": "feature",
                "expected_commit_subject": "feat: implement feat-010",
                "planning_tier": "direct",
                "status": "backlog",
                "priority": "high",
                "objective": "First candidate.",
                "acceptance": ["First candidate works."],
                "artifacts": {},
                "updated_at": "2026-03-12T00:00:00Z",
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    feature_two.write_text(
        yaml.safe_dump(
            {
                "id": "FEAT-011",
                "title": "Second",
                "type": "feature",
                "expected_commit_subject": "feat: implement feat-011",
                "planning_tier": "direct",
                "status": "done",
                "priority": "medium",
                "objective": "Second candidate.",
                "acceptance": ["Second candidate works."],
                "artifacts": {},
                "updated_at": "2026-03-12T00:00:00Z",
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    candidates = load_selection_candidates([feature_one, feature_two])

    assert candidates == [
        (
            feature_one,
            FeatureSelectionCandidate(
                feature_id="FEAT-010",
                status=FeatureStatus.BACKLOG,
                priority=FeaturePriority.HIGH,
                planning_tier=PlanningTier.DIRECT,
                phase_dependencies_satisfied=True,
            ),
        ),
        (
            feature_two,
            FeatureSelectionCandidate(
                feature_id="FEAT-011",
                status=FeatureStatus.DONE,
                priority=FeaturePriority.MEDIUM,
                planning_tier=PlanningTier.DIRECT,
                phase_dependencies_satisfied=True,
                block_reason_code="feature_done",
            ),
        ),
    ]


def _write_feature_package(
    project_root: Path,
    payload: dict[str, object],
) -> None:
    directory_name = str(payload["directory_name"])
    feature_id = str(payload["feature_id"])
    feature_dir = (
        project_root / "docs" / "specifications" / "features" / directory_name
    )
    feature_dir.mkdir(parents=True, exist_ok=True)
    feature_payload = {
        "id": feature_id,
        "title": f"{feature_id} title",
        "type": "feature",
        "expected_commit_subject": f"feat: implement {feature_id.lower()}",
        "planning_tier": payload.get("planning_tier", "direct"),
        "status": "backlog",
        "priority": payload.get("priority", "high"),
        "objective": "Verify the repository seam.",
        "acceptance": ["Repository seam works."],
        "artifacts": payload.get("artifacts", {}),
        "updated_at": "2026-03-11T00:00:00Z",
    }
    (feature_dir / "spec.yaml").write_text(
        yaml.safe_dump(feature_payload, sort_keys=False),
        encoding="utf-8",
    )


def _write_plan(project_root: Path, *, directory_name: str, body: str) -> None:
    plan_path = (
        project_root
        / "docs"
        / "specifications"
        / "features"
        / directory_name
        / "plan.md"
    )
    plan_path.write_text(body, encoding="utf-8")
