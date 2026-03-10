"""Bundled selector prompt definition."""

from __future__ import annotations

from typing import Mapping

from engineeringagent.ports import PromptDefinition, PromptInterpolation


def _render(values: Mapping[str, object]) -> str:
    return (
        "Choose the next feature spec to execute from this pending set. "
        "Reply with exactly one feature path from the list and no extra text.\n"
        f"{values['choices']}\n"
    )


PROMPT_DEFINITION = PromptDefinition(
    prompt_id="loop_selector",
    purpose="Select the next eligible feature specification from a candidate list.",
    target="operator",
    renderer=_render,
    interpolations=(
        PromptInterpolation(
            name="choices",
            source="application.feature_selection.choices",
            required=True,
            render_as="bullet_list",
            content_policy="summary_only",
            content_bound=None,
            rationale="The selector prompt only needs deterministic feature summaries.",
        ),
    ),
)
