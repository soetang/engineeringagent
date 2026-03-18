"""Tests for SelectAgentService."""

import tempfile
import os
from developer.agents.select_agent_service import SelectAgentService
from developer.agents.adapters.codex_adapter import CodexAdapter
from developer.agents.adapters.vibe_adapter import VibeAdapter


def test_select_agent_service_with_config():
    """Test SelectAgentService using configuration."""
    # Create temporary TOML file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
        f.write("""
[agents]
backend = "codex"
profile = "test_profile"
model = "gpt-4"
""")
        temp_file = f.name

    try:
        # Create service with custom config file
        service = SelectAgentService()
        service.config_service._config_file = temp_file

        # Test selecting agent with no parameters (should use config)
        agent = service.select_agent()
        assert isinstance(agent, CodexAdapter)
        # With constructor-based config, agents now store profile/model
        assert agent.profile == "test_profile"
        assert agent.model == "gpt-4"

    finally:
        os.unlink(temp_file)


def test_select_agent_service_with_explicit_params():
    """Test SelectAgentService with explicit parameters."""
    service = SelectAgentService()

    # Test with explicit backend
    agent = service.select_agent(backend="vibe", profile="custom", model="gpt-4-turbo")
    assert isinstance(agent, VibeAdapter)
    # With constructor-based config, agents now store profile/model
    assert agent.profile == "custom"
    assert agent.model == "gpt-4-turbo"


def test_select_agent_service_mixed_params():
    """Test SelectAgentService with mix of config and explicit parameters."""
    # Create temporary TOML file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
        f.write("""
[agents]
backend = "codex"
profile = "config_profile"
model = "config_model"
""")
        temp_file = f.name

    try:
        service = SelectAgentService()
        service.config_service._config_file = temp_file

        # Test with explicit backend but config profile/model
        agent = service.select_agent(backend="vibe")
        assert isinstance(agent, VibeAdapter)
        # With constructor-based config, agents now store profile/model from config
        assert agent.profile == "config_profile"
        assert agent.model == "config_model"

        # Test with explicit profile but config backend/model
        agent = service.select_agent(profile="custom_profile")
        assert isinstance(agent, CodexAdapter)
        # With constructor-based config, agents now store profile/model
        assert agent.profile == "custom_profile"
        assert agent.model == "config_model"

    finally:
        os.unlink(temp_file)


def test_select_agent_service_unknown_backend():
    """Test SelectAgentService with unknown backend."""
    service = SelectAgentService()

    try:
        service.select_agent(backend="unknown_backend")
        assert False, "Expected ValueError for unknown backend"
    except ValueError as e:
        assert "Unknown backend" in str(e)


def test_select_agent_service_factory_function():
    """Test the factory function for getting agent service."""
    from developer.agents.select_agent_service import get_agent_service

    service = get_agent_service()
    assert isinstance(service, SelectAgentService)

    # Note: get_agent_service() creates new instances, not singleton
    # This is fine for our use case
    service2 = get_agent_service()
    assert isinstance(service2, SelectAgentService)


def test_select_agent_service_with_path():
    """Test SelectAgentService passes path to the selected agent."""
    service = SelectAgentService()

    agent = service.select_agent(backend="vibe", path="/tmp")

    assert isinstance(agent, VibeAdapter)
    assert agent.path == "/tmp"
