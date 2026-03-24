"""Shared prompt-configuration helpers."""

from engineeringagent.config.service import ConfigService
from engineeringagent.prompts.models import PromptSettings


def load_prompt_settings(config_service: ConfigService) -> PromptSettings:
    """Load prompt settings from the shared prompts section."""
    return config_service.get_config("prompts", PromptSettings)
