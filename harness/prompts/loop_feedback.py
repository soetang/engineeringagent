"""Repository-local feedback prompt definition."""

from __future__ import annotations

from typing import Mapping

from pydantic import BaseModel, ConfigDict

from engineeringagent.ports import PromptDefinition, PromptInterpolation


class FeedbackPromptInput(BaseModel):
    """Typed input contract for feedback injection."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    feedback: str


def _render(values: Mapping[str, object]) -> str:
    return (
        "\n\nPrevious feedback is available. Fix the issues reported below "
        "before marking the feature complete:\n"
        f"{values['feedback']}\n"
    )


PROMPT_DEFINITION = PromptDefinition(
    prompt_id="loop_feedback",
    purpose="Inject retry feedback into the next implementation attempt.",
    target="implementation",
    output_mode="text",
    token_budget_hint=800,
    input_model=FeedbackPromptInput,
    renderer=_render,
    interpolations=(
        PromptInterpolation(
            name="feedback",
            source="application.retry_feedback",
            required=True,
            render_as="markdown_block",
            content_policy="summary_only",
            content_bound=None,
            rationale="The implementation prompt needs the prior failure context.",
        ),
    ),
)
