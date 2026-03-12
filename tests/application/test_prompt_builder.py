from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import engineeringagent.application.prompt_builder as prompt_builder_module
from engineeringagent.application.prompt_builder import PromptBuilder
from engineeringagent.application.prompt_builder import ImplementationPromptRequest
from engineeringagent.domain.shared.prompt_definition import PromptDefinition
from engineeringagent.domain.specification import (
    FeatureArtifacts,
    FeaturePriority,
    FeatureSpecification,
    FeatureStatus,
    FeatureType,
    PlanningTier,
)
from engineeringagent.ports import PromptDefinitionRepository


class LocalPromptDefinitionRepository(PromptDefinitionRepository):
    """Test-local prompt repository that stays on the port surface."""

    def __init__(self, prompts_root: Path) -> None:
        self._prompts_root = prompts_root

    def get(self, prompt_id: str) -> PromptDefinition:
        prompt_path = self._prompts_root / f"{prompt_id}.py"
        if not prompt_path.is_file():
            available = ", ".join(self.list_ids())
            raise KeyError(
                f"unknown prompt definition {prompt_id!r}; available definitions: {available}"
            )
        return _load_prompt_definition(prompt_path)

    def list_ids(self) -> list[str]:
        if not self._prompts_root.is_dir():
            return []
        return sorted(path.stem for path in self._prompts_root.glob("*.py"))


def _prompt_builder(
    prompts_root: Path | None = None,
    *,
    implementation_prompt_id: str = "implementation_default",
) -> PromptBuilder:
    resolved_prompts_root = prompts_root or (
        Path(__file__).resolve().parents[2] / "harness" / "prompts"
    )
    return PromptBuilder(
        LocalPromptDefinitionRepository(resolved_prompts_root),
        implementation_prompt_id=implementation_prompt_id,
    )


