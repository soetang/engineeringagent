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
        assert "✗ Some checks failed!" not in result.output


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


def test_cli_check_phase_option_runs_selected_phase() -> None:
    """Pass only implementation checks when requested."""
    runner = CliRunner()

    with runner.isolated_filesystem():
        harness_dir = Path(".") / "harness"
        harness_dir.mkdir()

        config_file = Path(".") / "engineeringagent.toml"
        config_file.write_text(f"""[quality]
checks_path = "{harness_dir / "checks.yaml"}"
""")

        checks_yaml = harness_dir / "checks.yaml"
        checks_yaml.write_text("""checks:
  - name: "Test Check"
    filepath: "test.yaml"
""")

        test_yaml = harness_dir / "test.yaml"
        test_yaml.write_text("""name: "test"
filepath: ""
checks:
  - check_type: "command"
    phase: "ImplementationComplete"
    command: ["python", "-c", "import sys; sys.exit(1)"]
""")

        result = runner.invoke(
            app,
            [
                "check",
                "run",
                "--phase",
                "ImplementationComplete",
            ],
        )

        assert result.exit_code == 1
        assert "✗ Some checks failed!" in result.output
        assert "Command failed with return code 1" in result.output


def test_cli_check_default_phase_is_iteration() -> None:
    """Omitting --phase should run IterationComplete."""
    runner = CliRunner()

    with runner.isolated_filesystem():
        harness_dir = Path(".") / "harness"
        harness_dir.mkdir()

        config_file = Path(".") / "engineeringagent.toml"
        config_file.write_text(f"""[quality]
checks_path = "{harness_dir / "checks.yaml"}"
""")

        checks_yaml = harness_dir / "checks.yaml"
        checks_yaml.write_text("""checks:
  - name: "Test Check"
    filepath: "test.yaml"
""")

        test_yaml = harness_dir / "test.yaml"
        test_yaml.write_text("""name: "test"
filepath: ""
checks:
  - check_type: "command"
    command: ["echo", "ok"]
""")

        result = runner.invoke(app, ["check", "run"])

        assert result.exit_code == 0
        assert "✓ All checks passed!" in result.output


def test_cli_check_runs_all_checks_by_default() -> None:
    """Without an explicit failure-short-circuit option, all checks run."""
    runner = CliRunner()

    with runner.isolated_filesystem():
        harness_dir = Path(".") / "harness"
        harness_dir.mkdir()

        config_file = Path(".") / "engineeringagent.toml"
        config_file.write_text(f"""[quality]
checks_path = "{harness_dir / "checks.yaml"}"
""")

        checks_yaml = harness_dir / "checks.yaml"
        checks_yaml.write_text("""checks:
  - name: "Test Check"
    filepath: "test.yaml"
""")

        test_yaml = harness_dir / "test.yaml"
        test_yaml.write_text("""name: "test"
filepath: ""
checks:
  - check_type: "command"
    command: ["python", "-c", "import sys; sys.exit(1)"]
  - check_type: "command"
    command: ["python", "-c", "open('ran_second_command.txt', 'w').write('done')"]
""")

        result = runner.invoke(app, ["check", "run"])

        assert result.exit_code == 1
        assert "✗ Some checks failed!" in result.output
        assert Path("ran_second_command.txt").exists() is True
        assert "1." in result.output and "2." in result.output


def test_cli_check_displays_each_check_entry() -> None:
    """Check command should include individual check lines in output."""
    runner = CliRunner()

    with runner.isolated_filesystem():
        fictive_dir = Path(".") / "fictive_project"
        fictive_dir.mkdir()

        config_file = Path(".") / "engineeringagent.toml"
        config_file.write_text(f"""[quality]
checks_path = "{fictive_dir / "fictive_checks.yaml"}"
""")

        checks_yaml = fictive_dir / "fictive_checks.yaml"
        checks_yaml.write_text("""checks:
  - name: "Fictive Check"
    filepath: "fictive_suite.yaml"
""")

        test_yaml = fictive_dir / "fictive_suite.yaml"
        test_yaml.write_text("""name: "test"
filepath: ""
checks:
  - check_type: "command"
    command: ["echo", "check_one"]
""")

        result = runner.invoke(app, ["check", "run"])

    assert result.exit_code == 0
    assert "[command] echo check_one" in result.output
    assert "1. ✓" in result.output


def test_cli_check_help():
    """Test the CLI check command help."""
    runner = CliRunner()
    result = runner.invoke(app, ["check", "--help"])

    assert result.exit_code == 0
    # Validate that subcommands are listed in help output
    assert "run" in result.output
    assert "validate" in result.output
    assert "--stop-on-first-failure" not in result.output


def test_root_cli_help_lists_plan_commands() -> None:
    """The root CLI help should list the primary command surfaces."""
    runner = CliRunner()
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "check" in result.output
    assert "implement" in result.output
    assert "schema" in result.output
    assert "validate-plan" in result.output
