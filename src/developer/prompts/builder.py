from pathlib import Path
from typing import Any, Mapping

from jinja2 import Template, TemplateError

from developer.config.service import ConfigService
from developer.orchestrators.protocols import PromptBuilder

from .errors import PromptTemplateMissingError, PromptTemplateSyntaxError
from .settings import OrchestratorPromptSettings


class OrchestratorPromptBuilder(PromptBuilder):
    """Build prompts from configured Jinja templates."""

    def __init__(self, config_service: ConfigService | None = None):
        self._config_service = config_service or ConfigService()
        self._settings = self._config_service.get_config(
            "orchestrator", OrchestratorPromptSettings
        )

    def build(self, context: Mapping[str, Any]) -> str:
        """Render the implementation prompt with the provided context."""
        prompt_path = Path(self._settings.implementation_prompt_path)

        try:
            template_text = prompt_path.read_text()
        except FileNotFoundError as exc:
            raise PromptTemplateMissingError(
                f"Prompt template not found: {self._settings.implementation_prompt_path}"
            ) from exc

        try:
            template = Template(template_text)
            return template.render(**dict(context))
        except TemplateError as exc:
            raise PromptTemplateSyntaxError(
                f"Failed to render prompt template: {prompt_path}"
            ) from exc
