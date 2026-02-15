from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from engineeringagent import cli as cli_module
from engineeringagent.cli import build_parser
from engineeringagent.config import resolve_docs_root
from engineeringagent.fitness import FitnessRunSummary
from engineeringagent.fitness.contracts import CONTRACT_VERSION, FitnessRuleResult


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


def _subcommand_parsers(
    parser: argparse.ArgumentParser,
) -> dict[str, argparse.ArgumentParser]:
    for action in parser._actions:
        choices = getattr(action, "choices", None)
        if isinstance(choices, dict):
            return {
                name: subparser
                for name, subparser in choices.items()
                if isinstance(subparser, argparse.ArgumentParser)
            }
    return {}


def _option_strings(parser: argparse.ArgumentParser) -> set[str]:
    return {option for action in parser._actions for option in action.option_strings}


def test_cli_surface_inventory_commands() -> None:
    parser = build_parser()
    root_commands = _subcommand_parsers(parser)

    assert set(root_commands) == {
        "fitness",
        "gates",
        "init",
        "reviewers",
        "run",
        "validate",
    }
    assert _option_strings(parser) == {"-h", "--help", "--project-root", "--version"}
    assert set(_subcommand_parsers(root_commands["gates"])) == {"list", "plan", "run"}
    assert set(_subcommand_parsers(root_commands["reviewers"])) == {
        "init",
        "list",
        "plan",
        "run",
    }
    assert set(_subcommand_parsers(root_commands["fitness"])) == {
        "catalog",
        "list",
        "run",
    }


def test_cli_surface_inventory_option_spellings() -> None:
    parser = build_parser()
    root_commands = _subcommand_parsers(parser)

    assert _option_strings(root_commands["validate"]) == {
        "-h",
        "--help",
        "--schema-only",
    }

    gates_commands = _subcommand_parsers(root_commands["gates"])
    assert _option_strings(gates_commands["list"]) == {"-h", "--help"}
    assert _option_strings(gates_commands["plan"]) == {
        "-h",
        "--help",
        "--profile",
        "--base",
        "--head",
    }
    assert _option_strings(gates_commands["run"]) == {
        "-h",
        "--help",
        "--profile",
        "--base",
        "--head",
        "--explain",
    }

    reviewers_commands = _subcommand_parsers(root_commands["reviewers"])
    assert _option_strings(reviewers_commands["init"]) == {"-h", "--help", "--force"}
    assert _option_strings(reviewers_commands["list"]) == {"-h", "--help"}
    assert _option_strings(reviewers_commands["plan"]) == {
        "-h",
        "--help",
        "--profile",
        "--phase",
        "--base",
        "--head",
    }
    assert _option_strings(reviewers_commands["run"]) == {
        "-h",
        "--help",
        "--reviewer",
        "--feature-id",
        "--feature-path",
        "--prior-feedback",
        "--base",
        "--head",
    }

    assert _option_strings(root_commands["run"]) == {
        "-h",
        "--help",
        "--all",
        "--implement-command",
        "--skip-implement",
        "--dry-run",
        "--max-iterations",
        "--allow-dirty",
        "--verbose-output",
    }

    fitness_commands = _subcommand_parsers(root_commands["fitness"])
    assert _option_strings(fitness_commands["list"]) == {
        "-h",
        "--help",
        "--manifest-path",
        "--format",
    }
    assert _option_strings(fitness_commands["run"]) == {
        "-h",
        "--help",
        "--manifest-path",
        "--jobs",
        "--format",
    }
    assert _option_strings(fitness_commands["catalog"]) == {
        "-h",
        "--help",
        "--manifest-path",
        "--format",
        "--output",
    }

    assert _option_strings(root_commands["init"]) == {
        "-h",
        "--help",
        "--force",
        "--scaffold-profile",
        "--docs-mode",
        "--scaffold-docs-dir",
    }


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


def test_root_version_flag_outputs_installed_package_version_only(
    capsys: Any,
    monkeypatch: Any,
) -> None:
    package_names: list[str] = []

    def _fake_version(distribution_name: str) -> str:
        package_names.append(distribution_name)
        return "9.9.9"

    monkeypatch.setattr(cli_module.importlib.metadata, "version", _fake_version)

    parser = build_parser()
    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args(["--version"])

    captured = capsys.readouterr()
    assert exc_info.value.code == 0
    assert captured.out == "9.9.9\n"
    assert captured.err == ""
    assert package_names == ["engineeringagent"]