def _load_prompt_definition(prompt_path: Path) -> PromptDefinition:
    module_name = f"test_prompt_definition_{prompt_path.stem}"
    spec = importlib.util.spec_from_file_location(module_name, prompt_path)
    if spec is None or spec.loader is None:
        raise KeyError(f"failed to load prompt definition module from {prompt_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return _prompt_definition_from_module(module, prompt_path.stem)


def _prompt_definition_from_module(
    module: ModuleType, prompt_id: str
) -> PromptDefinition:
    definition = getattr(module, "PROMPT_DEFINITION", None)
    if not isinstance(definition, PromptDefinition):
        raise KeyError(
            f"prompt definition module for {prompt_id!r} must export PROMPT_DEFINITION"
        )
    return definition


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


def test_build_implementation_prompt_request_does_not_invent_handoff_path(
    tmp_path: Path,
) -> None:
    """Application prompt requests keep handoff optional until runtime provides one."""

    feature_path = (
        tmp_path
        / "docs"
        / "specifications"
        / "features"
        / "FEAT-900"
        / "specification.yaml"
    )
    feature_path.parent.mkdir(parents=True, exist_ok=True)

    request = _prompt_builder().build_implementation_prompt_request(
        specification=_feature_specification(),
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
        tmp_path
        / "docs"
        / "specifications"
        / "features"
        / "FEAT-900-bundled-smoke-test"
        / "specification.yaml"
    )
    feature_path.parent.mkdir(parents=True, exist_ok=True)
    specification = _feature_specification(
        feature_id="FEAT-900-bundled-smoke-test",
        status=FeatureStatus.IN_PROGRESS,
        planning_tier=PlanningTier.RESEARCHED,
        artifacts=FeatureArtifacts(plan="plan.md", research="research.md"),
    )

    prompt = _prompt_builder().build_implementation_prompt(
        ImplementationPromptRequest(
            feature_id=specification.feature_id,
            specification_path=feature_path,
            plan_path=str(feature_path.parent / "plan.md"),
            research_path=str(feature_path.parent / "research.md"),
            handoff_path=".engineeringagent/progress/FEAT-900/handoff.md",
            retry_feedback="fix the failing tests first",
        )
    )

    assert f"Feature: {specification.feature_id}" in prompt
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

    feature_path = (
        tmp_path
        / "docs"
        / "specifications"
        / "features"
        / "FEAT-900"
        / "specification.yaml"
    )
    feature_path.parent.mkdir(parents=True, exist_ok=True)

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

    feature_path = (
        tmp_path
        / "docs"
        / "specifications"
        / "features"
        / "FEAT-900"
        / "specification.yaml"
    )
    feature_path.parent.mkdir(parents=True, exist_ok=True)

    assert prompt_builder_module._normalize_plain_prompt_feedback(None) is None
    request = _prompt_builder().build_implementation_prompt_request(
        specification=_feature_specification(
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
        "from engineeringagent.domain.shared.prompt_definition import PromptDefinition, PromptInterpolation\n"
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

    prompt = _prompt_builder(prompts_root).build_implementation_prompt(
        ImplementationPromptRequest(
            feature_id="FEAT-900",
            specification_path=tmp_path / "docs/specifications/features/FEAT-900/specification.yaml",
            retry_feedback="retry this",
        )
    )

    assert prompt == (
        "repo implementation\n"
        "FEAT-900\n"
        f"{tmp_path / 'docs/specifications/features/FEAT-900/specification.yaml'}\n"
        "retry this\n"
    )


def test_prompt_builder_uses_configured_implementation_prompt_id(
    tmp_path: Path,
) -> None:
    """The builder should respect the configured prompt-definition id."""

    prompts_root = tmp_path / "harness" / "prompts"
    prompts_root.mkdir(parents=True)
    _write_prompt_module(
        prompts_root,
        "repo_override",
        "from pydantic import BaseModel\n"
        "from engineeringagent.domain.shared.prompt_definition import PromptDefinition, PromptInterpolation\n"
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
        "    prompt_id='repo_override',\n"
        "    purpose='implementation',\n"
        "    target='implementation',\n"
        "    output_mode='structured',\n"
        "    token_budget_hint=100,\n"
        "    input_model=ImplementationInput,\n"
        "    output_model=ImplementationOutput,\n"
        "    body_template='override:$feature_id:$specification_path',\n"
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

    prompt = _prompt_builder(
        prompts_root,
        implementation_prompt_id="repo_override",
    ).build_implementation_prompt(
        ImplementationPromptRequest(
            feature_id="FEAT-900",
            specification_path=tmp_path / "docs/specifications/features/FEAT-900/specification.yaml",
        )
    )

    assert prompt == (
        "override:FEAT-900:"
        f"{tmp_path / 'docs/specifications/features/FEAT-900/specification.yaml'}"
    )


def test_prompt_builder_renders_with_typed_prompt_input_model(
    tmp_path: Path,
) -> None:
    """Repository prompt renderers should receive validated typed input models."""

    prompts_root = tmp_path / "harness" / "prompts"
    prompts_root.mkdir(parents=True)
    _write_prompt_module(
        prompts_root,
        "implementation_default",
        "from pydantic import BaseModel\n"
        "from engineeringagent.domain.shared.prompt_definition import PromptDefinition, PromptInterpolation\n"
        "class ImplementationInput(BaseModel):\n"
        "    feature_id: str\n"
        "    specification_path: str\n"
        "    plan_path: str = ''\n"
        "    research_path: str = ''\n"
        "    handoff_path: str = ''\n"
        "    retry_feedback: str = ''\n"
        "class ImplementationOutput(BaseModel):\n"
        "    summary: str\n"
        "def _render(values: ImplementationInput) -> str:\n"
        "    return f'{values.__class__.__name__}:{values.feature_id}:{values.specification_path}'\n"
        "PROMPT_DEFINITION = PromptDefinition(\n"
        "    prompt_id='implementation_default',\n"
        "    purpose='implementation',\n"
        "    target='implementation',\n"
        "    output_mode='structured',\n"
        "    token_budget_hint=100,\n"
        "    input_model=ImplementationInput,\n"
        "    output_model=ImplementationOutput,\n"
        "    renderer=_render,\n"
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

    prompt = _prompt_builder(prompts_root).build_implementation_prompt(
        ImplementationPromptRequest(
            feature_id="FEAT-900",
            specification_path=tmp_path / "docs/specifications/features/FEAT-900/specification.yaml",
        )
    )

    assert prompt == (
        "ImplementationInput:FEAT-900:"
        f"{tmp_path / 'docs/specifications/features/FEAT-900/specification.yaml'}"
    )
