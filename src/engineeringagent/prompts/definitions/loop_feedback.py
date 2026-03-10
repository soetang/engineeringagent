"""Bundled feedback prompt definition."""

from __future__ import annotations

from typing import Mapping

from engineeringagent.ports import PromptDefinition, PromptInterpolation


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
