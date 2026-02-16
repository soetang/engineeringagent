from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from engineeringagent import cli as cli_module


def test_cli_checks_run_requires_checks_yaml(tmp_path: Path) -> None:
    runner = CliRunner(mix_stderr=False)
    result = runner.invoke(
        cli_module.build_typer_app(),
        ["--project-root", str(tmp_path), "checks", "run"],
    )

    assert result.exit_code == 1
    assert "missing harness/checks.yaml" in result.stdout


def test_cli_checks_run_executes_command_check(tmp_path: Path) -> None:
    harness_dir = tmp_path / "harness"
    harness_dir.mkdir(parents=True, exist_ok=True)
    (harness_dir / "checks.yaml").write_text(
        "\n".join(
            [
                'contract_version: "1.0"',
                "checks:",
                "  smoke:",
                "    type: command",
                '    command: "python -c \\"print(\'ok\')\\""',
                "",
            ]
        ),
        encoding="utf-8",
    )

    runner = CliRunner(mix_stderr=False)
    result = runner.invoke(
        cli_module.build_typer_app(),
        ["--project-root", str(tmp_path), "checks", "run", "--phase", "iteration_end"],
    )

    assert result.exit_code == 0
    assert "[check:smoke]" in result.stdout
    assert "checks run: ok" in result.stdout
