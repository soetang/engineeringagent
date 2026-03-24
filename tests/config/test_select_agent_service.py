"""Tests for SelectAgentBackendService."""

import pytest

from engineeringagent.agent_backends.adapters.codex_adapter import CodexAdapter
from engineeringagent.agent_backends.adapters.vibe_adapter import VibeAdapter
from engineeringagent.agent_backends.select_agent_backend_service import (
    SelectAgentBackendService,
    get_agent_backend_service,
)
from engineeringagent.config.service import ConfigService


def _config_service(tmp_path, config_text: str = "") -> ConfigService:
    """Create an isolated config service for backend selection tests."""
    config_file = tmp_path / "engineeringagent.toml"
    config_file.write_text(config_text, encoding="utf-8")
    return ConfigService(config_file=str(config_file))


def _agents_config(**settings: str) -> str:
    """Build a minimal `[agents]` config block for tests."""
    lines = ["[agents]"]
    lines.extend(f'{key} = "{value}"' for key, value in settings.items())
    return "\n".join(lines)


def test_select_agent_backend_service_with_codex_config(tmp_path):
    """Service should load Codex backend settings from config."""
    service = SelectAgentBackendService(
        config_service=_config_service(
            tmp_path,
            _agents_config(
                backend="codex",
                profile="test_profile",
                model="gpt-4",
            ),
        )
    )

    agent = service.select_agent()

    assert isinstance(agent, CodexAdapter)
    assert agent.profile == "test_profile"
    assert agent.model == "gpt-4"
    assert agent.path is None


def test_select_agent_backend_service_with_explicit_vibe_profile(tmp_path):
    """Vibe selection should use profile as the agent source."""
    service = SelectAgentBackendService(config_service=_config_service(tmp_path))

    agent = service.select_agent(backend="vibe", profile="testagent", path="/tmp")

    assert isinstance(agent, VibeAdapter)
    assert agent.profile == "testagent"
    assert agent.model is None
    assert agent.path == "/tmp"


def test_select_agent_backend_service_mixed_params(tmp_path):
    """Explicit overrides should merge with shared config defaults."""
    service = SelectAgentBackendService(
        config_service=_config_service(
            tmp_path,
            _agents_config(
                backend="codex",
                profile="config_profile",
                model="config_model",
            ),
        )
    )

    agent = service.select_agent(profile="custom_profile")

    assert isinstance(agent, CodexAdapter)
    assert agent.profile == "custom_profile"
    assert agent.model == "config_model"
    assert agent.path is None


def test_select_agent_backend_service_unknown_backend(tmp_path):
    """Unknown backends should fail clearly."""
    service = SelectAgentBackendService(config_service=_config_service(tmp_path))

    with pytest.raises(ValueError, match="Unknown backend: unknown_backend"):
        service.select_agent(backend="unknown_backend")


def test_select_agent_backend_service_factory_function():
    """Factory should create fresh backend selection service instances."""
    service = get_agent_backend_service()
    assert isinstance(service, SelectAgentBackendService)

    service2 = get_agent_backend_service()
    assert isinstance(service2, SelectAgentBackendService)


def test_select_agent_backend_service_rejects_vibe_model(tmp_path):
    """Vibe should reject raw model configuration."""
    service = SelectAgentBackendService(config_service=_config_service(tmp_path))

    with pytest.raises(
        ValueError,
        match="Vibe backend does not support `model`; use `profile`",
    ):
        service.select_agent(backend="vibe", model="gpt-4-turbo")


def test_select_agent_backend_service_rejects_vibe_profile_and_model(tmp_path):
    """Vibe should reject providing both profile and model."""
    service = SelectAgentBackendService(config_service=_config_service(tmp_path))

    with pytest.raises(
        ValueError,
        match="Received both `profile` and `model`",
    ):
        service.select_agent(
            backend="vibe",
            profile="testagent",
            model="gpt-4-turbo",
        )


def test_select_agent_backend_service_rejects_vibe_model_from_config(tmp_path):
    """Config-driven Vibe selection should also reject raw model usage."""
    service = SelectAgentBackendService(
        config_service=_config_service(
            tmp_path,
            _agents_config(backend="vibe", model="gpt-4-turbo"),
        )
    )

    with pytest.raises(
        ValueError,
        match="Vibe backend does not support `model`; use `profile`",
    ):
        service.select_agent()
