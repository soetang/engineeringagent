from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import yaml
from typer.testing import CliRunner

from engineeringagent import cli as cli_module
from engineeringagent.config import resolve_docs_root
from engineeringagent.fitness import FitnessRunSummary
from engineeringagent.fitness.contracts import CONTRACT_VERSION, FitnessRuleResult
from engineeringagent.loop_runtime.run_context import LoopRun, RunConfig


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


def _invoke_cli(args: list[str]) -> Any:
    runner = CliRunner(mix_stderr=False)
    return runner.invoke(cli_module.build_typer_app(), args)


def test_cli_surface_inventory_commands() -> None:
    result = _invoke_cli(["--help"])

    assert result.exit_code == 0
    for token in (
        "validate",
        "run",
        "fitness",
        "init",
        "--project-root",
        "--version",
    ):
        assert token in result.stdout


def test_cli_surface_inventory_option_spellings() -> None:
    cases = [
        (["validate", "--help"], ["--schema-only"]),
        (
            ["run", "--help"],
            [
                "--all",
                "--dry-run",
                "--max-iterations",
                "--allow-dirty",
                "--verbose-output",
            ],
        ),
        (["fitness", "list", "--help"], ["--manifest-path", "--format"]),
        (["fitness", "run", "--help"], ["--manifest-path", "--jobs", "--format"]),
        (
            ["fitness", "catalog", "--help"],
            ["--manifest-path", "--format", "--output"],
        ),
        (
            ["init", "--help"],
            ["--force", "--scaffold-profile", "--docs-mode", "--scaffold-docs-dir"],
        ),
    ]

    for args, expected_options in cases:
        result = _invoke_cli(args)
        assert result.exit_code == 0
        assert "--help" in result.stdout
        for option in expected_options:
            assert option in result.stdout


def test_run_help_does_not_advertise_implement_command() -> None:
    removed_skip_flag = "--skip-" + "implement"
    result = _invoke_cli(["run", "--help"])
    stdout = result.stdout

    assert result.exit_code == 0
    assert "--implement-command" not in stdout
    assert removed_skip_flag not in stdout
    assert "skip implementation and run gates only" not in stdout
    assert "skip the implementation command" not in stdout


def test_run_rejects_removed_skip_flag() -> None:
    removed_skip_flag = "--skip-" + "implement"
    result = _invoke_cli(["run", "docs/spec/features/FEAT-900.yaml", removed_skip_flag])

    assert result.exit_code != 0
    combined_output = (result.stderr or "") + (result.stdout or "")
    assert removed_skip_flag in combined_output
    assert "No such option" in combined_output


def test_run_rejects_implement_command_option() -> None:
    result = _invoke_cli(["run", "--implement-command", "echo hi"])

    assert result.exit_code != 0
    assert "--implement-command" in (result.stderr or result.stdout)


def test_run_all_requires_checks_yaml(tmp_path: Path) -> None:
    result = _invoke_cli(
        [
            "--project-root",
            str(tmp_path),
            "run",
            "--all",
            "--dry-run",
        ]
    )

    assert result.exit_code == 1
    assert "missing harness/checks.yaml" in result.stdout
    assert "engineeringagent init" in result.stdout


def test_run_all_rejects_invalid_checks_yaml(tmp_path: Path) -> None:
    checks_path = tmp_path / "harness" / "checks.yaml"
    checks_path.parent.mkdir(parents=True, exist_ok=True)
    checks_path.write_text("checks: {}\n", encoding="utf-8")

    result = _invoke_cli(
        [
            "--project-root",
            str(tmp_path),
            "run",
            "--all",
            "--dry-run",
        ]
    )

    assert result.exit_code == 1
    assert "invalid harness/checks.yaml" in result.stdout
    assert "harness/checks.yaml:contract_version" in result.stdout


def test_run_all_rejects_legacy_harness_contract_files(tmp_path: Path) -> None:
    checks_path = tmp_path / "harness" / "checks.yaml"
    checks_path.parent.mkdir(parents=True, exist_ok=True)
    checks_path.write_text(
        "contract_version: '1.0'\nchecks: {}\n",
        encoding="utf-8",
    )

    legacy_path = tmp_path / "harness" / "gates.yaml"
    legacy_path.write_text("profiles: {}\n", encoding="utf-8")

    result = _invoke_cli(
        [
            "--project-root",
            str(tmp_path),
            "run",
            "--all",
            "--dry-run",
        ]
    )

    assert result.exit_code == 1
    assert "legacy harness contract" in result.stdout
    assert "harness/gates.yaml" in result.stdout
    assert "engineeringagent init" in result.stdout


def test_fitness_subcommands(tmp_path: Path, capsys: Any) -> None:
    src_dir = tmp_path / "src" / "engineeringagent"
    src_dir.mkdir(parents=True, exist_ok=True)
    for module_name in ["specs", "validator", "loop", "cli"]:
        (src_dir / f"{module_name}.py").write_text("\n", encoding="utf-8")

    list_code = cli_module.cmd_fitness_list(
        SimpleNamespace(
            project_root=str(tmp_path),
            manifest_path=None,
            output_format="json",
        )
    )
    list_output = capsys.readouterr().out
    list_payload = json.loads(list_output)

    assert list_code == 0
    assert list_payload == []

    run_code = cli_module.cmd_fitness_run(
        SimpleNamespace(
            project_root=str(tmp_path),
            manifest_path=None,
            jobs=2,
            output_format="json",
        )
    )
    run_output = capsys.readouterr().out
    run_payload = json.loads(run_output)

    assert run_code == 0
    assert run_payload["failed"] is False
    assert run_payload["results"] == []


