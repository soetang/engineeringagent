"""Prompt rendering helpers and publication-specific prompt adapters."""

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from jinja2 import Template, TemplateError
from pydantic import BaseModel

from engineeringagent.config.service import ConfigService
from engineeringagent.orchestrators.publication import (
    CommitMessageContext,
    PublicationPromptRenderer,
    PullRequestContentContext,
)
from engineeringagent.prompts.config import load_prompt_settings
from engineeringagent.prompts.errors import (
    PromptTemplateMissingError,
    PromptTemplateSyntaxError,
)


class ConfiguredPublicationPromptRenderer(PublicationPromptRenderer):
    """Render publication prompts from configured template paths."""

    def __init__(self, config_service: ConfigService | None = None) -> None:
        """Load publication prompt settings from config."""
        self._settings = load_prompt_settings(config_service or ConfigService())

    def render_commit_prompt(self, context: CommitMessageContext) -> str:
        """Render the configured commit-message prompt."""
        return render_prompt_template(
            self._settings.commit_prompt_path,
            context.model_dump(mode="json"),
        )

    def render_pull_request_prompt(self, context: PullRequestContentContext) -> str:
        """Render the configured pull-request prompt."""
        return render_prompt_template(
            self._settings.pull_request_prompt_path,
            context.model_dump(mode="json"),
        )


def render_prompt_template(prompt_path: str, context: Mapping[str, Any]) -> str:
    """Render one Jinja prompt from the configured path."""
    path = Path(prompt_path)
    try:
        template_text = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise PromptTemplateMissingError(
            f"Prompt template not found: {prompt_path}"
        ) from exc
    try:
        template = Template(template_text)
        return template.render(**dict(context))
    except TemplateError as exc:
        raise PromptTemplateSyntaxError(
            f"Failed to render prompt template: {path}"
        ) from exc


def render_prompt_model(prompt_path: str, context: BaseModel) -> str:
    """Render one prompt from a Pydantic model context."""
    return render_prompt_template(prompt_path, context.model_dump(mode="json"))
