from __future__ import annotations

from pathlib import Path

import yaml

from engineeringagent.adapters.prompts import FilesystemPromptDefinitionRepository
import engineeringagent.application.prompt_builder as prompt_builder_module
from engineeringagent.application import (
    ImplementationPromptRequest,
    PromptBuilder,
)
from engineeringagent.domain.specification import (
    FeatureArtifacts,
    FeaturePriority,
    FeatureSpecification,
    FeatureStatus,
    FeatureType,
    PlanningTier,
)
from tests.loop.feature_iteration_support import (
    base_feature,
    make_project_root,
)


def _prompt_builder(prompts_root: Path | None = None) -> PromptBuilder:
    resolved_prompts_root = prompts_root or (
        Path(__file__).resolve().parents[2] / "harness" / "prompts"
    )
    return PromptBuilder(FilesystemPromptDefinitionRepository(resolved_prompts_root))


def _write_prompt_module(prompts_root: Path, prompt_id: str, body: str) -> None:
    (prompts_root / f"{prompt_id}.py").write_text(body, encoding="utf-8")


def _feature_specification(**overrides: object) -> FeatureSpecification:
    payload = {
        "feature_id": "FEAT-900",
        "title": "Feature iteration smoke test",
        "feature_type": FeatureType.FEATURE,
        "expected_commit_subject": "feat: complete feat-900 feature iteration smoke test",
        "planning_tier": PlanningTier.DIRECT,
        "status": FeatureStatus.BACKLOG,
        "priority": FeaturePriority.HIGH,
        "objective": "Verify feature iteration does not require subtask selection.",
        "acceptance": ("Feature iteration runs as a feature-level unit.",),
        "artifacts": FeatureArtifacts(),
    }
    payload.update(overrides)
    return FeatureSpecification(**payload)


def test_application_selector_prompt_renders_feature_summaries(tmp_path: Path) -> None:
    """Selector prompt rendering belongs to the application prompt surface."""

    feature_path = tmp_path / "docs" / "spec" / "features" / "FEAT-900" / "spec.yaml"
    feature_path.parent.mkdir(parents=True, exist_ok=True)
    prompt = _prompt_builder().build_selector_prompt(
        [(feature_path, {"id": "FEAT-900", "status": "backlog", "priority": "high"})]
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

    prompt = _prompt_builder(prompts_root).build_selector_prompt(
        [(tmp_path / "feature.yaml", {"id": "FEAT-100", "status": "backlog"})]
    )

    assert prompt.startswith("repo selector\n")


def test_build_implementation_prompt_request_does_not_invent_handoff_path(
    tmp_path: Path,
) -> None:
    """Application prompt requests keep handoff optional until runtime provides one."""

    _, feature_path = make_project_root(tmp_path, feature_data=base_feature())

    request = _prompt_builder().build_implementation_prompt_request(
        feature=_feature_specification(),
        specification_path=feature_path,
        feedback=None,
    )

    assert request.handoff_path is None
    assert request.retry_feedback is None


def test_default_prompt_builder_renders_artifact_path_prompt(
    tmp_path: Path,
) -> None:
    """The default implementation prompt should render canonical artifact paths."""

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
            feature_id=feature["id"],
            specification_path=feature_path,
            plan_path=str(feature_path.parent / "plan.md"),
            research_path=str(feature_path.parent / "research.md"),
            handoff_path=".engineeringagent/progress/FEAT-900/handoff.md",
            retry_feedback="fix the failing tests first",
        )
    )

    assert f"Feature: {feature['id']}" in prompt
    assert f"- specification: {feature_path}" in prompt
    assert f"- plan: {feature_path.parent / 'plan.md'}" in prompt
    assert f"- research: {feature_path.parent / 'research.md'}" in prompt
    assert "- handoff: .engineeringagent/progress/FEAT-900/handoff.md" in prompt
    assert "Retry feedback:" in prompt
    assert "fix the failing tests first" in prompt


