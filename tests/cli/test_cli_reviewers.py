from __future__ import annotations

from typer.testing import CliRunner

from engineeringagent import cli as cli_module


def test_cli_help_does_not_register_removed_gates_and_reviewers_apps() -> None:
    runner = CliRunner(mix_stderr=False)
    result = runner.invoke(cli_module.build_typer_app(), ["--help"])

    assert result.exit_code == 0
    # Typer renders registered subapps as command names in the help output.
    assert "\n  gates\n" not in result.stdout
    assert "\n  reviewers\n" not in result.stdout
