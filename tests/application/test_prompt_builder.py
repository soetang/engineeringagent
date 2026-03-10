from __future__ import annotations

import ast
from pathlib import Path

import yaml

from engineeringagent.adapters.prompts import BundledPromptDefinitionRepository
from engineeringagent.application import (
    DefaultPromptBuilder,
    ImplementationPromptRequest,
    PromptArtifactPaths,
    build_implementation_prompt,
    build_implementation_prompt_request,
)
from tests.loop.feature_iteration_support import (
    base_feature,
    make_bundled_project_root,
    make_project_root,
)


def _prompt_builder() -> DefaultPromptBuilder:
    return DefaultPromptBuilder(BundledPromptDefinitionRepository())


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

    prompt = _prompt_builder().build_implementation_prompt(
        ImplementationPromptRequest(
            feature=feature,
            artifacts=PromptArtifactPaths(specification=feature_path),
            handoff_path=".engineeringagent/progress/features/FEAT-900/handoff.md",
            feedback=None,
            progress_kind="phase",
            current_progress="P1 - Build prompt seam",
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
    builder = _prompt_builder()

    direct = builder.build_implementation_prompt(
        build_implementation_prompt_request(
            feature=feature,
            feature_path=feature_path,
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

    prompt = _prompt_builder().build_implementation_prompt(
        ImplementationPromptRequest(
            feature=feature,
            artifacts=PromptArtifactPaths(specification=feature_path),
            handoff_path="custom/handoff-reference.md",
            feedback=None,
            progress_kind="subtask",
            current_progress="subtask-1 - Example",
        )
    )

    assert "read prior handoff context from custom/handoff-reference.md" in prompt


def test_default_prompt_builder_renders_explicit_plan_and_research_paths(
    tmp_path: Path,
) -> None:
    """The application prompt builder renders explicit artifact paths."""

    feature_path = (
        tmp_path / "docs" / "spec" / "features" / "FEAT-900-bundled-smoke-test" / "spec.yaml"
    )
    feature_path.parent.mkdir(parents=True, exist_ok=True)
    feature = {
        **base_feature(status="in_progress"),
        "planning_tier": "researched",
        "artifacts": {"plan": "plan.md", "research": "research.md"},
    }
    feature_path.write_text(yaml.safe_dump(feature, sort_keys=False), encoding="utf-8")

    prompt = _prompt_builder().build_implementation_prompt(
        ImplementationPromptRequest(
            feature=feature,
            artifacts=PromptArtifactPaths(
                specification=feature_path,
                plan=str(feature_path.parent / "plan.md"),
                research=str(feature_path.parent / "research.md"),
            ),
            handoff_path=".engineeringagent/progress/features/FEAT-900/handoff.md",
            feedback=None,
            progress_kind="phase",
            current_progress="FEAT-900 - Artifact paths",
        )
    )

    assert "Read and follow these files:" in prompt
    assert f"- specification: {feature_path}" in prompt
    assert f"- plan: {feature_path.parent / 'plan.md'}" in prompt
    assert f"- research: {feature_path.parent / 'research.md'}" in prompt


def test_application_prompt_builder_does_not_import_prompt_adapters() -> None:
    """Keep prompt-template adapter wiring out of the application layer."""

    module_path = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "engineeringagent"
        / "application"
        / "prompt_builder.py"
    )
    tree = ast.parse(module_path.read_text(encoding="utf-8"), filename=str(module_path))

    imported_modules = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported_from_modules = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }

    assert "engineeringagent.adapters.prompts" not in imported_modules
    assert "engineeringagent.adapters.prompts" not in imported_from_modules


def test_application_prompt_builder_keeps_runtime_resolution_outside_renderer() -> None:
    """Keep progress-state resolution out of the rendering service."""

    module_path = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "engineeringagent"
        / "application"
        / "prompt_builder.py"
    )
    tree = ast.parse(module_path.read_text(encoding="utf-8"), filename=str(module_path))

    imported_modules = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported_from_modules = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }

    forbidden = {
        "engineeringagent.loop_runtime.progress_units",
        "engineeringagent.progress.paths",
        "engineeringagent.specs",
    }
    assert imported_modules.isdisjoint(forbidden)
    assert imported_from_modules.isdisjoint(forbidden)
