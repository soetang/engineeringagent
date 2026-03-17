"""Agent selection service that uses configuration or explicit parameters."""

from typing import Optional, Tuple
from developer.config.service import ConfigService
from developer.agents.settings import AgentSettings
from developer.agents.adapters.codex_adapter import CodexAdapter
from developer.agents.adapters.vibe_adapter import VibeAdapter
from developer.agents.protocol import AgentProtocol


class SelectAgentService:
    """Service for selecting agents based on configuration or explicit parameters."""

    def __init__(self):
        """Initialize the agent selection service."""
        self.config_service = ConfigService()

    def select_agent(
        self,
        backend: Optional[str] = None,
        profile: Optional[str] = None,
        model: Optional[str] = None,
    ) -> AgentProtocol:
        """Select an agent based on configuration or explicit parameters.

        Args:
            backend: Optional backend name (codex, vibe, etc.)
            profile: Optional profile name
            model: Optional model name

        Returns:
            AgentProtocol instance configured with the selected parameters
        """
        # Get configuration if no explicit parameters provided
        if backend is None or profile is None or model is None:
            settings = self.config_service.get_config("agents", AgentSettings)

            # Use config values for None parameters
            if backend is None:
                backend = settings.backend
            if profile is None:
                profile = settings.profile
            if model is None:
                model = settings.model

        # Create and return the appropriate agent with configuration
        return self._create_agent(backend, profile, model)

    def _create_agent(self, backend: str, profile: str, model: str) -> AgentProtocol:
        """Create an agent instance based on backend type with configuration."""
        backends = {
            "codex": CodexAdapter,
            "vibe": VibeAdapter,
        }
        adapter_cls = backends.get(backend)
        if adapter_cls is None:
            raise ValueError(f"Unknown backend: {backend}")
        return adapter_cls(profile=profile, model=model)


def get_agent_service() -> SelectAgentService:
    """Factory function to get the agent selection service."""
    return SelectAgentService()
