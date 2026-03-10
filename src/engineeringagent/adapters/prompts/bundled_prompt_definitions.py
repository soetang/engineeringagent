"""Bundled prompt-template adapter."""

from __future__ import annotations

from importlib.resources import files

from engineeringagent.ports import PromptDefinitionRepository, PromptTemplate

_TEMPLATE_PACKAGE = "engineeringagent.prompts.templates"
_PROMPT_FILES = {
    "loop_feedback": "loop_feedback.md",
    "loop_implementation": "loop_implementation.md",
    "loop_selector": "loop_selector.md",
}


class BundledPromptDefinitionRepository(PromptDefinitionRepository):
    """Load prompt templates from the packaged markdown bundle."""

    def get(self, prompt_id: str) -> PromptTemplate:
        try:
            filename = _PROMPT_FILES[prompt_id]
        except KeyError as exc:
            available = ", ".join(sorted(_PROMPT_FILES))
            raise KeyError(
                f"unknown prompt template {prompt_id!r}; available templates: {available}"
            ) from exc
        template_text = files(_TEMPLATE_PACKAGE).joinpath(filename).read_text(
            encoding="utf-8"
        )
        return PromptTemplate(prompt_id=prompt_id, template_text=template_text)

    def list_ids(self) -> list[str]:
        return sorted(_PROMPT_FILES)
