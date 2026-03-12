"""Repository-local implementation prompt definition."""

from __future__ import annotations

from typing import Callable, cast

from pydantic import BaseModel, ConfigDict, Field

from engineeringagent.ports import PromptDefinition, PromptInterpolation


class ImplementationPromptInput(BaseModel):
    """Typed input contract for the implementation prompt."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    feature_id: str
    specification_path: str
    plan_path: str = ""
    research_path: str = ""
    handoff_path: str = ""
    retry_feedback: str = ""


class ImplementationPromptOutputV1(BaseModel):
    """Structured implementation-agent response contract."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    summary: str
    changed_paths: list[str] = Field(default_factory=list)
    follow_up_notes: list[str] = Field(default_factory=list)


def _render(values: ImplementationPromptInput) -> str:
    sections = [
        f"Feature: {values.feature_id}",
        "Read and follow these files:",
        f"- specification: {values.specification_path}",
    ]
    plan_path = values.plan_path.strip()
    research_path = values.research_path.strip()
    handoff_path = values.handoff_path.strip()
    retry_feedback = values.retry_feedback.strip()

    if plan_path:
        sections.append(f"- plan: {plan_path}")
    if research_path:
        sections.append(f"- research: {research_path}")
    if handoff_path:
        sections.append(f"- handoff: {handoff_path}")
    if retry_feedback:
        sections.extend(("", "Retry feedback:", retry_feedback))
    return "\n".join(sections)


PROMPT_DEFINITION = PromptDefinition(
    prompt_id="implementation_default",
    purpose="Execute the active work unit from a feature specification.",
    target="implementation",
    output_mode="structured",
    token_budget_hint=6000,
    input_model=ImplementationPromptInput,
    output_model=ImplementationPromptOutputV1,
    renderer=cast(Callable[[BaseModel], str], _render),
    interpolations=(
        PromptInterpolation(
            name="feature_id",
            source="feature_specification.id",
            required=True,
            render_as="scalar",
            content_policy="summary_only",
            content_bound=None,
            rationale="The agent should know which feature it is executing.",
        ),
        PromptInterpolation(
            name="specification_path",
            source="runtime.specification_path",
            required=True,
            render_as="path_list",
            content_policy="path_only",
            content_bound=None,
            rationale="The agent should read the selected specification file itself.",
        ),
        PromptInterpolation(
            name="plan_path",
            source="runtime.plan_path",
            required=False,
            render_as="path_list",
            content_policy="path_only",
            content_bound=None,
            rationale="The agent should read the selected plan file when one exists.",
        ),
        PromptInterpolation(
            name="research_path",
            source="runtime.research_path",
            required=False,
            render_as="path_list",
            content_policy="path_only",
            content_bound=None,
            rationale="The agent should read the research file when one exists.",
        ),
        PromptInterpolation(
            name="handoff_path",
            source="runtime.handoff_path",
            required=False,
            render_as="path_list",
            content_policy="path_only",
            content_bound=None,
            rationale="The agent should read the persisted handoff file when continuing the same feature.",
        ),
        PromptInterpolation(
            name="retry_feedback",
            source="runtime.retry_feedback",
            required=False,
            render_as="markdown_block",
            content_policy="summary_only",
            content_bound=None,
            rationale="The latest correction loop should be available when retrying.",
        ),
    ),
)
