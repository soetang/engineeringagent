"""Prompt assembly port used by orchestration code."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from engineeringagent.application.prompt_builder import ImplementationPromptRequest


class PromptBuilder(Protocol):
    """Render stable implementation prompts from normalized inputs."""

    def build_implementation_prompt(
        self, request: ImplementationPromptRequest
    ) -> str:
        """Render the implementation prompt for one iteration."""
        raise NotImplementedError
