"""Prompt-backed content generation for commits and pull requests."""

from pathlib import Path

from pydantic import BaseModel

from developer.agent_backends.protocol import AgentBackendProtocol
from developer.prompts.builder import _load_prompt_settings
from developer.prompts.errors import (
    PromptTemplateMissingError,
    PromptTemplateSyntaxError,
)
from developer.version_control.content_models import (
    CommitMessageOutput,
    CommitPromptContext,
    PullRequestContentOutput,
    PullRequestPromptContext,
)
from jinja2 import Template, TemplateError

from developer.config.service import ConfigService


class VersionControlContentService:
    """Generate commit and pull request content through an agent backend."""

    def __init__(
        self,
        agent_runner: AgentBackendProtocol,
        config_service: ConfigService | None = None,
    ) -> None:
        """Store the agent runner and configured prompt paths."""
        self._agent_runner = agent_runner
        self._config_service = config_service or ConfigService()
        self._settings = _load_prompt_settings(self._config_service)

    def build_commit_message(self, context: CommitPromptContext) -> CommitMessageOutput:
        """Generate one commit message, with deterministic fallback on failure."""
        prompt = self._render_prompt(self._settings.commit_prompt_path, context)
        try:
            result = self._agent_runner.run_agent(
                prompt,
                output_format=CommitMessageOutput,
            )
        except Exception:
            return CommitMessageOutput(
                subject=f"chore: implement {context.task_name}"[:72],
                body="",
            )
        return CommitMessageOutput.model_validate(result)

    def build_pull_request_content(
        self, context: PullRequestPromptContext
    ) -> PullRequestContentOutput:
        """Generate pull request title and body, with deterministic fallback."""
        prompt = self._render_prompt(self._settings.pull_request_prompt_path, context)
        try:
            result = self._agent_runner.run_agent(
                prompt,
                output_format=PullRequestContentOutput,
            )
        except Exception:
            summary = f"Complete task {context.task_name}."
            body = "## Summary\n- " + summary + "\n\n## Testing\n- Not run"
            return PullRequestContentOutput(
                title=f"Complete {context.task_name}",
                summary=[summary],
                body=body,
            )
        return PullRequestContentOutput.model_validate(result)

    def _render_prompt(self, prompt_path: str, context: BaseModel) -> str:
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
            return template.render(**context.model_dump(mode="json"))
        except TemplateError as exc:
            raise PromptTemplateSyntaxError(
                f"Failed to render prompt template: {path}"
            ) from exc
