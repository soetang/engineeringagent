from __future__ import annotations

from pathlib import Path

import engineeringagent.domain.specification.selection as selection
from engineeringagent.domain.specification import (
    FeaturePriority,
    FeatureSelectionCandidate,
    FeatureStatus,
    PlanningTier,
)


def _candidate(
    feature_id: str,
    *,
    status: FeatureStatus,
    priority: FeaturePriority,
    planning_tier: PlanningTier = PlanningTier.DIRECT,
) -> FeatureSelectionCandidate:
    return FeatureSelectionCandidate(
        feature_id=feature_id,
        status=status,
        priority=priority,
        planning_tier=planning_tier,
        phase_dependencies_satisfied=True,
    )


def _pending_features() -> list[tuple[Path, FeatureSelectionCandidate]]:
    return [
        (
            Path("docs/specifications/features/FEAT-200-third-feature/spec.yaml"),
            _candidate(
                "FEAT-200",
                status=FeatureStatus.BACKLOG,
                priority=FeaturePriority.LOW,
            ),
        ),
        (
            Path("docs/specifications/features/FEAT-100-first-feature/spec.yaml"),
            _candidate(
                "FEAT-100",
                status=FeatureStatus.IN_PROGRESS,
                priority=FeaturePriority.HIGH,
            ),
        ),
        (
            Path("docs/specifications/features/FEAT-150-second-feature/spec.yaml"),
            _candidate(
                "FEAT-150",
                status=FeatureStatus.BACKLOG,
                priority=FeaturePriority.MEDIUM,
            ),
        ),
    ]


def _bundled_pending_features() -> list[tuple[Path, FeatureSelectionCandidate]]:
    return [
        (
            Path("docs/specifications/features/FEAT-320-first-bundle/spec.yaml"),
            _candidate(
                "FEAT-320",
                status=FeatureStatus.BACKLOG,
                priority=FeaturePriority.MEDIUM,
            ),
        ),
        (
            Path("docs/specifications/features/FEAT-321-second-bundle/spec.yaml"),
            _candidate(
                "FEAT-321",
                status=FeatureStatus.IN_PROGRESS,
                priority=FeaturePriority.HIGH,
            ),
        ),
    ]


def test_deterministic_feature_choice_prefers_status_then_priority_then_id() -> None:
    """Prefer active work, then higher priority, then stable ids."""
    chosen_path, chosen_feature = selection.deterministic_feature_choice(
        _pending_features()
    )

    assert chosen_path == Path("docs/specifications/features/FEAT-100-first-feature/spec.yaml")
    assert chosen_feature.feature_id == "FEAT-100"


def test_parse_selector_output_matches_full_path_fragment() -> None:
    """Accept a returned full path when the selector includes it verbatim."""
    pending = _pending_features()

    selected = selection.parse_selector_output(
        "pick docs/specifications/features/FEAT-150-second-feature/spec.yaml", pending
    )

    assert selected == Path("docs/specifications/features/FEAT-150-second-feature/spec.yaml")


def test_parse_selector_output_uses_unique_directory_name_and_id_tokens() -> None:
    """Match unique bundle directory names without accepting unknown ids."""
    pending = _pending_features()

    selected_by_name = selection.parse_selector_output(
        "`FEAT-150-second-feature`", pending
    )
    selected_by_id = selection.parse_selector_output("choose FEAT-300", pending)

    assert selected_by_name == Path("docs/specifications/features/FEAT-150-second-feature/spec.yaml")
    assert selected_by_id is None


def test_parse_selector_output_uses_unique_feature_id_tokens() -> None:
    """Match a unique feature id token to its selected bundle path."""
    pending = _pending_features()

    selected_by_id = selection.parse_selector_output("choose FEAT-150", pending)

    assert selected_by_id == Path("docs/specifications/features/FEAT-150-second-feature/spec.yaml")


def test_parse_selector_output_uses_unique_bundled_package_directory_tokens() -> None:
    """Resolve bundled package directory names when they are unique."""
    pending = _bundled_pending_features()

    selected = selection.parse_selector_output("pick FEAT-321-second-bundle", pending)

    assert selected == Path("docs/specifications/features/FEAT-321-second-bundle/spec.yaml")


def test_parse_selector_output_normalizes_multiline_punctuated_tokens() -> None:
    """Strip punctuation and newlines before checking selector tokens."""
    pending = _bundled_pending_features()

    selected = selection.parse_selector_output(
        "pick\n`FEAT-320-first-bundle`, please",
        pending,
    )

    assert selected == Path("docs/specifications/features/FEAT-320-first-bundle/spec.yaml")


def test_parse_selector_output_returns_none_for_empty_or_ambiguous_tokens() -> None:
    """Reject empty, ambiguous, or unmatched selector output."""
    pending = [
        (
            Path("docs/specifications/features/dup-a/spec.yaml"),
            _candidate(
                "FEAT-401",
                status=FeatureStatus.BACKLOG,
                priority=FeaturePriority.MEDIUM,
            ),
        ),
        (
            Path("tmp/dup-b/spec.yaml"),
            _candidate(
                "FEAT-402",
                status=FeatureStatus.BACKLOG,
                priority=FeaturePriority.MEDIUM,
            ),
        ),
    ]

    assert selection.parse_selector_output("", pending) is None
    assert selection.parse_selector_output("spec.yaml", pending) is None
    assert selection.parse_selector_output("not-a-feature", pending) is None
