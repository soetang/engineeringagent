"""Prompt-definition loader helpers for bundled and repository-local prompts."""

from __future__ import annotations

import importlib
import importlib.util
from pathlib import Path
from types import ModuleType

from engineeringagent.ports import PromptDefinition

_BUNDLED_PROMPT_MODULES = {
    "loop_feedback": "engineeringagent.prompts.definitions.loop_feedback",
    "loop_implementation": "engineeringagent.prompts.definitions.loop_implementation",
    "loop_selector": "engineeringagent.prompts.definitions.loop_selector",
}


def bundled_prompt_ids() -> list[str]:
    """Return the stable bundled prompt ids."""
    return sorted(_BUNDLED_PROMPT_MODULES)


def bundled_prompt_definition(prompt_id: str) -> PromptDefinition:
    """Return one bundled Python-authored prompt definition."""
    try:
        module_name = _BUNDLED_PROMPT_MODULES[prompt_id]
    except KeyError as exc:
        available = ", ".join(bundled_prompt_ids())
        raise KeyError(
            f"unknown prompt definition {prompt_id!r}; available definitions: {available}"
        ) from exc

    return _prompt_definition_from_module(importlib.import_module(module_name), prompt_id)


def filesystem_prompt_definition(prompt_path: Path) -> PromptDefinition:
    """Load one repository-local Python prompt definition module."""
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
