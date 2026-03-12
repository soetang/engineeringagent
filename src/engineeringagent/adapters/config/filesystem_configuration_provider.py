"""Filesystem-backed adapter for effective repository configuration."""

from __future__ import annotations

from pathlib import Path

from engineeringagent.domain.shared import RepositoryConfig

from .filesystem import load_repository_config


class FilesystemConfigurationProvider:
    """Load repository configuration from the current project root."""

    def __init__(self, project_root: Path) -> None:
        self._project_root = project_root.resolve()

    def load(self) -> RepositoryConfig:
        """Return the effective repository configuration."""
        return load_repository_config(self._project_root)
