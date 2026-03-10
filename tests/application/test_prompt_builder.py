from __future__ import annotations

from pathlib import Path

import yaml

from engineeringagent.application import (
    DefaultPromptBuilder,
    ImplementationPromptRequest,
    build_implementation_prompt,
)
from tests.loop.feature_iteration_support import (
    base_feature,
    make_bundled_project_root,
    make_project_root,
)


def test_default_prompt_builder_renders_bundled_phase_prompt(tmp_path: Path) -> None:
    """The application prompt builder preserves bundled-phase prompt context."""

    feature_data = {
        **base_feature(status="in_progress"),
        "planning_tier": "planned",
        "artifacts": {"plan": "plan.md"},
    }
    feature_data.pop("subtasks", None)
    _, feature_path, _plan_path = make_bundled_project_root(
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
                    "title": "Build prompt seam",
                    "status": "pending",
                }
            ],
        },
    )
    feature = yaml.safe_load(feature_path.read_text(encoding="utf-8"))

    prompt = DefaultPromptBuilder().build_implementation_prompt(
        ImplementationPromptRequest(
            feature=feature,
            feature_path=feature_path,
            handoff_path=".engineeringagent/progress/features/FEAT-900/handoff.md",
            feedback=None,
        )
    )

    assert "Current phase: P1 - Build prompt seam" in prompt
    assert "Treat this bundled feature package as canonical" in prompt


def test_compatibility_helper_delegates_to_prompt_builder(tmp_path: Path) -> None:
    """The compatibility helper routes through the application prompt builder."""

    feature_data = {
        **base_feature(status="in_progress"),
        "planning_tier": "planned",
        "artifacts": {"plan": "plan.md"},
    }
    feature_data.pop("subtasks", None)
    _, feature_path, _plan_path = make_bundled_project_root(
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
                    "title": "Build prompt seam",
                    "status": "pending",
                }
            ],
        },
    )
    feature = yaml.safe_load(feature_path.read_text(encoding="utf-8"))
    builder = DefaultPromptBuilder()

    direct = builder.build_implementation_prompt(
        ImplementationPromptRequest(
            feature=feature,
            feature_path=feature_path,
            handoff_path=".engineeringagent/progress/features/FEAT-900/handoff.md",
            feedback="",
        )
    )
    via_helper = build_implementation_prompt(
        feature=feature,
        feature_path=feature_path,
        feedback="",
        prompt_builder=builder,
    )

    assert via_helper == direct


def test_default_prompt_builder_uses_explicit_handoff_path_input(
    tmp_path: Path,
) -> None:
    """The application prompt request owns handoff path interpolation."""

    feature_data = base_feature()
    _, feature_path = make_project_root(tmp_path, feature_data=feature_data)
    feature = yaml.safe_load(feature_path.read_text(encoding="utf-8"))

    prompt = DefaultPromptBuilder().build_implementation_prompt(
        ImplementationPromptRequest(
            feature=feature,
            feature_path=feature_path,
            handoff_path="custom/handoff-reference.md",
            feedback=None,
        )
    )

    assert "read prior handoff context from custom/handoff-reference.md" in prompt