def test_root_parser_still_requires_subcommand_without_version_flag(
    capsys: Any,
) -> None:
    parser = build_parser()

    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args([])

    captured = capsys.readouterr()
    assert exc_info.value.code == 2
    assert captured.out == ""
    assert "the following arguments are required: command" in captured.err


def test_main_runs_selected_handler(monkeypatch: Any) -> None:
    recorded: dict[str, object] = {}

    def _fake_run_legacy_cli_command(
        *,
        command: str,
        args: list[str],
        project_root: str,
    ) -> int:
        recorded["command"] = command
        recorded["args"] = args
        recorded["project_root"] = project_root
        return 0

    monkeypatch.setattr(
        cli_module,
        "_run_legacy_cli_command",
        _fake_run_legacy_cli_command,
    )

    with pytest.raises(SystemExit) as exc_info:
        cli_module.main(
            [
                "--project-root",
                "repo",
                "validate",
                "--schema-only",
            ]
        )

    assert exc_info.value.code == 0
    assert recorded == {
        "command": "validate",
        "args": ["--schema-only"],
        "project_root": "repo",
    }


def test_main_run_command_uses_typer_handler(monkeypatch: Any) -> None:
    recorded: dict[str, object] = {}

    def _fail_if_forwarded(**_kwargs: object) -> int:
        raise AssertionError("run command should not use legacy forwarding")

    def _fake_cmd_run(args: argparse.Namespace) -> int:
        recorded["project_root"] = args.project_root
        recorded["feature_paths"] = args.feature_paths
        recorded["all"] = args.all
        recorded["gate_profile"] = args.gate_profile
        recorded["skip_implement"] = args.skip_implement
        recorded["dry_run"] = args.dry_run
        recorded["max_iterations"] = args.max_iterations
        recorded["allow_dirty"] = args.allow_dirty
        recorded["verbose_output"] = args.verbose_output
        return 0

    monkeypatch.setattr(cli_module, "_run_legacy_cli_command", _fail_if_forwarded)
    monkeypatch.setattr(cli_module, "cmd_run", _fake_cmd_run)

    with pytest.raises(SystemExit) as exc_info:
        cli_module.main(
            [
                "--project-root",
                "repo",
                "run",
                "docs/spec/features/FEAT-900.yaml",
                "--all",
                "--skip-implement",
                "--dry-run",
                "--max-iterations",
                "7",
                "--allow-dirty",
                "--verbose-output",
            ]
        )

    assert exc_info.value.code == 0
    assert recorded == {
        "project_root": "repo",
        "feature_paths": ["docs/spec/features/FEAT-900.yaml"],
        "all": True,
        "gate_profile": "loop_fast",
        "skip_implement": True,
        "dry_run": True,
        "max_iterations": 7,
        "allow_dirty": True,
        "verbose_output": True,
    }


def test_main_init_command_uses_typer_handler(monkeypatch: Any) -> None:
    recorded: dict[str, object] = {}

    def _fail_if_forwarded(**_kwargs: object) -> int:
        raise AssertionError("init command should not use legacy forwarding")

    def _fake_cmd_init(args: argparse.Namespace) -> int:
        recorded["project_root"] = args.project_root
        recorded["force"] = args.force
        recorded["scaffold_profile"] = args.scaffold_profile
        recorded["docs_mode"] = args.docs_mode
        recorded["scaffold_docs_dir"] = args.scaffold_docs_dir
        return 0

    monkeypatch.setattr(cli_module, "_run_legacy_cli_command", _fail_if_forwarded)
    monkeypatch.setattr(cli_module, "cmd_init", _fake_cmd_init)

    with pytest.raises(SystemExit) as exc_info:
        cli_module.main(
            [
                "--project-root",
                "repo",
                "init",
                "--force",
                "--scaffold-profile",
                "python_uv",
                "--docs-mode",
                "separate",
                "--scaffold-docs-dir",
                "docs.custom",
            ]
        )

    assert exc_info.value.code == 0
    assert recorded == {
        "project_root": "repo",
        "force": True,
        "scaffold_profile": "python_uv",
        "docs_mode": "separate",
        "scaffold_docs_dir": "docs.custom",
    }


