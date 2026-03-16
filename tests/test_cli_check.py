"""Test the CLI check command with real harness files."""

from typer.testing import CliRunner
from pathlib import Path
from developer.presentation.cli import app


def test_cli_check_with_valid_checks_yaml():
    """Test the CLI check command with a valid checks.yaml file."""
    runner = CliRunner()

    with runner.isolated_filesystem():
        # Create harness directory
        harness_dir = Path(".") / "harness"
        harness_dir.mkdir()

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
        assert "Running validation checks..." in result.output
        assert "Validation successful!" in result.output
        assert "All 1 check configurations are valid" in result.output


def test_cli_check_without_checks_yaml():
    """Test the CLI check command without a checks.yaml file - should fail."""
    runner = CliRunner()

    with runner.isolated_filesystem():
        # Run the CLI check command (no harness directory)
        result = runner.invoke(app, ["check", "run"])

        # Should fail
        assert result.exit_code == 1
        assert "Validation failed!" in result.output
        assert (
            "No such file or directory" in result.output
            or "checks.yaml" in result.output
        )


def test_cli_check_help():
    """Test the CLI check command help."""
    runner = CliRunner()
    result = runner.invoke(app, ["check", "--help"])

    assert result.exit_code == 0
    assert "Run validation checks using harness/checks.yaml" in result.output
