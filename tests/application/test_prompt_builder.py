from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import pytest
import yaml

from engineeringagent.adapters.prompts import FilesystemPromptDefinitionRepository
import engineeringagent.application.prompt_builder as prompt_builder_module
from engineeringagent.application import (
    DefaultPromptBuilder,
    ImplementationPromptFeature,
    ImplementationPromptRequest,
    PromptArtifactPaths,
    build_implementation_prompt,
    build_implementation_prompt_request,
    build_selector_prompt,
)
from tests.loop.feature_iteration_support import (
    base_feature,
    make_bundled_project_root,
    make_project_root,
)


def _prompt_builder() -> DefaultPromptBuilder:
    prompts_root = Path(__file__).resolve().parents[2] / "harness" / "prompts"
    return DefaultPromptBuilder(FilesystemPromptDefinitionRepository(prompts_root))


def _write_prompt_module(prompts_root: Path, prompt_id: str, body: str) -> None:
    (prompts_root / f"{prompt_id}.py").write_text(body, encoding="utf-8")


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
            feature=ImplementationPromptFeature(
                feature_id=feature["id"],
                title=feature["title"],
                objective=feature["objective"],
                context=feature.get("context", ""),
            ),
            artifacts=PromptArtifactPaths(specification=feature_path),
            handoff_path=".engineeringagent/progress/features/FEAT-900/handoff.md",
            feedback=None,
            progress_kind="phase",
            current_progress="P1 - Build prompt seam",
        )
    )

    assert "Current phase: P1 - Build prompt seam" in prompt
    assert "Treat this bundled feature package as canonical" in prompt


def test_application_selector_prompt_renders_feature_summaries(tmp_path: Path) -> None:
    """Selector prompt rendering belongs to the application prompt surface."""

    feature_path = tmp_path / "docs" / "spec" / "features" / "FEAT-900" / "spec.yaml"
    feature_path.parent.mkdir(parents=True, exist_ok=True)
    prompt = build_selector_prompt(
        [(feature_path, {"id": "FEAT-900", "status": "backlog", "priority": "high"})],
        prompt_definitions=FilesystemPromptDefinitionRepository(
            Path(__file__).resolve().parents[2] / "harness" / "prompts"
        ),
    )

    assert "id=FEAT-900" in prompt
    assert f"path={feature_path}" in prompt


def test_application_selector_prompt_prefers_repo_local_template(
    tmp_path: Path,
) -> None:
    """Selector prompt rendering should use repository-local overrides."""

    prompts_root = tmp_path / "harness" / "prompts"
    prompts_root.mkdir(parents=True)
    _write_prompt_module(
        prompts_root,
        "loop_selector",
        "from pydantic import BaseModel\n"
        "from engineeringagent.ports import PromptDefinition, PromptInterpolation\n"
        "class SelectorInput(BaseModel):\n"
        "    choices: str\n"
        "PROMPT_DEFINITION = PromptDefinition(\n"
        "    prompt_id='loop_selector',\n"
        "    purpose='selector',\n"
        "    target='operator',\n"
        "    output_mode='text',\n"
        "    token_budget_hint=100,\n"
        "    input_model=SelectorInput,\n"
        "    body_template='repo selector\\n$choices\\n',\n"
        "    interpolations=(PromptInterpolation(\n"
        "        name='choices', source='test', required=True, rationale='test'),),\n"
        ")\n",
    )

    prompt = build_selector_prompt(
        [(tmp_path / "feature.yaml", {"id": "FEAT-100", "status": "backlog"})],
        prompt_definitions=FilesystemPromptDefinitionRepository(prompts_root),
    )

    assert prompt.startswith("repo selector\n")


def test_loop_runtime_prompt_helper_delegates_to_prompt_builder(tmp_path: Path) -> None:
    """Loop runtime prompt assembly delegates rendering to the application builder."""

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

def test_build_implementation_prompt_request_does_not_invent_handoff_path(
    tmp_path: Path,
) -> None:
    """Application prompt requests keep handoff optional until runtime provides one."""

    feature_data = base_feature()
    _, feature_path = make_project_root(tmp_path, feature_data=feature_data)
    feature = yaml.safe_load(feature_path.read_text(encoding="utf-8"))

    request = build_implementation_prompt_request(
        feature=feature,
        feature_path=feature_path,
        feedback=None,
    )

    assert request.handoff_path is None


def test_default_prompt_builder_uses_explicit_handoff_path_input(
    tmp_path: Path,
) -> None:
    """The application prompt request owns handoff path interpolation."""

    feature_data = base_feature()
    _, feature_path = make_project_root(tmp_path, feature_data=feature_data)
    feature = yaml.safe_load(feature_path.read_text(encoding="utf-8"))

    prompt = _prompt_builder().build_implementation_prompt(
        ImplementationPromptRequest(
            feature=ImplementationPromptFeature(
                feature_id=feature["id"],
                title=feature["title"],
                objective=feature["objective"],
                context=feature.get("context", ""),
            ),
            artifacts=PromptArtifactPaths(specification=feature_path),
            handoff_path="custom/handoff-reference.md",
            feedback=None,
            progress_kind="feature",
            current_progress="FEAT-900 - Example",
        )
    )

    assert "read prior handoff context from custom/handoff-reference.md" in prompt


