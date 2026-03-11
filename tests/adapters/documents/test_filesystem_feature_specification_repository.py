from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from engineeringagent.adapters.documents import FilesystemFeatureSpecificationRepository
from engineeringagent.domain.specification import (
    FeatureArtifacts,
    FeaturePriority,
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
            / "spec"
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
        tmp_path / "docs" / "spec" / "features" / "FEAT-400-archive"
    ).exists()
    assert (
        tmp_path / "docs" / "spec" / "features_done" / "FEAT-400-archive" / "spec.yaml"
    ).is_file()


def test_filesystem_feature_specification_repository_rejects_invalid_feature_package(
    tmp_path: Path,
) -> None:
    """The adapter should fail deterministically on invalid bundled feature specs."""

    invalid_dir = tmp_path / "docs" / "spec" / "features" / "FEAT-500-invalid"
    invalid_dir.mkdir(parents=True, exist_ok=True)
    (invalid_dir / "spec.yaml").write_text("id: FEAT-500\n", encoding="utf-8")

    with pytest.raises(
        ValidationFailure,
        match="feature specification error: invalid feature package:",
    ):
        FilesystemFeatureSpecificationRepository().list_selection_candidates(tmp_path)


def _write_feature_package(
    project_root: Path,
    payload: dict[str, object],
) -> None:
    directory_name = str(payload["directory_name"])
    feature_id = str(payload["feature_id"])
    feature_dir = project_root / "docs" / "spec" / "features" / directory_name
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
    plan_path = project_root / "docs" / "spec" / "features" / directory_name / "plan.md"
    plan_path.write_text(body, encoding="utf-8")
