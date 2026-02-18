from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from engineeringagent import cli as cli_module


def test_cli_checks_catalog_writes_markdown(tmp_path: Path) -> None:
    manifest_path = tmp_path / "harness" / "fitness-functions" / "rules.yaml"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        "\n".join(
            [
                'contract_version: "1.0"',
                "rules:",
                "  - rule_id: custom.shell-contract",
                "    name: Custom shell contract",
                "    summary: Verify custom command envelope format.",
                "    rationale: Keeps custom adapters interoperable.",
                "    remediation: Update custom command output to the contract.",
                "    scope: harness/fitness-functions",
                "    severity: warning",
                "    side_effect_free: true",
                "    adapter: command",
                "    command:",
                "      - python",
                "      - -c",
                '      - print(\'{"contract_version":"1.0","rule_id":"custom.shell-contract","status":"pass","severity":"warning","summary":"ok","violations":[]}\')',
            ]
        ),
        encoding="utf-8",
    )

    output_path = tmp_path / "docs" / "fitness-functions" / "rules.md"
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

    markdown = output_path.read_text(encoding="utf-8")
    assert markdown.endswith("\n")
