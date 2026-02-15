from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from engineeringagent import cli as cli_module


def test_fitness_catalog_markdown_generation(tmp_path: Path) -> None:
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
            "fitness",
            "catalog",
            "--format",
            "markdown",
            "--output",
            str(output_path.relative_to(tmp_path)),
        ],
    )

    markdown = output_path.read_text(encoding="utf-8")

    assert result.exit_code == 0
    assert "fitness catalog written:" in result.stdout
    assert "`custom.shell-contract`" in markdown
    assert "`architecture.dep-directionality`" not in markdown
    assert "`architecture.loop-subprocess-boundary`" not in markdown
    assert "Rationale: Keeps custom adapters interoperable." in markdown
    assert "Remediation: Update custom command output to the contract." in markdown


def test_main_uses_typer_fitness_tree_without_legacy_forward(monkeypatch: Any) -> None:
    captured: dict[str, Any] = {}

    def _fake_cmd_fitness_catalog(args: Any) -> int:
        captured["project_root"] = args.project_root
        captured["manifest_path"] = args.manifest_path
        captured["format"] = args.format
        captured["output"] = args.output
        return 3

    assert not hasattr(cli_module, "_run_legacy_cli_command")
    monkeypatch.setattr(
        cli_module,
        "cmd_fitness_catalog",
        _fake_cmd_fitness_catalog,
    )

    with pytest.raises(SystemExit) as exc_info:
        cli_module.main(
            [
                "--project-root",
                "repo",
                "fitness",
                "catalog",
                "--manifest-path",
                "harness/fitness-functions/rules.yaml",
                "--format",
                "json",
                "--output",
                "docs/fitness-functions/rules.md",
            ]
        )

    assert exc_info.value.code == 3
    assert captured == {
        "project_root": "repo",
        "manifest_path": "harness/fitness-functions/rules.yaml",
        "format": "json",
        "output": "docs/fitness-functions/rules.md",
    }
