"""Service for selecting a forge adapter."""

from developer.config.service import ConfigService
from developer.forge.adapters.github_adapter import GitHubForgeAdapter
from developer.forge.protocol import ForgeProtocol
from developer.forge.settings import ForgeSettings


class SelectForgeService:
    """Select a configured forge adapter."""

    def __init__(self, config_service: ConfigService | None = None) -> None:
        """Store config access for later adapter resolution."""
        self._config_service = config_service or ConfigService()

    def select(self) -> ForgeProtocol | None:
        """Return the configured adapter when forge publication is enabled."""
        settings = self._config_service.get_config("forge", ForgeSettings)
        if not settings.enabled:
            return None
        if settings.provider != "github":
            raise ValueError(f"Unsupported forge provider: {settings.provider}")
        return GitHubForgeAdapter()
