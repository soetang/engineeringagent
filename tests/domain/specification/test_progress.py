from __future__ import annotations

from pathlib import Path

import yaml

from engineeringagent.domain.specification import (
    current_progress_unit,
    done_transition_verification_commands,
    progress_status_snapshot,
)
from tests.helpers.feature_iteration_support import (
    base_feature,
    make_bundled_project_root,
)


def test_valid_bundled_plan_progress_helpers_normalize_phase_metadata(
    tmp_path: Path,
) -> None:
    """Normalize plan-phase ids, titles, statuses, and verification commands."""

    verification_command = "uv run pytest -q tests/test_normalized_phase_verification.py"
    feature_data = {
        **base_feature(status="in_progress"),
        "title": "Bundled feature normalized plan metadata smoke test",
        "planning_tier": "planned",
        "artifacts": {"plan": "plan.md"},
    }
    feature_data.pop("subtasks", None)
    _, feature_path, plan_path = make_bundled_project_root(
        tmp_path,
        feature_data=feature_data,
        plan_frontmatter={
            "plan_id": "FEAT-900",
            "feature_id": "FEAT-900",
            "status": "in_progress",
            "source_spec": "spec.yaml",
            "planning_tier": "planned",
            "phases": [
                {
                    "id": " P1 ",
                    "title": " Normalize validated bundled phase metadata ",
                    "status": " in_progress ",
                    "verification": [verification_command],
                }
            ],
        },
    )

    progress_unit = current_progress_unit(feature_path, feature_data)
    assert progress_unit is not None
    assert progress_unit.kind == "phase"
    assert progress_unit.id == "P1"
    assert progress_unit.title == "Normalize validated bundled phase metadata"
    assert progress_unit.status == "in_progress"
    assert progress_status_snapshot(feature_path, feature_data) == {"P1": "in_progress"}

    plan_document = plan_path.read_text(encoding="utf-8")
    plan_path.write_text(
        plan_document.replace("status: ' in_progress '", "status: ' done '"),
        encoding="utf-8",
    )
    post_feature = yaml.safe_load(feature_path.read_text(encoding="utf-8"))

    assert done_transition_verification_commands(
        {"P1": "in_progress"},
        feature_path,
        post_feature,
    ) == [verification_command]


def test_direct_bundled_feature_progress_helpers_use_feature_surface(
    tmp_path: Path,
) -> None:
    """Treat direct bundled specs as feature-shaped progress units."""

    feature_path = (
        tmp_path / "docs" / "spec" / "features" / "FEAT-901-direct-bundled" / "spec.yaml"
    )
    feature_path.parent.mkdir(parents=True, exist_ok=True)
    feature_data = {
        "id": "FEAT-901",
        "title": "Direct bundled helper coverage",
        "type": "spec",
        "expected_commit_subject": "spec: direct bundled helper coverage",
        "planning_tier": "direct",
        "status": "in_progress",
        "priority": "high",
        "objective": "Keep direct bundled progress helpers feature-oriented.",
        "acceptance": ["Direct bundled helpers resolve feature-level progress units."],
        "artifacts": {},
    }
    feature_path.write_text(yaml.safe_dump(feature_data, sort_keys=False), encoding="utf-8")

    progress_unit = current_progress_unit(feature_path, feature_data)
    assert progress_unit is not None
    assert progress_unit.kind == "feature"
    assert progress_unit.id == "FEAT-901"
    assert progress_unit.title == "Direct bundled helper coverage"
    assert progress_unit.status == "in_progress"
    assert progress_status_snapshot(feature_path, feature_data) == {
        "FEAT-901": "in_progress"
    }

    done_feature = {**feature_data, "status": "done"}
    assert done_transition_verification_commands(
        progress_status_snapshot(feature_path, feature_data),
        feature_path,
        done_feature,
    ) == []


def test_invalid_bundled_plan_does_not_fall_back_to_feature_progress_unit(
    tmp_path: Path,
) -> None:
    """Keep invalid planned bundles off the feature fallback surface."""

    feature_data = {
        **base_feature(status="in_progress"),
        "title": "Bundled feature invalid plan progress helper coverage",
        "planning_tier": "planned",
        "artifacts": {"plan": "plan.md"},
    }
    feature_data.pop("subtasks", None)
    _, feature_path, plan_path = make_bundled_project_root(
        tmp_path,
        feature_data=feature_data,
        plan_frontmatter={
            "plan_id": "FEAT-900",
            "feature_id": "FEAT-900",
            "status": "in_progress",
            "source_spec": "spec.yaml",
            "planning_tier": "planned",
            "phases": [
                {
                    "id": "P1",
                    "title": "Keep bundled invalid plans on the phase surface",
                    "status": "in_progress",
                }
            ],
        },
    )
    plan_path.write_text("---\ninvalid: [\n---\n# Plan\n", encoding="utf-8")

    assert current_progress_unit(feature_path, feature_data) is None
    assert progress_status_snapshot(feature_path, feature_data) == {}
