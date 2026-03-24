"""Tests for the init CLI command."""

from pathlib import Path

import tomllib
from typer.testing import CliRunner

from engineeringagent.presentation.cli import app
from engineeringagent.scaffolding.paths import (
    AGENTS_MD_START_MARKER,
    COMMIT_MESSAGE_PROMPT_NAME,
    DEFAULT_HARNESS_DIR,
    IMPLEMENTATION_PROMPT_NAME,
    PULL_REQUEST_PROMPT_NAME,
    QUALITY_COMMANDS_FILE_NAME,
    QUALITY_DIR,
    build_checks_path,
    build_prompt_path,
)


def test_init_scaffolds_minimal_repository() -> None:
    """Init should create the starter config, prompts, checks, and docs."""
    runner = CliRunner()

    with runner.isolated_filesystem():
        result = runner.invoke(app, ["init"], input="\ny\ny\n")

        assert result.exit_code == 0
        assert Path("engineeringagent.toml").exists()
        assert Path("AGENTS.md").exists()
        assert Path(build_checks_path(DEFAULT_HARNESS_DIR)).exists()
        assert Path(
            DEFAULT_HARNESS_DIR, QUALITY_DIR, QUALITY_COMMANDS_FILE_NAME
        ).exists()
        assert Path(
            build_prompt_path(DEFAULT_HARNESS_DIR, IMPLEMENTATION_PROMPT_NAME)
        ).exists()
        assert Path(
            build_prompt_path(DEFAULT_HARNESS_DIR, COMMIT_MESSAGE_PROMPT_NAME)
        ).exists()
        assert Path(
            build_prompt_path(DEFAULT_HARNESS_DIR, PULL_REQUEST_PROMPT_NAME)
        ).exists()
        assert Path("docs/plans/example-plan.md").exists()

        config = tomllib.loads(Path("engineeringagent.toml").read_text())
        assert config["quality"]["checks_path"] == build_checks_path(
            DEFAULT_HARNESS_DIR
        )
        assert config["prompts"]["implementation_prompt_path"] == build_prompt_path(
            DEFAULT_HARNESS_DIR, IMPLEMENTATION_PROMPT_NAME
        )
        assert AGENTS_MD_START_MARKER in Path("AGENTS.md").read_text()


def test_init_updates_existing_config_without_overwriting_existing_values() -> None:
    """Init should add missing sections while preserving existing config values."""
    runner = CliRunner()

    with runner.isolated_filesystem():
        Path("engineeringagent.toml").write_text(
            """[prompts]\nimplementation_prompt_path = "custom.md"\n"""
        )

        result = runner.invoke(app, ["init"], input="bootstrap\ny\nn\n")

        assert result.exit_code == 0
        config = tomllib.loads(Path("engineeringagent.toml").read_text())
        assert config["prompts"]["implementation_prompt_path"] == "custom.md"
        assert config["quality"]["checks_path"] == build_checks_path("bootstrap")
        assert Path(build_prompt_path("bootstrap", IMPLEMENTATION_PROMPT_NAME)).exists()
        assert not Path("AGENTS.md").exists()


def test_init_skips_existing_files_without_silent_overwrite() -> None:
    """Init should report skipped scaffold files when they already exist."""
    runner = CliRunner()

    with runner.isolated_filesystem():
        existing_prompt = Path(
            build_prompt_path(DEFAULT_HARNESS_DIR, IMPLEMENTATION_PROMPT_NAME)
        )
        existing_prompt.parent.mkdir(parents=True, exist_ok=True)
        existing_prompt.write_text("existing prompt")

        result = runner.invoke(app, ["init"], input="\nn\nn\n")

        assert result.exit_code == 0
        assert existing_prompt.read_text() == "existing prompt"
        assert "SKIPPED" in result.output
        assert "already exists" in result.output


def test_init_appends_guidance_to_existing_agents_file_once() -> None:
    """Init should append the engineeringagent guidance block without duplicating it."""
    runner = CliRunner()

    with runner.isolated_filesystem():
        Path("AGENTS.md").write_text("# Existing instructions\n")

        first = runner.invoke(app, ["init"], input="\nn\ny\n")
        second = runner.invoke(app, ["init"], input="\nn\ny\n")

        assert first.exit_code == 0
        assert second.exit_code == 0

        agents_text = Path("AGENTS.md").read_text()
        assert agents_text.count(AGENTS_MD_START_MARKER) == 1
        assert "## Engineeringagent CLI" in agents_text


def test_generated_example_plan_passes_validate_plan() -> None:
    """The scaffolded example plan should validate as a task-plan input."""
    runner = CliRunner()

    with runner.isolated_filesystem():
        init_result = runner.invoke(app, ["init"], input="\nn\nn\n")
        validate_result = runner.invoke(
            app, ["validate-plan", "docs/plans/example-plan.md"]
        )

        assert init_result.exit_code == 0
        assert validate_result.exit_code == 0
        assert "Plan validation successful" in validate_result.output


def test_generated_scaffold_contains_expected_quality_commands() -> None:
    """The scaffolded quality file should contain the starter command checks."""
    runner = CliRunner()

    with runner.isolated_filesystem():
        result = runner.invoke(app, ["init"], input="\ny\ny\n")

        assert result.exit_code == 0

        quality_text = Path(
            DEFAULT_HARNESS_DIR, QUALITY_DIR, QUALITY_COMMANDS_FILE_NAME
        ).read_text()

        assert 'check_type: "command"' in quality_text
        assert quality_text.count('check_type: "command"') == 1
        assert 'command: ["pytest"]' in quality_text
