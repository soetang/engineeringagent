"""Agent backend selection service using configuration or explicit parameters."""

from dataclasses import dataclass

from engineeringagent.config.service import ConfigService
from engineeringagent.agent_backends.adapters.codex_adapter import CodexAdapter
from engineeringagent.agent_backends.adapters.vibe_adapter import VibeAdapter
from engineeringagent.agent_backends.protocol import AgentBackendProtocol
from engineeringagent.agent_backends.settings import AgentBackendSettings

_BACKEND_ADAPTERS = {
    "codex": CodexAdapter,
    "vibe": VibeAdapter,
}

_VIBE_MODEL_ERROR = (
    "Vibe backend does not support `model`; use `profile` to select a Vibe agent."
)


@dataclass(frozen=True)
class _NormalizedAgentBackendSelection:
    """Normalized backend selection values after config resolution."""

    backend: str
    profile: str | None
    model: str | None
    path: str | None


class SelectAgentBackendService:
    """Select an agent backend from shared settings and per-call overrides."""

    def __init__(self, config_service: ConfigService | None = None) -> None:
        """Initialize the backend selection service."""
        self.config_service = config_service or ConfigService()

    def select_agent(
        self,
        backend: str | None = None,
        profile: str | None = None,
        model: str | None = None,
        path: str | None = None,
    ) -> AgentBackendProtocol:
        """Select an agent backend from config and explicit overrides.

        Args:
            backend: Optional backend name (codex, vibe, etc.)
            profile: Optional backend preset, profile, or agent persona.
            model: Optional underlying LLM name.
            path: Optional execution working directory override.

        Returns:
            Agent backend instance configured with normalized semantics.

        Raises:
            ValueError: If the backend is unknown or the backend-specific
                configuration combination is invalid.
        """
        backend, profile, model = self._resolve_selection_inputs(
            backend=backend,
            profile=profile,
            model=model,
        )

        selection = self._normalize_selection(backend, profile, model, path)
        return self._create_agent(selection)

    def _resolve_selection_inputs(
        self,
        backend: str | None,
        profile: str | None,
        model: str | None,
    ) -> tuple[str, str | None, str | None]:
        """Resolve explicit inputs against persisted backend settings."""
        if backend is not None and profile is not None and model is not None:
            return backend, profile, model

        settings = self.config_service.get_config("agents", AgentBackendSettings)
        resolved_backend = settings.backend if backend is None else backend
        resolved_profile = settings.profile if profile is None else profile
        resolved_model = settings.model if model is None else model

        if resolved_backend is None:
            raise ValueError("Agent backend must be configured")

        return resolved_backend, resolved_profile, resolved_model

    def _normalize_selection(
        self,
        backend: str,
        profile: str | None,
        model: str | None,
        path: str | None,
    ) -> _NormalizedAgentBackendSelection:
        """Normalize shared settings into backend-specific construction inputs."""
        if backend == "vibe":
            self._validate_vibe_selection(profile=profile, model=model)
            model = None
        elif backend != "codex":
            raise ValueError(f"Unknown backend: {backend}")

        return _NormalizedAgentBackendSelection(
            backend=backend,
            profile=profile,
            model=model,
            path=path,
        )

    def _validate_vibe_selection(
        self,
        profile: str | None,
        model: str | None,
    ) -> None:
        """Reject invalid Vibe combinations under the shared backend contract."""
        if model is None:
            return

        if profile is not None:
            raise ValueError(
                f"{_VIBE_MODEL_ERROR} Received both `profile` and `model`."
            )

        raise ValueError(_VIBE_MODEL_ERROR)

    def _create_agent(
        self,
        selection: _NormalizedAgentBackendSelection,
    ) -> AgentBackendProtocol:
        """Create an agent backend instance from normalized selection values."""
        adapter_cls = _BACKEND_ADAPTERS.get(selection.backend)
        if adapter_cls is None:
            raise ValueError(f"Unknown backend: {selection.backend}")
        return adapter_cls(
            profile=selection.profile,
            model=selection.model,
            path=selection.path,
        )


def get_agent_backend_service() -> SelectAgentBackendService:
    """Factory function to get the agent backend selection service."""
    return SelectAgentBackendService()