def test_default_prompt_builder_omits_handoff_guidance_without_path(
    tmp_path: Path,
) -> None:
    """Bundled implementation prompts mention handoff only when one exists."""

    feature_data = base_feature()
    _, feature_path = make_project_root(tmp_path, feature_data=feature_data)
    feature = yaml.safe_load(feature_path.read_text(encoding="utf-8"))

    prompt = _prompt_builder().build_implementation_prompt(
        ImplementationPromptRequest(
            feature=ImplementationPromptFeature(
                feature_id=feature["id"],
                title=feature["title"],
                objective=feature["objective"],
                context=feature.get("context", ""),
            ),
            artifacts=PromptArtifactPaths(specification=feature_path),
            handoff_path=None,
            feedback=None,
            progress_kind="feature",
            current_progress="FEAT-900 - Example",
        )
    )

    assert "read prior handoff context" not in prompt
    assert "tail -n 40" not in prompt


def test_prompt_builder_private_helpers_cover_invalid_and_blank_inputs(
    tmp_path: Path,
) -> None:
    """Prompt requests stay deterministic for blank bundled artifact references."""

    feature_data = base_feature()
    feature_data["artifacts"] = {"plan": "   ", "research": ""}
    _, feature_path = make_project_root(tmp_path, feature_data=feature_data)
    feature = yaml.safe_load(feature_path.read_text(encoding="utf-8"))

    assert prompt_builder_module._normalize_plain_prompt_feedback(None) is None
    request = build_implementation_prompt_request(
        feature=feature,
        feature_path=feature_path,
        feedback=None,
    )

    assert request.artifacts.plan is None
    assert request.artifacts.research is None
    assert request.progress_kind == "feature"


