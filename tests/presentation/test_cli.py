"""Test the CLI check command with real harness files."""

from pathlib import Path

from typer.testing import CliRunner

from developer.presentation.cli import app


def test_cli_check_with_valid_checks_yaml():
    """Test the CLI check command with a valid checks.yaml file."""
    runner = CliRunner()

    with runner.isolated_filesystem():
        # Create harness directory
        harness_dir = Path(".") / "harness"
        harness_dir.mkdir()

        # Create config file with quality settings
        config_file = Path(".") / "engineeringagent.toml"
        config_file.write_text(f"""[quality]
checks_path = "{harness_dir / "checks.yaml"}"
""")

        # Create a valid checks.yaml file in harness directory
        checks_yaml = harness_dir / "checks.yaml"
        checks_yaml.write_text("""checks:
  - name: "Test Check"
    filepath: "test.yaml"
""")

        # Create a valid quality spec file in harness directory
        test_yaml = harness_dir / "test.yaml"
        test_yaml.write_text("""# Test quality spec
name: "test"
filepath: ""
checks:
  - check_type: "command"
    command: ["echo", "test"]
""")

        # Run the CLI check command
        result = runner.invoke(app, ["check", "run"])

        # Should succeed
        assert result.exit_code == 0
        assert "Running quality checks..." in result.output
        assert "✓ All checks passed!" in result.output
        assert "Executed 1 checks: 1 passed, 0 failed" in result.output


def test_cli_check_without_checks_yaml():
    """Test the CLI check command without a checks.yaml file - should fail."""
    runner = CliRunner()

    with runner.isolated_filesystem():
        # Create config file but no checks.yaml file
        config_file = Path(".") / "engineeringagent.toml"
        config_file.write_text("""[quality]
checks_path = "harness/checks.yaml"
""")

        # Run the CLI check command (no harness directory)
        result = runner.invoke(app, ["check", "run"])

        # Should fail
        assert result.exit_code == 1
        assert "Error executing checks" in result.output
        assert "No such file or directory" in result.output


def test_cli_check_help():
    """Test the CLI check command help."""
    runner = CliRunner()
    result = runner.invoke(app, ["check", "--help"])

    assert result.exit_code == 0
    # Validate that subcommands are listed in help output
    assert "run" in result.output
    assert "validate" in result.output
