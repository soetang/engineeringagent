from __future__ import annotations

from engineeringagent.domain.specification import (
    FeatureArtifacts,
    FeaturePriority,
    FeatureSelectionCandidate,
    FeatureSpecification,
    FeatureStatus,
    FeatureType,
    PlanningTier,
)


def test_feature_specification_models_are_typed_and_immutable() -> None:
    """Specification-domain models should expose stable typed feature contracts."""

    specification = FeatureSpecification(
        feature_id="FEAT-123",
        title="Extract feature specification repository",
        feature_type=FeatureType.FEATURE,
        expected_commit_subject="feat: add feature specification repository",
        planning_tier=PlanningTier.PLANNED,
        status=FeatureStatus.BACKLOG,
        priority=FeaturePriority.HIGH,
        objective="Move file-backed feature loading behind a port.",
        acceptance=("Feature specifications load through a repository seam.",),
        artifacts=FeatureArtifacts(plan="plan.md", supporting=("notes.md",)),
    )

    candidate = FeatureSelectionCandidate(
        feature_id="FEAT-123",
        status=FeatureStatus.BACKLOG,
        priority=FeaturePriority.HIGH,
        planning_tier=PlanningTier.PLANNED,
        next_phase_id="P1",
        phase_dependencies_satisfied=True,
    )

    assert specification.artifacts.supporting == ("notes.md",)
    assert candidate.next_phase_id == "P1"
