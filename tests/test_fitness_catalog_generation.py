from __future__ import annotations

from pathlib import Path
from typing import Any

from engineeringagent.cli import build_parser


def test_fitness_catalog_markdown_generation(tmp_path: Path, capsys: Any) -> None:
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
    parser = build_parser()
    args = parser.parse_args(
        [
            "--project-root",
            str(tmp_path),
            "fitness",
            "catalog",
            "--format",
            "markdown",
            "--output",
            str(output_path.relative_to(tmp_path)),
        ]
    )

    exit_code = args.func(args)
    output = capsys.readouterr().out
    markdown = output_path.read_text(encoding="utf-8")

    assert exit_code == 0
    assert "fitness catalog written:" in output
    assert "`architecture.dep-directionality`" in markdown
    assert "`architecture.loop-subprocess-boundary`" in markdown
    assert "`custom.shell-contract`" in markdown
    assert "Rationale: Keeps custom adapters interoperable." in markdown
    assert "Remediation: Update custom command output to the contract." in markdown
