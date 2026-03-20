"""Tests for domain settings models."""

import pytest

from developer.agent_backends.settings import AgentBackendSettings
from developer.config.service import ConfigService
from developer.forge.settings import ForgeSettings
from developer.prompts.settings import OrchestratorPromptSettings
from developer.quality.settings import QualitySettings
from developer.version_control.settings import VersionControlSettings


def test_quality_settings_defaults() -> None:
    """Test QualitySettings default values."""
    settings = QualitySettings()
    assert settings.checks_path == "checks.yaml"


def test_quality_settings_custom_values() -> None:
    """Test QualitySettings with custom values."""
    settings = QualitySettings(checks_path=".developer/quality/checks.yaml")
    assert settings.checks_path == ".developer/quality/checks.yaml"


def test_quality_settings_extra_forbid() -> None:
    """Test QualitySettings extra fields are forbidden."""
    with pytest.raises(Exception, match="(?i)extra|forbid"):
        QualitySettings.model_validate(
            {"checks_path": "test.yaml", "extra_field": "should_fail"}
        )


def test_agent_backend_settings_defaults() -> None:
    """Test AgentBackendSettings default values."""
    settings = AgentBackendSettings()
    assert settings.backend == "codex"
    assert settings.profile is None
    assert settings.model is None


def test_agent_backend_settings_custom_values() -> None:
    """Test AgentBackendSettings with custom values."""
    settings = AgentBackendSettings(
        backend="codex",
        profile="implementation",
        model="gpt-4-turbo",
    )
    assert settings.backend == "codex"
    assert settings.profile == "implementation"
    assert settings.model == "gpt-4-turbo"


def test_agent_backend_settings_accepts_vibe_profile_without_model() -> None:
    """Vibe configuration should use profile for agent selection semantics."""
    settings = AgentBackendSettings(backend="vibe", profile="testagent")

    assert settings.backend == "vibe"
    assert settings.profile == "testagent"
    assert settings.model is None


def test_agent_backend_settings_extra_forbid() -> None:
    """Test AgentBackendSettings extra fields are forbidden."""
    with pytest.raises(Exception, match="(?i)extra|forbid"):
        AgentBackendSettings.model_validate(
            {"backend": "test", "extra_field": "should_fail"}
        )


def test_settings_validation() -> None:
    """Test settings validation."""
    with pytest.raises(Exception, match="string|type"):
        QualitySettings.model_validate({"checks_path": 123})


def test_orchestrator_prompt_settings_defaults() -> None:
    """Test default orchestrator prompt settings."""
    settings = OrchestratorPromptSettings()
    assert settings.implementation_prompt_path == "harness/implementation_prompt.md"
    assert settings.commit_prompt_path == "harness/prompts/commit_message_prompt.md"
    assert settings.pull_request_prompt_path == "harness/prompts/pull_request_prompt.md"


def test_orchestrator_prompt_settings_custom_values() -> None:
    """Test custom prompt path values."""
    settings = OrchestratorPromptSettings(
        implementation_prompt_path=".custom/path/implementation_prompt.md",
        commit_prompt_path=".custom/path/commit.md",
        pull_request_prompt_path=".custom/path/pr.md",
    )
    assert (
        settings.implementation_prompt_path == ".custom/path/implementation_prompt.md"
    )
    assert settings.commit_prompt_path == ".custom/path/commit.md"
    assert settings.pull_request_prompt_path == ".custom/path/pr.md"


def test_orchestrator_prompt_settings_extra_forbid() -> None:
    """Test extra fields are forbidden for prompt settings."""
    with pytest.raises(Exception, match="(?i)extra|forbid"):
        OrchestratorPromptSettings.model_validate({"extra_field": "should_fail"})


def test_orchestrator_prompt_settings_loaded_from_new_config_section(tmp_path) -> None:
    """ConfigService should load prompt settings from the shared prompts section."""
    config_file = tmp_path / "engineeringagent.toml"
    config_file.write_text(
        '[prompts]\nimplementation_prompt_path = "custom/prompt.md"\n',
        encoding="utf-8",
    )

    service = ConfigService(config_file=str(config_file))
    settings = service.get_config("prompts", OrchestratorPromptSettings)

    assert settings.implementation_prompt_path == "custom/prompt.md"


def test_version_control_settings_defaults() -> None:
    """Version control settings should default to disabled git integration."""
    settings = VersionControlSettings()

    assert settings.enabled is False
    assert settings.provider == "git"
    assert settings.author_name is None
    assert settings.author_email is None


def test_forge_settings_defaults() -> None:
    """Forge settings should default to disabled GitHub publication."""
    settings = ForgeSettings()

    assert settings.enabled is False
    assert settings.provider == "github"
