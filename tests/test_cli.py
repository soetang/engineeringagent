from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from engineeringagent.cli import build_parser


def test_fitness_subcommands(tmp_path: Path, capsys: Any) -> None:
    src_dir = tmp_path / "src" / "engineeringagent"
    src_dir.mkdir(parents=True, exist_ok=True)
    for module_name in ["specs", "validator", "gates", "loop", "cli"]:
        (src_dir / f"{module_name}.py").write_text("\n", encoding="utf-8")

    parser = build_parser()

    args = parser.parse_args(
        [
            "--project-root",
            str(tmp_path),
            "fitness",
            "list",
            "--format",
            "json",
        ]
    )
    list_code = args.func(args)
    list_output = capsys.readouterr().out
    list_payload = json.loads(list_output)

    assert list_code == 0
    assert [entry["rule_id"] for entry in list_payload] == [
        "architecture.dep-directionality",
        "architecture.loop-subprocess-boundary",
    ]

    args = parser.parse_args(
        [
            "--project-root",
            str(tmp_path),
            "fitness",
            "run",
            "--jobs",
            "2",
            "--format",
            "json",
        ]
    )
    run_code = args.func(args)
    run_output = capsys.readouterr().out
    run_payload = json.loads(run_output)

    assert run_code == 0
    assert run_payload["failed"] is False
    assert [result["rule_id"] for result in run_payload["results"]] == [
        "architecture.dep-directionality",
        "architecture.loop-subprocess-boundary",
    ]


def test_validate_fails_on_agents_docs_map_errors(tmp_path: Path, capsys: Any) -> None:
    (tmp_path / "AGENTS.md").write_text(
        "\n".join(
            [
                "# AGENTS.md",
                "",
                "## 5) Documentation Layout Reference",
                "- `docs/missing.md`",
                "",
                "## 6) First-Window Boot Sequence",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    parser = build_parser()
    args = parser.parse_args(["--project-root", str(tmp_path), "validate"])
    code = args.func(args)
    output = capsys.readouterr().out

    assert code == 1
    assert "AGENTS.md:4: docs-map path does not exist: docs/missing.md" in output
