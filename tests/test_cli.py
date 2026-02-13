from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from engineeringagent.cli import build_parser
from engineeringagent.fitness.contracts import CONTRACT_VERSION


def _write_manifest(tmp_path: Path, rules: list[dict[str, object]]) -> None:
    manifest_path = tmp_path / "harness" / "fitness-functions" / "rules.yaml"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        yaml.safe_dump(
            {
                "contract_version": CONTRACT_VERSION,
                "rules": rules,
            },
            sort_keys=False,
            allow_unicode=False,
        ),
        encoding="utf-8",
    )


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
    assert list_payload == []

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
    assert run_payload["results"] == []


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


def test_fitness_run_json_includes_remediation_for_failures(
    tmp_path: Path,
    capsys: Any,
) -> None:
    src_dir = tmp_path / "src" / "engineeringagent"
    src_dir.mkdir(parents=True, exist_ok=True)
    for module_name in ["specs", "validator", "gates", "loop", "cli"]:
        (src_dir / f"{module_name}.py").write_text("\n", encoding="utf-8")

    (src_dir / "bad_subprocess.py").write_text(
        "import subprocess\nsubprocess.run(['git', 'status'], check=False)\n",
        encoding="utf-8",
    )
    _write_manifest(
        tmp_path,
        [{"builtin": "architecture.loop-subprocess-boundary"}],
    )

    parser = build_parser()
    args = parser.parse_args(
        [
            "--project-root",
            str(tmp_path),
            "fitness",
            "run",
            "--format",
            "json",
        ]
    )
    code = args.func(args)
    output = capsys.readouterr().out
    payload = json.loads(output)

    assert code == 1
    assert payload["failed"] is True
    assert payload["failed_rules"] == [
        {
            "rule_id": "architecture.loop-subprocess-boundary",
            "status": "fail",
            "remediation": "Move OpenCode command execution to engineeringagent.opencode.client and Git command execution to engineeringagent.git.client.",
        }
    ]


def test_fitness_run_executes_shell_command_rule(tmp_path: Path, capsys: Any) -> None:
    _write_manifest(
        tmp_path,
        [
            {
                "rule_id": "custom.shell-pass",
                "name": "Shell pass",
                "summary": "Passes from shell command adapter.",
                "rationale": "Confirms manifest-declared command rules execute.",
                "remediation": "Fix the shell command output contract.",
                "scope": "harness/fitness-functions",
                "severity": "warning",
                "side_effect_free": True,
                "adapter": "command",
                "command": [
                    "sh",
                    "-c",
                    'printf \'%s\\n\' \'{"contract_version":"1.0","rule_id":"custom.shell-pass","status":"pass","severity":"warning","summary":"ok","violations":[]}\'',
                ],
            }
        ],
    )

    parser = build_parser()
    args = parser.parse_args(
        [
            "--project-root",
            str(tmp_path),
            "fitness",
            "run",
            "--format",
            "json",
        ]
    )
    code = args.func(args)
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert payload["failed"] is False
    assert [result["rule_id"] for result in payload["results"]] == ["custom.shell-pass"]


def test_fitness_list_shows_declared_shell_rule_only(
    tmp_path: Path,
    capsys: Any,
) -> None:
    _write_manifest(
        tmp_path,
        [
            {
                "rule_id": "custom.shell-only",
                "name": "Shell only",
                "summary": "Only declared shell rule should be listed.",
                "rationale": "Prevents undeclared implicit rules from appearing.",
                "remediation": "Declare required rules in the manifest.",
                "scope": "harness/fitness-functions",
                "severity": "warning",
                "side_effect_free": True,
                "adapter": "command",
                "command": [
                    "sh",
                    "-c",
                    'printf \'%s\\n\' \'{"contract_version":"1.0","rule_id":"custom.shell-only","status":"pass","severity":"warning","summary":"ok","violations":[]}\'',
                ],
            }
        ],
    )

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
    code = args.func(args)
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert [entry["rule_id"] for entry in payload] == ["custom.shell-only"]
