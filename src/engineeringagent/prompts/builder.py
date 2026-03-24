from typing import Any, Mapping

from engineeringagent.config.service import ConfigService
from engineeringagent.orchestrators.loop.protocols import PromptBuilder

from .config import load_prompt_settings
from .renderer import render_prompt_template


class OrchestratorPromptBuilder(PromptBuilder):
    """Build prompts from configured Jinja templates."""

    def __init__(self, config_service: ConfigService | None = None):
        """Load prompt settings from the shared prompt section."""
        self._config_service = config_service or ConfigService()
        self._settings = load_prompt_settings(self._config_service)

    def build(self, context: Mapping[str, Any]) -> str:
        """Render the implementation prompt with the provided context."""
        return render_prompt_template(
            self._settings.implementation_prompt_path, context
        )
