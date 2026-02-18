from __future__ import annotations

import json
from pathlib import Path
from typer.testing import CliRunner

from engineeringagent import cli as cli_module
from engineeringagent.checks import render_fitness_catalog


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
            "checks",
            "catalog",
            "--format",
            "markdown",
            "--output",
            str(output_path.relative_to(tmp_path)),
        ],
    )

    assert result.exit_code == 0
    assert "checks catalog written:" in result.stdout
    assert output_path.exists()

    markdown = output_path.read_text(encoding="utf-8")
    assert markdown.endswith("\n")


def test_fitness_catalog_json_generation(tmp_path: Path) -> None:
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

    payload = json.loads(
        render_fitness_catalog(
            tmp_path,
            manifest_path=manifest_path.relative_to(tmp_path),
            format="json",
        )
    )

    assert payload == [
        {
            "adapter": "command",
            "name": "Custom shell contract",
            "rationale": "Keeps custom adapters interoperable.",
            "remediation": "Update custom command output to the contract.",
            "rule_id": "custom.shell-contract",
            "scope": "harness/fitness-functions",
            "severity": "warning",
            "side_effect_free": True,
            "source": "custom",
            "summary": "Verify custom command envelope format.",
        }
    ]


def test_fitness_catalog_json_contract_is_sorted_and_complete(tmp_path: Path) -> None:
    manifest_path = tmp_path / "harness" / "fitness-functions" / "rules.yaml"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        "\n".join(
            [
                'contract_version: "1.0"',
                "rules:",
                "  - rule_id: custom.z-last",
                "    name: Custom z-last",
                "    summary: Custom command rule z-last.",
                "    rationale: Exercise contract fields.",
                "    remediation: Update custom rules manifest.",
                "    scope: docs",
                "    severity: warning",
                "    side_effect_free: true",
                "    adapter: command",
                "    command:",
                "      - python",
                "      - -c",
                "      - print('{}')",
                "  - rule_id: custom.a-first",
                "    name: Custom a-first",
                "    summary: Custom command rule a-first.",
                "    rationale: Exercise contract fields.",
                "    remediation: Update custom rules manifest.",
                "    scope: docs",
                "    severity: warning",
                "    side_effect_free: true",
                "    adapter: command",
                "    command:",
                "      - python",
                "      - -c",
                "      - print('{}')",
            ]
        ),
        encoding="utf-8",
    )

    payload = json.loads(
        render_fitness_catalog(
            tmp_path,
            manifest_path=manifest_path.relative_to(tmp_path),
            format="json",
        )
    )

    assert isinstance(payload, list)
    assert payload

    rule_ids = [entry["rule_id"] for entry in payload]
    assert rule_ids == sorted(rule_ids)

    required_keys = {
        "adapter",
        "name",
        "rationale",
        "remediation",
        "rule_id",
        "scope",
        "severity",
        "side_effect_free",
        "source",
        "summary",
    }
    for entry in payload:
        assert set(entry.keys()) == required_keys