@pytest.mark.parametrize("reported_version", ["9.9.9", "3.2.1"])
def test_root_version_flag_uses_distribution_metadata_source(
    reported_version: str,
    monkeypatch: Any,
) -> None:
    requested_distribution_names: list[str] = []

    def _fake_version(distribution_name: str) -> str:
        requested_distribution_names.append(distribution_name)
        return reported_version

    monkeypatch.setattr(cli_module.importlib.metadata, "version", _fake_version)

    result = _invoke_cli(["--version"])

    assert result.exit_code == 0
    assert result.stdout == f"{reported_version}\n"
    assert result.stderr == ""
    assert requested_distribution_names == ["engineeringagent"]


def test_root_parser_still_requires_subcommand_without_version_flag() -> None:
    result = _invoke_cli([])

    assert result.exit_code == 2
    assert result.stdout == ""
    assert "Missing command" in result.stderr


def test_main_validate_command_uses_typer_handler(monkeypatch: Any) -> None:
    recorded: dict[str, object] = {}

    def _fake_cmd_validate(args: Any) -> int:
        recorded["project_root"] = args.project_root
        recorded["schema_only"] = args.schema_only
        return 0

    monkeypatch.setattr(cli_module, "cmd_validate", _fake_cmd_validate)

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
        "project_root": "repo",
        "schema_only": True,
    }


def test_main_run_command_uses_typer_handler(monkeypatch: Any) -> None:
    recorded: dict[str, object] = {}

    def _fake_cmd_run(args: Any) -> int:
        recorded["project_root"] = args.project_root
        recorded["feature_paths"] = args.feature_paths
        recorded["run_all"] = args.run_all
        recorded["dry_run"] = args.dry_run
        recorded["max_iterations"] = args.max_iterations
        recorded["allow_dirty"] = args.allow_dirty
        recorded["verbose_output"] = args.verbose_output
        return 0

    monkeypatch.setattr(cli_module, "cmd_run", _fake_cmd_run)

    with pytest.raises(SystemExit) as exc_info:
        cli_module.main(
            [
                "--project-root",
                "repo",
                "run",
                "docs/spec/features/FEAT-900.yaml",
                "--all",
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
        "run_all": True,
        "dry_run": True,
        "max_iterations": 7,
        "allow_dirty": True,
        "verbose_output": True,
    }


def test_cmd_run_builds_looprun_context_for_loop_entrypoint(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    captured: dict[str, LoopRun] = {}

    def _fake_run_loop(loop_run: LoopRun) -> int:
        captured["loop_run"] = loop_run
        return 7

    monkeypatch.setattr(cli_module, "run_loop", _fake_run_loop)

    exit_code = cli_module.cmd_run(
        SimpleNamespace(
            project_root=str(tmp_path),
            feature_paths=["docs/spec/features/FEAT-078.yaml"],
            run_all=False,
            dry_run=True,
            max_iterations=7,
            allow_dirty=True,
            verbose_output=True,
        )
    )

    assert exit_code == 7
    loop_run = captured["loop_run"]
    assert isinstance(loop_run, LoopRun)
    assert loop_run.config == RunConfig(
        project_root=tmp_path,
        feature_paths=("docs/spec/features/FEAT-078.yaml",),
        dry_run=True,
        run_all=False,
        max_iterations=7,
        allow_dirty=True,
        verbose_output=True,
    )


def test_main_init_command_uses_typer_handler(monkeypatch: Any) -> None:
    recorded: dict[str, object] = {}

    def _fake_cmd_init(args: Any) -> int:
        recorded["project_root"] = args.project_root
        recorded["force"] = args.force
        recorded["scaffold_profile"] = args.scaffold_profile
        recorded["docs_mode"] = args.docs_mode
        recorded["scaffold_docs_dir"] = args.scaffold_docs_dir
        return 0

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

    code = cli_module.cmd_validate(
        SimpleNamespace(project_root=str(tmp_path), schema_only=False)
    )
    output = capsys.readouterr().out

    assert code == 1
    assert "AGENTS.md:4: docs-map path does not exist: docs/missing.md" in output


def test_fitness_run_json_includes_remediation_for_failures(
    tmp_path: Path,
    capsys: Any,
) -> None:
    src_dir = tmp_path / "src" / "engineeringagent"
    src_dir.mkdir(parents=True, exist_ok=True)
    for module_name in ["specs", "validator", "loop", "cli"]:
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

    code = cli_module.cmd_fitness_run(
        SimpleNamespace(
            project_root=str(tmp_path),
            manifest_path=None,
            jobs=1,
            output_format="json",
        )
    )
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

    code = cli_module.cmd_fitness_run(
        SimpleNamespace(
            project_root=str(tmp_path),
            manifest_path=None,
            jobs=1,
            output_format="json",
        )
    )
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert payload["failed"] is False
    assert [result["rule_id"] for result in payload["results"]] == ["custom.shell-pass"]


def test_fitness_run_json_uses_fallback_when_remediation_metadata_missing(
    tmp_path: Path,
    capsys: Any,
    monkeypatch: Any,
) -> None:
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

    code = cli_module.cmd_fitness_run(
        SimpleNamespace(
            project_root=str(tmp_path),
            manifest_path=None,
            jobs=1,
            output_format="json",
        )
    )
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

    code = cli_module.cmd_fitness_list(
        SimpleNamespace(
            project_root=str(tmp_path),
            manifest_path=None,
            output_format="json",
        )
    )
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

    code = cli_module.cmd_fitness_catalog(
        SimpleNamespace(
            project_root=str(tmp_path),
            manifest_path=None,
            output_format="json",
            output=None,
        )
    )
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
