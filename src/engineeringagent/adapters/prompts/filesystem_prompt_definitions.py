"""Filesystem-backed prompt-definition adapter."""

from __future__ import annotations

from pathlib import Path

from engineeringagent.ports import PromptDefinitionRepository, PromptTemplate


class FilesystemPromptDefinitionRepository(PromptDefinitionRepository):
    """Load prompt templates from one repository-local prompts directory."""

    def __init__(self, prompts_root: Path) -> None:
        self._prompts_root = prompts_root

    def get(self, prompt_id: str) -> PromptTemplate:
        template_path = self._prompts_root / f"{prompt_id}.md"
        if not template_path.is_file():
            available = ", ".join(self.list_ids())
            raise KeyError(
                f"unknown prompt template {prompt_id!r}; available templates: {available}"
            )
        return PromptTemplate(
            prompt_id=prompt_id,
            template_text=template_path.read_text(encoding="utf-8"),
        )

    def list_ids(self) -> list[str]:
        if not self._prompts_root.is_dir():
            return []
        return sorted(path.stem for path in self._prompts_root.glob("*.md"))
