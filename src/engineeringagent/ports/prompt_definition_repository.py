"""Prompt-definition repository port."""

from __future__ import annotations

from typing import Protocol

from engineeringagent.domain.shared.prompt_definition import PromptDefinition


class PromptDefinitionRepository(Protocol):
    """Load stable prompt definitions by id."""

    def get(self, prompt_id: str) -> PromptDefinition:
        """Return one prompt definition."""
        raise NotImplementedError

    def list_ids(self) -> list[str]:
        """Return available prompt definition ids."""
        raise NotImplementedError
