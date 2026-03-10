"""Filesystem-backed prompt-definition adapter."""

from __future__ import annotations

from pathlib import Path

from engineeringagent.ports import PromptDefinition, PromptDefinitionRepository

from .prompt_catalog import override_prompt_definition


class FilesystemPromptDefinitionRepository(PromptDefinitionRepository):
    """Load prompt templates from one repository-local prompts directory."""

    def __init__(self, prompts_root: Path) -> None:
        self._prompts_root = prompts_root

    def get(self, prompt_id: str) -> PromptDefinition:
        template_path = self._prompts_root / f"{prompt_id}.md"
        if not template_path.is_file():
            available = ", ".join(self.list_ids())
            raise KeyError(
                f"unknown prompt definition {prompt_id!r}; available definitions: {available}"
            )
        return override_prompt_definition(
            prompt_id,
            body_template=template_path.read_text(encoding="utf-8"),
        )

    def list_ids(self) -> list[str]:
        if not self._prompts_root.is_dir():
            return []
        return sorted(path.stem for path in self._prompts_root.glob("*.md"))
