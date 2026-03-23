"""Tests for the init CLI command."""

from pathlib import Path

import tomllib
from typer.testing import CliRunner

from developer.presentation.cli import app


def test_init_scaffolds_minimal_repository() -> None:
    """Init should create the starter config, prompts, checks, and docs."""
    runner = CliRunner()

    with runner.isolated_filesystem():
        result = runner.invoke(app, ["init"], input="\ny\ny\n")

        assert result.exit_code == 0
        assert Path("engineeringagent.toml").exists()
        assert Path("AGENTS.md").exists()
        assert Path("harness/checks.yaml").exists()
        assert Path("harness/quality/commands.yaml").exists()
        assert Path("harness/prompts/implementation_prompt.md").exists()
        assert Path("harness/prompts/commit_message_prompt.md").exists()
        assert Path("harness/prompts/pull_request_prompt.md").exists()
        assert Path("docs/plans/example-plan.md").exists()

        config = tomllib.loads(Path("engineeringagent.toml").read_text())
        assert config["quality"]["checks_path"] == "harness/checks.yaml"
        assert (
            config["prompts"]["implementation_prompt_path"]
            == "harness/prompts/implementation_prompt.md"
        )
        assert "uv run --active developer init" in Path("AGENTS.md").read_text()


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
        assert config["quality"]["checks_path"] == "bootstrap/checks.yaml"
        assert Path("bootstrap/prompts/implementation_prompt.md").exists()
        assert not Path("AGENTS.md").exists()


def test_init_skips_existing_files_without_silent_overwrite() -> None:
    """Init should report skipped scaffold files when they already exist."""
    runner = CliRunner()

    with runner.isolated_filesystem():
        existing_prompt = Path("harness/prompts/implementation_prompt.md")
        existing_prompt.parent.mkdir(parents=True, exist_ok=True)
        existing_prompt.write_text("existing prompt")

        result = runner.invoke(app, ["init"], input="\nn\nn\n")

        assert result.exit_code == 0
        assert existing_prompt.read_text() == "existing prompt"
        assert "SKIPPED" in result.output
        assert "already exists" in result.output


def test_init_appends_guidance_to_existing_agents_file_once() -> None:
    """Init should append the developer guidance block without duplicating it."""
    runner = CliRunner()

    with runner.isolated_filesystem():
        Path("AGENTS.md").write_text("# Existing instructions\n")

        first = runner.invoke(app, ["init"], input="\nn\ny\n")
        second = runner.invoke(app, ["init"], input="\nn\ny\n")

        assert first.exit_code == 0
        assert second.exit_code == 0

        agents_text = Path("AGENTS.md").read_text()
        assert agents_text.count("<!-- developer:init:start -->") == 1
        assert "uv run --active developer schema plan" in agents_text


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


def test_generated_guidance_uses_active_uv_invocation() -> None:
    """The scaffolded guidance should consistently target the active uv environment."""
    runner = CliRunner()

    with runner.isolated_filesystem():
        result = runner.invoke(app, ["init"], input="\ny\ny\n")

        assert result.exit_code == 0

        agents_text = Path("AGENTS.md").read_text()
        prompt_text = Path("harness/prompts/implementation_prompt.md").read_text()
        quality_text = Path("harness/quality/commands.yaml").read_text()

        assert "uv run --active developer init" in agents_text
        assert "uv run developer" not in agents_text
        assert "uv run --active developer validate-plan" in prompt_text
        assert 'command: ["uv", "run", "--active", "ruff", "check"]' in quality_text
        assert 'command: ["uv", "run", "--active", "pyrefly", "check"]' in quality_text
        assert 'command: ["uv", "run", "--active", "pytest"]' in quality_text
