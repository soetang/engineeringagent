from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from engineeringagent.presentation import cli as cli_module
from tests.helpers.fitness_manifest import write_shell_contract_manifest


def test_cli_checks_catalog_writes_markdown(tmp_path: Path) -> None:
    manifest_path = write_shell_contract_manifest(tmp_path)

    output_path = tmp_path / "docs" / "fitness_functions" / "rules.md"
    runner = CliRunner(mix_stderr=False)
    result = runner.invoke(
        cli_module.build_typer_app(),
        [
            "--project-root",
            str(tmp_path),
            "checks",
            "catalog",
            "--manifest-path",
            str(manifest_path.relative_to(tmp_path)),
            "--format",
            "markdown",
            "--output",
            str(output_path.relative_to(tmp_path)),
        ],
    )

    assert result.exit_code == 0
    assert (
        f"checks catalog written: {output_path.relative_to(tmp_path)}" in result.stdout
    )
    assert output_path.exists()
