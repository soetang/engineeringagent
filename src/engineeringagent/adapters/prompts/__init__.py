"""Prompt-definition adapters."""

from .bundled_prompt_definitions import BundledPromptDefinitionRepository
from .filesystem_prompt_definitions import FilesystemPromptDefinitionRepository
from .project_prompt_definitions import ProjectPromptDefinitionRepository

__all__ = [
    "BundledPromptDefinitionRepository",
    "FilesystemPromptDefinitionRepository",
    "ProjectPromptDefinitionRepository",
]
