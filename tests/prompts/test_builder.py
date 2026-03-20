"""Tests for orchestrator prompt template rendering."""

from pathlib import Path

import pytest

from developer.config.service import ConfigService
from developer.prompts.builder import OrchestratorPromptBuilder
from developer.prompts.errors import (
    PromptTemplateMissingError,
    PromptTemplateSyntaxError,
)


def _write_config_with_prompt_path(
    config_path: Path,
    prompt_path: str | Path,
    section: str = "prompts",
) -> None:
    config_path.write_text(
        f'[{section}]\nimplementation_prompt_path = "{prompt_path}"\n',
        encoding="utf-8",
    )


def test_render_hides_feedback_when_none(tmp_path) -> None:
    """Template feedback block should not render when feedback is None."""
    prompt_file = tmp_path / "implementation_prompt.md"
    prompt_file.write_text(
        "Intro\n{% if feedback %}feedback: {{ feedback }}{% endif %}\n",
        encoding="utf-8",
    )
    config_file = tmp_path / "engineeringagent.toml"
    _write_config_with_prompt_path(config_file, prompt_file)

    builder = OrchestratorPromptBuilder(ConfigService(config_file=config_file))
    rendered = builder.build({"feedback": None})

    assert rendered == "Intro\n"


def test_render_feedback_only(tmp_path) -> None:
    """Template should include rendered feedback text."""
    prompt_file = tmp_path / "implementation_prompt.md"
    prompt_file.write_text("Feedback: {{ feedback }}", encoding="utf-8")
    config_file = tmp_path / "engineeringagent.toml"
    _write_config_with_prompt_path(config_file, prompt_file)

    builder = OrchestratorPromptBuilder(ConfigService(config_file=config_file))
    rendered = builder.build({"feedback": "address this"})

    assert rendered == "Feedback: address this"


def test_render_injects_additional_context_values(tmp_path) -> None:
    """Template rendering should include values from additional context keys."""
    prompt_file = tmp_path / "implementation_prompt.md"
    prompt_file.write_text(
        "Task: {{ task }} | Feedback: {{ feedback }}", encoding="utf-8"
    )
    config_file = tmp_path / "engineeringagent.toml"
    _write_config_with_prompt_path(config_file, prompt_file)

    builder = OrchestratorPromptBuilder(ConfigService(config_file=config_file))
    rendered = builder.build({"task": "ship it", "feedback": "fine"})

    assert rendered == "Task: ship it | Feedback: fine"


def test_render_raises_on_invalid_template_syntax(tmp_path) -> None:
    """Malformed templates should raise a deterministic domain error."""
    prompt_file = tmp_path / "implementation_prompt.md"
    prompt_file.write_text("{% if feedback %}{{ feedback }}", encoding="utf-8")
    config_file = tmp_path / "engineeringagent.toml"
    _write_config_with_prompt_path(config_file, prompt_file)

    builder = OrchestratorPromptBuilder(ConfigService(config_file=config_file))

    with pytest.raises(
        PromptTemplateSyntaxError, match="Failed to render prompt template"
    ):
        builder.build({"feedback": "oops"})


def test_render_raises_on_missing_prompt_file(tmp_path) -> None:
    """Missing configured prompt files should fail with a clear error."""
    missing_prompt = tmp_path / "does_not_exist.md"
    config_file = tmp_path / "engineeringagent.toml"
    _write_config_with_prompt_path(config_file, missing_prompt)

    builder = OrchestratorPromptBuilder(ConfigService(config_file=config_file))

    with pytest.raises(PromptTemplateMissingError, match="Prompt template not found"):
        builder.build({"feedback": "still needed"})


def test_legacy_orchestrator_prompt_section_still_works(tmp_path) -> None:
    """Prompt builder should fall back to the legacy orchestrator section."""
    prompt_file = tmp_path / "implementation_prompt.md"
    prompt_file.write_text("Legacy: {{ feedback }}", encoding="utf-8")
    config_file = tmp_path / "engineeringagent.toml"
    _write_config_with_prompt_path(config_file, prompt_file, section="orchestrator")

    builder = OrchestratorPromptBuilder(ConfigService(config_file=config_file))

    assert builder.build({"feedback": "ok"}) == "Legacy: ok"