def test_prompt_builder_private_helpers_cover_progress_fallback_paths(
    tmp_path: Path,
) -> None:
    """Prompt requests use canonical progress fallback behavior from spec helpers."""

    feature_path = (
        tmp_path / "docs" / "spec" / "features" / "FEAT-900-bundled-smoke-test" / "spec.yaml"
    )
    feature_path.parent.mkdir(parents=True, exist_ok=True)
    feature = {
        **base_feature(status="in_progress"),
        "planning_tier": "planned",
        "artifacts": {"plan": "plan.md"},
    }
    feature_path.write_text(yaml.safe_dump(feature, sort_keys=False), encoding="utf-8")
    mixed_phases = tmp_path / "mixed-phases.md"
    mixed_phases.write_text(
        "---\nphases:\n  - invalid\n  - id: P1\n    title: Phase one\n    status: pending\n---\n# Plan\n",
        encoding="utf-8",
    )
    (feature_path.parent / "plan.md").write_text(
        mixed_phases.read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    request = build_implementation_prompt_request(
        feature=feature,
        feature_path=feature_path,
        feedback=None,
    )

    assert request.progress_kind == "phase"
    assert request.current_progress == "P1 - Phase one"
    assert request.artifacts.plan == str(feature_path.parent / "plan.md")
    assert (
        prompt_builder_module._current_progress_reference(
            progress_unit=type("Unit", (), {"id": "P1", "title": ""})(),
            feature={},
            progress_kind="phase",
        )
        == "P1"
    )
    assert (
        prompt_builder_module._current_progress_reference(
            progress_unit=None,
            feature={"title": "Missing id"},
            progress_kind="feature",
        )
        is None
    )
    assert (
        prompt_builder_module._current_progress_reference(
            progress_unit=None,
            feature={"id": "FEAT-1", "title": "Title"},
            progress_kind="feature",
        )
        == "FEAT-1 - Title"
    )
    assert (
        prompt_builder_module._progress_update_instruction("unexpected")
        == "Update progress in the bundled feature package by setting `spec.yaml` feature status fields and `updated_at`."
    )
    assert prompt_builder_module._progress_unit_prompt_label("unexpected") == (
        "implementation step"
    )


def test_default_prompt_builder_prefers_repo_local_templates(
    tmp_path: Path,
) -> None:
    """Implementation prompt rendering should use repository-local overrides."""

    prompts_root = tmp_path / "harness" / "prompts"
    prompts_root.mkdir(parents=True)
    _write_prompt_module(
        prompts_root,
        "loop_implementation",
        "from pydantic import BaseModel\n"
        "from engineeringagent.ports import PromptDefinition, PromptInterpolation\n"
        "class ImplementationInput(BaseModel):\n"
        "    feature_id: str\n"
        "    artifact_paths: str\n"
        "    handoff_path: str\n"
        "    feature_title: str\n"
        "    objective: str\n"
        "    context: str\n"
        "    progress_unit: str\n"
        "    current_progress_reference: str\n"
        "    progress_context_instruction: str\n"
        "    progress_update_instruction: str\n"
        "class ImplementationOutput(BaseModel):\n"
        "    summary: str\n"
        "PROMPT_DEFINITION = PromptDefinition(\n"
        "    prompt_id='loop_implementation',\n"
        "    purpose='implementation',\n"
        "    target='implementation',\n"
        "    output_mode='structured',\n"
        "    token_budget_hint=100,\n"
        "    input_model=ImplementationInput,\n"
        "    output_model=ImplementationOutput,\n"
        "    body_template='repo implementation\\n$feature_id\\n$artifact_paths\\n',\n"
        "    interpolations=(\n"
        "        PromptInterpolation(name='feature_id', source='test', required=True, rationale='test'),\n"
        "        PromptInterpolation(name='artifact_paths', source='test', required=True, rationale='test'),\n"
        "        PromptInterpolation(name='handoff_path', source='test', required=True, rationale='test'),\n"
        "        PromptInterpolation(name='feature_title', source='test', required=True, rationale='test'),\n"
        "        PromptInterpolation(name='objective', source='test', required=True, rationale='test'),\n"
        "        PromptInterpolation(name='context', source='test', required=True, rationale='test'),\n"
        "        PromptInterpolation(name='progress_unit', source='test', required=True, rationale='test'),\n"
        "        PromptInterpolation(name='current_progress_reference', source='test', required=True, rationale='test'),\n"
        "        PromptInterpolation(name='progress_context_instruction', source='test', required=True, rationale='test'),\n"
        "        PromptInterpolation(name='progress_update_instruction', source='test', required=True, rationale='test'),\n"
        "    ),\n"
        ")\n",
    )
    _write_prompt_module(
        prompts_root,
        "loop_feedback",
        "from pydantic import BaseModel\n"
        "from engineeringagent.ports import PromptDefinition, PromptInterpolation\n"
        "class FeedbackInput(BaseModel):\n"
        "    feedback: str\n"
        "PROMPT_DEFINITION = PromptDefinition(\n"
        "    prompt_id='loop_feedback',\n"
        "    purpose='feedback',\n"
        "    target='implementation',\n"
        "    output_mode='text',\n"
        "    token_budget_hint=100,\n"
        "    input_model=FeedbackInput,\n"
        "    body_template='\\n\\nRepo feedback:\\n$feedback\\n',\n"
        "    interpolations=(PromptInterpolation(\n"
        "        name='feedback', source='test', required=True, rationale='test'),),\n"
        ")\n",
    )
    feature_path = tmp_path / "docs" / "features" / "spec.yaml"
    feature_path.parent.mkdir(parents=True)
    feature_path.write_text("id: FEAT-101\n", encoding="utf-8")

    prompt = DefaultPromptBuilder(
        FilesystemPromptDefinitionRepository(prompts_root)
    ).build_implementation_prompt(
        ImplementationPromptRequest(
            feature=ImplementationPromptFeature(
                feature_id="FEAT-101",
                title="",
                objective="",
                context="",
            ),
            artifacts=PromptArtifactPaths(specification=feature_path),
            handoff_path=".engineeringagent/progress/features/FEAT-101/handoff.md",
            feedback="retry",
            progress_kind="feature",
            current_progress="FEAT-101 - Repo local",
        )
    )

    assert prompt.startswith("repo implementation\nFEAT-101\n")
    assert "Repo feedback:\nretry" in prompt


def test_default_prompt_builder_normalizes_legacy_subtask_progress_to_feature_wording(
    tmp_path: Path,
) -> None:
    """The core application contract only accepts bundled progress kinds."""

    feature_data = base_feature()
    _, feature_path = make_project_root(tmp_path, feature_data=feature_data)
    feature = yaml.safe_load(feature_path.read_text(encoding="utf-8"))

    with pytest.raises(ValueError, match="progress_kind"):
        ImplementationPromptRequest(
            feature=ImplementationPromptFeature(
                feature_id=feature["id"],
                title=feature["title"],
                objective=feature["objective"],
                context=feature.get("context", ""),
            ),
            artifacts=PromptArtifactPaths(specification=feature_path),
            handoff_path="custom/handoff-reference.md",
            feedback=None,
            progress_kind=cast(Any, "subtask"),
            current_progress="subtask-1 - Example",
        )


def test_loop_runtime_prompt_request_ignores_legacy_subtasks_for_application(
    tmp_path: Path,
) -> None:
    """Loop prompt requests stay on the bundled feature surface."""

    feature_data = base_feature(status="in_progress")
    feature_data["subtasks"] = [
        {
            "id": "subtask-1",
            "title": "Example",
            "status": "in_progress",
        }
    ]
    _, feature_path = make_project_root(tmp_path, feature_data=feature_data)
    feature = yaml.safe_load(feature_path.read_text(encoding="utf-8"))

    request = build_implementation_prompt_request(
        feature=feature,
        feature_path=feature_path,
        feedback=None,
    )

    assert request.progress_kind == "feature"
    assert request.current_progress == "FEAT-900 - Feature iteration smoke test"


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
            feature=ImplementationPromptFeature(
                feature_id=feature["id"],
                title=feature["title"],
                objective=feature["objective"],
                context=feature.get("context", ""),
            ),
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