def test_root_version_flag_uses_distribution_metadata_source(
    capsys: Any,
    monkeypatch: Any,
) -> None:
    requested_distribution_names: list[str] = []

    def _fake_version(distribution_name: str) -> str:
        requested_distribution_names.append(distribution_name)
        return "3.2.1"

    monkeypatch.setattr(cli_module.importlib.metadata, "version", _fake_version)

    parser = build_parser()
    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args(["--version"])

    captured = capsys.readouterr()
    assert exc_info.value.code == 0
    assert captured.out == "3.2.1\n"
    assert captured.err == ""
    assert requested_distribution_names == ["engineeringagent"]


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
        [
            {
                "rule_id": "architecture.loop-subprocess-boundary",
                "name": "Loop subprocess boundary",
                "summary": "Enforce subprocess allowlist boundaries for command adapters/clients.",
                "rationale": "Centralizes command execution paths for consistent control.",
                "remediation": "Move OpenCode command execution to engineeringagent.opencode.client and Git command execution to engineeringagent.git.client.",
                "scope": "src/engineeringagent",
                "severity": "error",
                "side_effect_free": True,
                "adapter": "command",
                "command": [
                    "sh",
                    "-c",
                    'printf \'%s\\n\' \'{"contract_version":"1.0","rule_id":"architecture.loop-subprocess-boundary","status":"fail","severity":"error","summary":"failed","violations":["x"]}\'',
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


def test_fitness_run_json_uses_fallback_when_remediation_metadata_missing(
    tmp_path: Path,
    capsys: Any,
    monkeypatch: Any,
) -> None:
    parser = build_parser()

    orphan_result = FitnessRuleResult.model_validate(
        {
            "contract_version": "1.0",
            "rule_id": "custom.orphan-failure",
            "status": "fail",
            "severity": "warning",
            "summary": "orphan failure",
            "violations": ["missing metadata"],
        }
    )

    monkeypatch.setattr(cli_module, "build_rule_catalog", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(
        cli_module,
        "run_rule_catalog",
        lambda *_args, **_kwargs: FitnessRunSummary(results=(orphan_result,)),
    )

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

    assert code == 1
    assert payload["failed"] is True
    assert payload["failed_rules"] == [
        {
            "rule_id": "custom.orphan-failure",
            "status": "fail",
            "remediation": (
                "No remediation available: rule metadata missing from active "
                "catalog for custom.orphan-failure."
            ),
        }
    ]


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


def test_fitness_catalog_json_contract_is_deterministic(
    tmp_path: Path,
    capsys: Any,
) -> None:
    _write_manifest(
        tmp_path,
        [
            {
                "rule_id": "custom.catalog-contract",
                "name": "Catalog contract",
                "summary": "Ensure JSON catalog output remains stable.",
                "rationale": "Downstream tools parse catalog payloads.",
                "remediation": "Keep metadata contract stable.",
                "scope": "harness/fitness-functions",
                "severity": "warning",
                "side_effect_free": True,
                "adapter": "command",
                "command": [
                    "sh",
                    "-c",
                    'printf \'%s\\n\' \'{"contract_version":"1.0","rule_id":"custom.catalog-contract","status":"pass","severity":"warning","summary":"ok","violations":[]}\'',
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
            "catalog",
            "--format",
            "json",
        ]
    )
    code = args.func(args)
    output = capsys.readouterr().out
    payload = json.loads(output)

    assert code == 0
    assert payload == [
        {
            "adapter": "command",
            "name": "Catalog contract",
            "rationale": "Downstream tools parse catalog payloads.",
            "remediation": "Keep metadata contract stable.",
            "rule_id": "custom.catalog-contract",
            "scope": "harness/fitness-functions",
            "severity": "warning",
            "side_effect_free": True,
            "source": "custom",
            "summary": "Ensure JSON catalog output remains stable.",
        }
    ]
    assert tuple(payload[0].keys()) == (
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
    )


def test_docs_root_resolver_defaults_to_docs(tmp_path: Path) -> None:
    assert resolve_docs_root(tmp_path) == tmp_path / "docs"


def test_docs_root_resolver_prefers_engineeringagent_toml(tmp_path: Path) -> None:
    (tmp_path / "engineeringagent.toml").write_text(
        'docs-root = "docs.engineeringagent"\n',
        encoding="utf-8",
    )
    (tmp_path / "pyproject.toml").write_text(
        '[tool.engineeringagent]\ndocs-root = "docs.from.pyproject"\n',
        encoding="utf-8",
    )

    assert resolve_docs_root(tmp_path) == tmp_path / "docs.engineeringagent"


def test_docs_root_resolver_reads_pyproject_tool_engineeringagent(
    tmp_path: Path,
) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[tool.engineeringagent]\ndocs-root = "docs.from.pyproject"\n',
        encoding="utf-8",
    )

    assert resolve_docs_root(tmp_path) == tmp_path / "docs.from.pyproject"
