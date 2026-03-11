"""Repository-local implementation prompt definition."""

from __future__ import annotations

from typing import Mapping

from pydantic import BaseModel, ConfigDict, Field

from engineeringagent.ports import PromptDefinition, PromptInterpolation


class ImplementationPromptInput(BaseModel):
    """Typed input contract for the implementation prompt."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    artifact_paths: str
    handoff_path: str = ""
    feature_id: str
    feature_title: str
    objective: str
    context: str
    progress_unit: str
    current_progress_reference: str
    progress_context_instruction: str
    progress_update_instruction: str


class ImplementationPromptOutputV1(BaseModel):
    """Structured implementation-agent response contract."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    summary: str
    changed_paths: list[str] = Field(default_factory=list)
    follow_up_notes: list[str] = Field(default_factory=list)


def _render(values: Mapping[str, object]) -> str:
    handoff_path = str(values["handoff_path"]).strip()
    sections = [
        str(values["artifact_paths"]),
    ]
    if handoff_path:
        sections.extend(
            [
                (
                    "Before doing new work, read prior handoff context from "
                    f"{handoff_path}."
                ),
                (
                    "Because handoff is append-only, read from the bottom first "
                    "(`tail -n 40 ...`) to get the latest iteration."
                ),
                "Do not write the handoff file directly; loop/runtime owns handoff file appends.",
                "",
            ]
        )
    sections.extend(
        [
            "If there is feedback, from previous iterations always address that first.",
            "",
            "If no feedback is present:",
            (
                "Execute one incremental implementation step for feature "
                f"{values['feature_id']} ({values['feature_title']})."
            ),
            f"Identify the most important open {values['progress_unit']} first.",
            (
                "Before making changes - research the code base. You can use multiple "
                "parallel subagents to do the reasearch."
            ),
            (
                f"Then implement the most important {values['progress_unit']}, using TDD - "
                "Write a tests, implement funtionality that passes the test, refactor."
            ),
            "",
            (
                "Always focus on the intention of the feature over overly specific "
                "instructions, especially since other features might have been "
                "implemented in the meantime. Don't be afraid to change current "
                "implementation details if that obviously simplifies the code."
            ),
            "",
            "After implementing functionality or resolving problems, run the tests for that unit of code that was improved.",
            "",
            f"Objective: {values['objective']}",
            f"Context: {values['context']}",
            str(values["current_progress_reference"]).rstrip(),
            str(values["progress_context_instruction"]),
            "",
            "Make minimal deterministic code/documentation edits, and keep CLI behavior unchanged unless the spec explicitly requires it.",
            "",
            (
                f"{values['progress_update_instruction']} "
                "Validate with: `uv run engineeringagent validate --schema-only`."
            ),
            (
                f"Run the chosen {values['progress_unit']}'s listed verification command(s) "
                "only after it transitions to done in this iteration, then report "
                "concise outcomes covering: what changed, which verification "
                "passed/failed, and what remains."
            ),
            "",
            (
                "Your output should be written so that the next developer can easily "
                "continue the work. If you discover issues or surprises please "
                "clearly note it in the summary with `ISSUE: description of issue..`"
            ),
        ]
    )
    return "\n".join(section for section in sections if section != "")


PROMPT_DEFINITION = PromptDefinition(
    prompt_id="loop_implementation",
    purpose="Guide one deterministic implementation step for the active feature.",
    target="implementation",
    output_mode="structured",
    token_budget_hint=6000,
    input_model=ImplementationPromptInput,
    output_model=ImplementationPromptOutputV1,
    renderer=_render,
    interpolations=(
        PromptInterpolation(
            name="artifact_paths",
            source="application.artifact_paths",
            required=True,
            render_as="path_list",
            content_policy="path_only",
            content_bound=None,
            rationale="Artifact paths are the canonical references for implementation.",
        ),
        PromptInterpolation(
            name="handoff_path",
            source="application.handoff_path",
            required=False,
            render_as="scalar",
            content_policy="path_only",
            content_bound=None,
            rationale="The agent needs the handoff artifact path when resuming work.",
        ),
        PromptInterpolation(
            name="feature_id",
            source="application.feature.id",
            required=True,
            render_as="scalar",
            content_policy="summary_only",
            content_bound=None,
            rationale="The prompt identifies the active feature deterministically.",
        ),
        PromptInterpolation(
            name="feature_title",
            source="application.feature.title",
            required=True,
            render_as="scalar",
            content_policy="summary_only",
            content_bound=None,
            rationale="The prompt includes the feature title for operator context.",
        ),
        PromptInterpolation(
            name="objective",
            source="application.feature.objective",
            required=True,
            render_as="markdown_block",
            content_policy="summary_only",
            content_bound=None,
            rationale="The objective keeps the implementation step aligned with intent.",
        ),
        PromptInterpolation(
            name="context",
            source="application.feature.context",
            required=True,
            render_as="markdown_block",
            content_policy="summary_only",
            content_bound=None,
            rationale="The prompt carries explicit feature context.",
        ),
        PromptInterpolation(
            name="progress_unit",
            source="application.progress.kind",
            required=True,
            render_as="scalar",
            content_policy="summary_only",
            content_bound=None,
            rationale="The prompt names the progress unit to update.",
        ),
        PromptInterpolation(
            name="current_progress_reference",
            source="application.progress.current_reference",
            required=True,
            render_as="scalar",
            content_policy="summary_only",
            content_bound=None,
            rationale="The current progress reference anchors the next increment.",
        ),
        PromptInterpolation(
            name="progress_context_instruction",
            source="application.progress.context_instruction",
            required=True,
            render_as="markdown_block",
            content_policy="summary_only",
            content_bound=None,
            rationale="The prompt states the canonical progress source of truth.",
        ),
        PromptInterpolation(
            name="progress_update_instruction",
            source="application.progress.update_instruction",
            required=True,
            render_as="markdown_block",
            content_policy="summary_only",
            content_bound=None,
            rationale="The prompt explains how progress should be updated.",
        ),
    ),
)
