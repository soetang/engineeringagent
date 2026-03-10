from __future__ import annotations

from pathlib import Path

import yaml

from engineeringagent.adapters.prompts import (
    BundledPromptDefinitionRepository,
)
from engineeringagent.application import (
    DefaultPromptBuilder,
    build_implementation_prompt,
)
from tests.loop.feature_iteration_support import (
    base_feature,
    make_bundled_project_root,
    make_project_root,
)


def _bundled_prompt_builder() -> DefaultPromptBuilder:
    return DefaultPromptBuilder(BundledPromptDefinitionRepository())


def test_ralph_prompt_includes_feature_file_path(tmp_path: Path) -> None:
    feature_data = base_feature()
    feature_data["context"] = "Loop iteration uses runtime phase orchestration."
    _, feature_path = make_project_root(tmp_path, feature_data=feature_data)
    feature = yaml.safe_load(feature_path.read_text(encoding="utf-8"))

    prompt = build_implementation_prompt(
        feature=feature,
        feature_path=feature_path,
        feedback=None,
        prompt_builder=_bundled_prompt_builder(),
    )

    expected_interpolated_values = (
        f"- specification: {feature_path}",
        "feature FEAT-900 (Feature iteration smoke test)",
        f"Objective: {feature_data['objective']}",
        f"Context: {feature_data['context']}",
    )
    for value in expected_interpolated_values:
        assert value in prompt
    assert "Read and follow these files:" in prompt
    assert "read prior handoff context" not in prompt

def test_ralph_prompt_contract_uses_schema_only_validate_command(
    tmp_path: Path,
) -> None:
    _, feature_path = make_project_root(tmp_path, feature_data=base_feature())
    feature = yaml.safe_load(feature_path.read_text(encoding="utf-8"))

    prompt = build_implementation_prompt(
        feature=feature,
        feature_path=feature_path,
        feedback=None,
        prompt_builder=_bundled_prompt_builder(),
    )

    assert "uv run engineeringagent validate --schema-only" in prompt


def test_bundled_ralph_prompt_uses_phase_wording(tmp_path: Path) -> None:
    feature_data = {
        **base_feature(status="in_progress"),
        "title": "Bundled feature prompt wording test",
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
                    "title": "Track bundled prompt wording",
                    "status": "pending",
                    "verification": ["uv run pytest -q tests/test_prompt_wording.py"],
                }
            ],
        },
    )
    feature = yaml.safe_load(feature_path.read_text(encoding="utf-8"))

    prompt = build_implementation_prompt(
        feature=feature,
        feature_path=feature_path,
        feedback=None,
        prompt_builder=_bundled_prompt_builder(),
    )

    assert "Identify the most important open phase first." in prompt
    assert "Then implement the most important phase, using TDD" in prompt
    assert "Run the chosen phase's listed verification command(s)" in prompt
    assert "open subtask" not in prompt
    assert "chosen subtask" not in prompt
    assert "Update progress in the bundled feature package" in prompt
    assert "`plan.md` by setting relevant phase status fields" in prompt
    assert "same feature YAML by setting relevant subtask/feature status fields" not in prompt


def test_bundled_ralph_prompt_surfaces_current_phase_reference(tmp_path: Path) -> None:
    feature_data = {
        **base_feature(status="in_progress"),
        "title": "Bundled feature current phase prompt test",
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
                    "title": "Track bundled prompt context",
                    "status": "pending",
                },
                {
                    "id": "P2",
                    "title": "Later phase",
                    "status": "pending",
                },
            ],
        },
    )
    feature = yaml.safe_load(feature_path.read_text(encoding="utf-8"))

    prompt = build_implementation_prompt(
        feature=feature,
        feature_path=feature_path,
        feedback=None,
        prompt_builder=_bundled_prompt_builder(),
    )

    assert "Current phase: P1 - Track bundled prompt context" in prompt
    assert "Current phase: P2 - Later phase" not in prompt


def test_bundled_ralph_prompt_keeps_phase_wording_with_invalid_plan_frontmatter(
    tmp_path: Path,
) -> None:
    feature_data = {
        **base_feature(status="in_progress"),
        "title": "Bundled feature invalid plan prompt wording test",
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
                    "title": "Track bundled prompt wording",
                    "status": "pending",
                }
            ],
        },
    )
    plan_path.write_text("---\ninvalid: [\n---\n# Plan\n", encoding="utf-8")
    feature = yaml.safe_load(feature_path.read_text(encoding="utf-8"))

    prompt = build_implementation_prompt(
        feature=feature,
        feature_path=feature_path,
        feedback=None,
        prompt_builder=_bundled_prompt_builder(),
    )

    assert "Identify the most important open phase first." in prompt
    assert "Update progress in the bundled feature package" in prompt
    assert "same feature YAML by setting relevant subtask/feature status fields" not in prompt


