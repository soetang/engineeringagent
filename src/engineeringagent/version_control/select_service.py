"""Service for selecting a version control adapter."""

from engineeringagent.config.service import ConfigService
from engineeringagent.version_control.adapters.git_adapter import (
    GitVersionControlAdapter,
)
from engineeringagent.version_control.protocol import VersionControlProtocol
from engineeringagent.version_control.settings import VersionControlSettings


class SelectVersionControlService:
    """Select a configured version control adapter."""

    def __init__(self, config_service: ConfigService | None = None) -> None:
        """Store config access for later adapter resolution."""
        self._config_service = config_service or ConfigService()

    def select(self) -> VersionControlProtocol | None:
        """Return the configured adapter when version control is enabled."""
        settings = self._config_service.get_config(
            "version_control", VersionControlSettings
        )
        if not settings.enabled:
            return None
        if settings.provider != "git":
            raise ValueError(
                f"Unsupported version control provider: {settings.provider}"
            )
        return GitVersionControlAdapter(settings=settings)
