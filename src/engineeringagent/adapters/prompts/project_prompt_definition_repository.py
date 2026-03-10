"""Repository-aware prompt-definition adapter selection."""

from __future__ import annotations

from pathlib import Path

from engineeringagent.config import resolve_harness_root
from engineeringagent.ports import PromptDefinition, PromptDefinitionRepository

from .bundled_prompt_definition_repository import BundledPromptDefinitionRepository
from .filesystem_prompt_definition_repository import (
    FilesystemPromptDefinitionRepository,
)


class ProjectPromptDefinitionRepository(PromptDefinitionRepository):
    """Prefer repository-local prompt templates and fall back to bundled ones."""

    def __init__(
        self,
        project_root: Path,
        *,
        bundled_repository: PromptDefinitionRepository | None = None,
    ) -> None:
        prompts_root = resolve_harness_root(project_root) / "prompts"
        self._filesystem_repository = FilesystemPromptDefinitionRepository(prompts_root)
        self._bundled_repository = (
            bundled_repository or BundledPromptDefinitionRepository()
        )

    def get(self, prompt_id: str) -> PromptDefinition:
        try:
            return self._filesystem_repository.get(prompt_id)
        except KeyError:
            return self._bundled_repository.get(prompt_id)

    def list_ids(self) -> list[str]:
        return sorted(
            set(self._filesystem_repository.list_ids())
            | set(self._bundled_repository.list_ids())
        )
