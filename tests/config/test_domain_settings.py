"""Tests for domain settings models."""

import pytest

from developer.quality.settings import QualitySettings
from developer.agents.settings import AgentSettings
from developer.prompts.settings import OrchestratorPromptSettings


def test_quality_settings_defaults():
    """Test QualitySettings default values."""
    settings = QualitySettings()
    assert settings.checks_path == "checks.yaml"


def test_quality_settings_custom_values():
    """Test QualitySettings with custom values."""
    settings = QualitySettings(checks_path=".developer/quality/checks.yaml")
    assert settings.checks_path == ".developer/quality/checks.yaml"


def test_quality_settings_extra_forbid():
    """Test QualitySettings extra fields are forbidden."""
    with pytest.raises(Exception, match="(?i)extra|forbid"):
        QualitySettings.model_validate(
            {"checks_path": "test.yaml", "extra_field": "should_fail"}
        )


def test_agent_settings_defaults():
    """Test AgentSettings default values."""
    settings = AgentSettings()
    assert settings.backend == "codex"
    assert settings.profile == "default"
    assert settings.model == "gpt-4"


def test_agent_settings_custom_values():
    """Test AgentSettings with custom values."""
    settings = AgentSettings(backend="vibe", profile="production", model="gpt-4-turbo")
    assert settings.backend == "vibe"
    assert settings.profile == "production"
    assert settings.model == "gpt-4-turbo"


def test_agent_settings_extra_forbid():
    """Test AgentSettings extra fields are forbidden."""
    with pytest.raises(Exception, match="(?i)extra|forbid"):
        AgentSettings.model_validate({"backend": "test", "extra_field": "should_fail"})


def test_settings_validation():
    """Test settings validation."""
    # Test invalid types
    with pytest.raises(Exception, match="string|type"):
        QualitySettings.model_validate({"checks_path": 123})  # Should be string


def test_orchestrator_prompt_settings_defaults():
    """Test default orchestrator prompt settings."""
    settings = OrchestratorPromptSettings()
    assert settings.implementation_prompt_path == "prompts/implementation_prompt.md"


def test_orchestrator_prompt_settings_custom_values():
    """Test custom orchestrator prompt path values."""
    settings = OrchestratorPromptSettings(
        implementation_prompt_path=".custom/path/implementation_prompt.md"
    )
    assert (
        settings.implementation_prompt_path == ".custom/path/implementation_prompt.md"
    )


def test_orchestrator_prompt_settings_extra_forbid():
    """Test extra fields are forbidden for orchestrator prompt settings."""
    with pytest.raises(Exception, match="(?i)extra|forbid"):
        OrchestratorPromptSettings.model_validate({"extra_field": "should_fail"})


def test_orchestrator_prompt_settings_loaded_from_config(tmp_path):
    """ConfigService should load orchestrator settings from the configured section."""
    from developer.config.service import ConfigService

    config_file = tmp_path / "engineeringagent.toml"
    config_file.write_text(
        '[orchestrator]\nimplementation_prompt_path = "custom/prompt.md"\n'
    )

    service = ConfigService(config_file=str(config_file))
    settings = service.get_config("orchestrator", OrchestratorPromptSettings)

    assert settings.implementation_prompt_path == "custom/prompt.md"
