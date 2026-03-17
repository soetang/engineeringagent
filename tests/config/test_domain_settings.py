"""Tests for domain settings models."""

from developer.quality.settings import QualitySettings
from developer.agents.settings import AgentSettings


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
    try:
        QualitySettings(checks_path="test.yaml", extra_field="should_fail")
        assert False, "Expected validation error for extra field"
    except Exception as e:
        assert "extra" in str(e).lower() or "forbid" in str(e).lower()


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
    try:
        AgentSettings(backend="test", extra_field="should_fail")
        assert False, "Expected validation error for extra field"
    except Exception as e:
        assert "extra" in str(e).lower() or "forbid" in str(e).lower()


def test_settings_validation():
    """Test settings validation."""
    # Test invalid types
    try:
        QualitySettings(checks_path=123)  # Should be string
        assert False, "Expected validation error for wrong type"
    except Exception as e:
        assert "string" in str(e).lower() or "type" in str(e).lower()
