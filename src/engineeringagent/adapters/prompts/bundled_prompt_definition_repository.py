"""Bundled prompt-definition adapter."""

from __future__ import annotations

from engineeringagent.ports import PromptDefinition, PromptDefinitionRepository

from .prompt_catalog import bundled_prompt_definition, bundled_prompt_ids


class BundledPromptDefinitionRepository(PromptDefinitionRepository):
    """Load prompt templates from the packaged markdown bundle."""

    def get(self, prompt_id: str) -> PromptDefinition:
        return bundled_prompt_definition(prompt_id)

    def list_ids(self) -> list[str]:
        return bundled_prompt_ids()
