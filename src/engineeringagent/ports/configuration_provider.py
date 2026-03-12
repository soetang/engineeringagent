"""Port contract for loading effective repository configuration."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from engineeringagent.domain.shared import RepositoryConfig


@runtime_checkable
class ConfigurationProvider(Protocol):
    """Load effective repository configuration for the current workspace."""

    def load(self) -> RepositoryConfig:
        """Return the merged repository configuration."""
        raise NotImplementedError
