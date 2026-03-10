"""Shared prompt-definition metadata for bundled and repository-local prompts."""

from __future__ import annotations

from importlib.resources import files
from string import Template
from typing import Literal, TypedDict

from engineeringagent.ports import PromptDefinition, PromptInterpolation

PromptTarget = Literal["implementation", "reviewer", "operator"]


class _PromptMetadata(TypedDict):
    purpose: str
    target: PromptTarget
    interpolations: tuple[PromptInterpolation, ...]

_TEMPLATE_PACKAGE = "engineeringagent.prompts.templates"
_PROMPT_FILES = {
    "loop_feedback": "loop_feedback.md",
    "loop_implementation": "loop_implementation.md",
    "loop_selector": "loop_selector.md",
}

_PROMPT_METADATA: dict[str, _PromptMetadata] = {
    "loop_feedback": {
        "purpose": "Inject retry feedback into the next implementation attempt.",
        "target": "implementation",
        "interpolations": (
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
    },
    "loop_implementation": {
        "purpose": "Guide one deterministic implementation step for the active feature.",
        "target": "implementation",
        "interpolations": (
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
                required=True,
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
    },
    "loop_selector": {
        "purpose": "Select the next eligible feature specification from a candidate list.",
        "target": "operator",
        "interpolations": (
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
    },
}


def bundled_prompt_ids() -> list[str]:
    """Return the stable bundled prompt ids."""
    return sorted(_PROMPT_FILES)


def bundled_prompt_definition(prompt_id: str) -> PromptDefinition:
    """Return one bundled prompt definition with packaged template content."""
    try:
        filename = _PROMPT_FILES[prompt_id]
        metadata = _PROMPT_METADATA[prompt_id]
    except KeyError as exc:
        available = ", ".join(bundled_prompt_ids())
        raise KeyError(
            f"unknown prompt definition {prompt_id!r}; available definitions: {available}"
        ) from exc

    template_text = files(_TEMPLATE_PACKAGE).joinpath(filename).read_text(
        encoding="utf-8"
    )
    return PromptDefinition(
        prompt_id=prompt_id,
        purpose=metadata["purpose"],
        target=metadata["target"],
        body_template=template_text,
        interpolations=metadata["interpolations"],
    )


def override_prompt_definition(
    prompt_id: str,
    *,
    body_template: str,
) -> PromptDefinition:
    """Return a repository-local override using the bundled contract when available."""
    if prompt_id in _PROMPT_METADATA:
        metadata = _PROMPT_METADATA[prompt_id]
        return PromptDefinition(
            prompt_id=prompt_id,
            purpose=metadata["purpose"],
            target=metadata["target"],
            body_template=body_template,
            interpolations=metadata["interpolations"],
        )

    return PromptDefinition(
        prompt_id=prompt_id,
        purpose="Repository-local prompt definition.",
        target="operator",
        body_template=body_template,
        interpolations=tuple(
            PromptInterpolation(
                name=name,
                source="repository.prompt_override",
                required=True,
                render_as="scalar",
                content_policy="summary_only",
                content_bound=None,
                rationale="Repository-local prompts declare placeholders from the template.",
            )
            for name in _placeholder_names(body_template)
        ),
    )


def _placeholder_names(template_text: str) -> tuple[str, ...]:
    names: set[str] = set()
    for match in Template.pattern.finditer(template_text):
        name = match.group("named") or match.group("braced")
        if name:
            names.add(name)
    return tuple(sorted(names))
