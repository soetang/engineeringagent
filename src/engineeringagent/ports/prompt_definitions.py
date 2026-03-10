"""Prompt definition repository port."""

from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, ConfigDict

class PromptTemplate(BaseModel):
    """Named prompt template text."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    prompt_id: str
    template_text: str


class PromptDefinitionRepository(Protocol):
    """Load stable prompt template definitions by id."""

    def get(self, prompt_id: str) -> PromptTemplate:
        """Return one prompt template definition."""
        raise NotImplementedError

    def list_ids(self) -> list[str]:
        """Return available prompt template ids."""
        raise NotImplementedError
