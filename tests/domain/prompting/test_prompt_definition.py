from __future__ import annotations

import pytest
from pydantic import BaseModel

from engineeringagent.domain.prompting import PromptDefinition, PromptInterpolation


class _InputModel(BaseModel):
    required_value: str


def test_prompt_definition_validation_branches_are_explicit() -> None:
    """Prompt-definition invariants should fail with deterministic messages."""
    interpolation = PromptInterpolation(
        name="required_value",
        source="runtime.required_value",
        required=True,
        rationale="Needed for rendering.",
    )

    with pytest.raises(ValueError, match="duplicate interpolations"):
        PromptDefinition(
            prompt_id="duplicate",
            purpose="test",
            target="implementation",
            output_mode="text",
            token_budget_hint=1,
            input_model=_InputModel,
            body_template="${required_value}",
            interpolations=(interpolation, interpolation),
        )

    with pytest.raises(ValueError, match="must define either body_template or renderer"):
        PromptDefinition(
            prompt_id="missing-renderer",
            purpose="test",
            target="implementation",
            output_mode="text",
            token_budget_hint=1,
            input_model=_InputModel,
            interpolations=(interpolation,),
        )

    with pytest.raises(ValueError, match="must not define both body_template and renderer"):
        PromptDefinition(
            prompt_id="double-renderer",
            purpose="test",
            target="implementation",
            output_mode="text",
            token_budget_hint=1,
            input_model=_InputModel,
            body_template="${required_value}",
            renderer=lambda values: str(values.model_dump()["required_value"]),
            interpolations=(interpolation,),
        )

    with pytest.raises(ValueError, match="uses undeclared placeholders"):
        PromptDefinition(
            prompt_id="undeclared",
            purpose="test",
            target="implementation",
            output_mode="text",
            token_budget_hint=1,
            input_model=_InputModel,
            body_template="${required_value} ${missing_value}",
            interpolations=(interpolation,),
        )

    with pytest.raises(ValueError, match="positive token_budget_hint"):
        PromptDefinition(
            prompt_id="bad-budget",
            purpose="test",
            target="implementation",
            output_mode="text",
            token_budget_hint=0,
            input_model=_InputModel,
            body_template="${required_value}",
            interpolations=(interpolation,),
        )

    with pytest.raises(ValueError, match="must define output_model"):
        PromptDefinition(
            prompt_id="structured-missing-output",
            purpose="test",
            target="implementation",
            output_mode="structured",
            token_budget_hint=1,
            input_model=_InputModel,
            body_template="${required_value}",
            interpolations=(interpolation,),
        )


def test_prompt_definition_render_rejects_invalid_input_shapes() -> None:
    """Prompt rendering should reject unexpected and missing interpolations."""
    definition = PromptDefinition(
        prompt_id="implementation_default",
        purpose="test",
        target="implementation",
        output_mode="text",
        token_budget_hint=1,
        input_model=_InputModel,
        body_template="${required_value}",
        interpolations=(
            PromptInterpolation(
                name="required_value",
                source="runtime.required_value",
                required=True,
                rationale="Needed for rendering.",
            ),
        ),
    )

    with pytest.raises(ValueError, match="unexpected interpolations"):
        definition.render({"required_value": "ok", "extra": "boom"})

    with pytest.raises(ValueError, match="missing required interpolations"):
        definition.render({})

    assert definition.placeholder_names == ("required_value",)
    assert definition.render({"required_value": "ok"}) == "ok"