def test_default_prompt_builder_omits_optional_lines_without_values(
    tmp_path: Path,
) -> None:
    """The default implementation prompt should omit empty optional fields."""

    feature_data = base_feature()
    _, feature_path = make_project_root(tmp_path, feature_data=feature_data)

    prompt = _prompt_builder().build_implementation_prompt(
        ImplementationPromptRequest(
            feature_id="FEAT-900",
            specification_path=feature_path,
        )
    )

    assert f"- specification: {feature_path}" in prompt
    assert "- plan:" not in prompt
    assert "- research:" not in prompt
    assert "- handoff:" not in prompt
    assert "Retry feedback:" not in prompt


def test_prompt_builder_private_helpers_cover_invalid_and_blank_inputs(
    tmp_path: Path,
) -> None:
    """Prompt requests stay deterministic for blank bundled artifact references."""

    _, feature_path = make_project_root(tmp_path, feature_data=base_feature())

    assert prompt_builder_module._normalize_plain_prompt_feedback(None) is None
    request = _prompt_builder().build_implementation_prompt_request(
        feature=_feature_specification(
            artifacts=FeatureArtifacts(plan="   ", research=""),
        ),
        specification_path=feature_path,
        feedback="  retry here  ",
    )

    assert request.plan_path is None
    assert request.research_path is None
    assert request.retry_feedback == "retry here"


def test_default_prompt_builder_prefers_repo_local_templates(
    tmp_path: Path,
) -> None:
    """Implementation prompt rendering should use repository-local overrides."""

    prompts_root = tmp_path / "harness" / "prompts"
    prompts_root.mkdir(parents=True)
    _write_prompt_module(
        prompts_root,
        "implementation_default",
        "from pydantic import BaseModel\n"
        "from engineeringagent.ports import PromptDefinition, PromptInterpolation\n"
        "class ImplementationInput(BaseModel):\n"
        "    feature_id: str\n"
        "    specification_path: str\n"
        "    plan_path: str = ''\n"
        "    research_path: str = ''\n"
        "    handoff_path: str = ''\n"
        "    retry_feedback: str = ''\n"
        "class ImplementationOutput(BaseModel):\n"
        "    summary: str\n"
        "PROMPT_DEFINITION = PromptDefinition(\n"
        "    prompt_id='implementation_default',\n"
        "    purpose='implementation',\n"
        "    target='implementation',\n"
        "    output_mode='structured',\n"
        "    token_budget_hint=100,\n"
        "    input_model=ImplementationInput,\n"
        "    output_model=ImplementationOutput,\n"
        "    body_template='repo implementation\\n$feature_id\\n$specification_path\\n$retry_feedback\\n',\n"
        "    interpolations=(\n"
        "        PromptInterpolation(name='feature_id', source='test', required=True, rationale='test'),\n"
        "        PromptInterpolation(name='specification_path', source='test', required=True, rationale='test'),\n"
        "        PromptInterpolation(name='plan_path', source='test', required=False, rationale='test'),\n"
        "        PromptInterpolation(name='research_path', source='test', required=False, rationale='test'),\n"
        "        PromptInterpolation(name='handoff_path', source='test', required=False, rationale='test'),\n"
        "        PromptInterpolation(name='retry_feedback', source='test', required=False, rationale='test'),\n"
        "    ),\n"
        ")\n",
    )
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
        "    body_template='selector\\n$choices\\n',\n"
        "    interpolations=(PromptInterpolation(name='choices', source='test', required=True, rationale='test'),),\n"
        ")\n",
    )
    feature_path = tmp_path / "docs" / "features" / "spec.yaml"
    feature_path.parent.mkdir(parents=True)
    feature_path.write_text("id: FEAT-101\n", encoding="utf-8")

    prompt = _prompt_builder(prompts_root).build_implementation_prompt(
        ImplementationPromptRequest(
            feature_id="FEAT-101",
            specification_path=feature_path,
            retry_feedback="retry",
        )
    )

    assert prompt.startswith("repo implementation\nFEAT-101\n")
    assert prompt.rstrip().endswith("retry")