def test_flat_feature_prompt_avoids_legacy_wrapper_wording(tmp_path: Path) -> None:
    _, feature_path = make_project_root(tmp_path, feature_data=base_feature())
    feature = yaml.safe_load(feature_path.read_text(encoding="utf-8"))

    prompt = build_implementation_prompt(
        feature=feature,
        feature_path=feature_path,
        feedback=None,
        prompt_builder=_bundled_prompt_builder(),
    )

    assert "Identify the most important open implementation step first." in prompt
    assert "Then implement the most important implementation step, using TDD" in prompt
    assert "Run the chosen implementation step's listed verification command(s)" in prompt
    assert "Update progress in the bundled feature package" in prompt
    assert "open subtask" not in prompt
    assert "chosen subtask" not in prompt
    assert "same feature YAML by setting relevant subtask/feature status fields" not in prompt
    assert "plan.md by setting relevant phase status fields" not in prompt
    assert "compatibility wrapper" not in prompt
    assert "canonical bundled package references" not in prompt
    assert "Current implementation step: subtask-1" not in prompt


def test_bundled_ralph_prompt_treats_package_as_canonical_working_set(
    tmp_path: Path,
) -> None:
    feature_data = {
        **base_feature(status="in_progress"),
        "title": "Bundled feature canonical prompt test",
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
                    "title": "Track canonical prompt guidance",
                    "status": "backlog",
                }
            ],
        },
    )
    feature = yaml.safe_load(feature_path.read_text(encoding="utf-8"))

    prompt = build_implementation_prompt(
        feature=feature,
        feature_path=feature_path,
        feedback=None,
        prompt_builder=_bundled_prompt_builder(),
    )

    assert (
        "Treat this bundled feature package as canonical: keep lifecycle status in "
        "`spec.yaml` and sequencing in `plan.md` when present." in prompt
    )
    assert "compatibility wrapper as a temporary shim" not in prompt


def test_direct_bundled_ralph_prompt_avoids_legacy_subtask_wording(
    tmp_path: Path,
) -> None:
    feature_path = (
        tmp_path / "docs" / "spec" / "features" / "FEAT-901-direct-bundled" / "spec.yaml"
    )
    feature_path.parent.mkdir(parents=True, exist_ok=True)
    feature = {
        "id": "FEAT-901",
        "title": "Direct bundled prompt wording test",
        "type": "spec",
        "expected_commit_subject": "spec: direct bundled prompt wording",
        "planning_tier": "direct",
        "status": "in_progress",
        "priority": "high",
        "objective": "Keep direct bundled prompts off legacy subtask wording.",
        "acceptance": [
            "Bundled direct features should use feature-level implementation wording."
        ],
        "artifacts": {},
    }
    feature_path.write_text(yaml.safe_dump(feature, sort_keys=False), encoding="utf-8")

    prompt = build_implementation_prompt(
        feature=feature,
        feature_path=feature_path,
        feedback=None,
        prompt_builder=_bundled_prompt_builder(),
    )

    assert "Identify the most important open implementation step first." in prompt
    assert "Then implement the most important implementation step, using TDD" in prompt
    assert "Run the chosen implementation step's listed verification command(s)" in prompt
    assert "open subtask" not in prompt
    assert "chosen subtask" not in prompt
    assert "Update progress in the bundled feature package" in prompt
    assert "`spec.yaml` feature status fields and `updated_at`." in prompt
    assert "`plan.md` by setting relevant phase status fields" not in prompt


def test_bundled_ralph_prompt_includes_plan_and_research_paths(tmp_path: Path) -> None:
    feature_root = (
        tmp_path / "docs" / "spec" / "features" / "FEAT-902-bundled-researched"
    )
    feature_path = feature_root / "spec.yaml"
    plan_path = feature_root / "plan.md"
    research_path = feature_root / "research.md"
    feature_root.mkdir(parents=True, exist_ok=True)
    feature = {
        **base_feature(status="in_progress"),
        "id": "FEAT-902",
        "title": "Researched bundled prompt paths test",
        "planning_tier": "researched",
        "artifacts": {"plan": "plan.md", "research": "research.md"},
    }
    feature_path.write_text(yaml.safe_dump(feature, sort_keys=False), encoding="utf-8")
    plan_path.write_text(
        "---\nfeature_id: FEAT-902\nplanning_tier: researched\nsource_spec: spec.yaml\nphases: []\n---\n",
        encoding="utf-8",
    )
    research_path.write_text("# Research\n", encoding="utf-8")

    prompt = build_implementation_prompt(
        feature=feature,
        feature_path=feature_path,
        feedback=None,
        prompt_builder=_bundled_prompt_builder(),
    )

    assert f"- specification: {feature_path}" in prompt
    assert f"- plan: {plan_path}" in prompt
    assert f"- research: {research_path}" in prompt
