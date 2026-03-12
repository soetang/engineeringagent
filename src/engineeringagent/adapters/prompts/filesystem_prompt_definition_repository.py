"""Filesystem-backed prompt-definition adapter."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

from engineeringagent.domain.shared.prompt_definition import PromptDefinition
from engineeringagent.ports import PromptDefinitionRepository


class FilesystemPromptDefinitionRepository(PromptDefinitionRepository):
    """Load Python-authored prompt definitions from one repository-local directory."""

    def __init__(self, prompts_root: Path) -> None:
        self._prompts_root = prompts_root

    def get(self, prompt_id: str) -> PromptDefinition:
        prompt_path = self._prompts_root / f"{prompt_id}.py"
        if not prompt_path.is_file():
            available = ", ".join(self.list_ids())
            raise KeyError(
                f"unknown prompt definition {prompt_id!r}; available definitions: {available}"
            )
        return _filesystem_prompt_definition(prompt_path)

    def list_ids(self) -> list[str]:
        if not self._prompts_root.is_dir():
            return []
        return sorted(path.stem for path in self._prompts_root.glob("*.py"))


def _filesystem_prompt_definition(prompt_path: Path) -> PromptDefinition:
    module_name = f"engineeringagent_project_prompt_{prompt_path.stem}"
    spec = importlib.util.spec_from_file_location(module_name, prompt_path)
    if spec is None or spec.loader is None:
        raise KeyError(f"failed to load prompt definition module from {prompt_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return _prompt_definition_from_module(module, prompt_path.stem)


def _prompt_definition_from_module(
    module: ModuleType,
    prompt_id: str,
) -> PromptDefinition:
    definition = getattr(module, "PROMPT_DEFINITION", None)
    if not isinstance(definition, PromptDefinition):
        raise KeyError(
            f"prompt definition module for {prompt_id!r} must export PROMPT_DEFINITION"
        )
    return definition
