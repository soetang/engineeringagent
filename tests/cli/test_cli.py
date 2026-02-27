from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from typer.testing import CliRunner

from engineeringagent import cli as cli_module
from engineeringagent.config import (
    resolve_allow_duplicate_done_base_ids_below,
    resolve_docs_root,
)
from engineeringagent.loop_runtime.run_context import LoopRun, RunConfig


def _invoke_cli(args: list[str]) -> Any:
    runner = CliRunner(mix_stderr=False)
    return runner.invoke(cli_module.build_typer_app(), args)


def test_cli_surface_inventory_commands() -> None:
    result = _invoke_cli(["--help"])

    assert result.exit_code == 0
    for token in (
        "validate",
        "run",
        "checks",
        "fitness",
        "progress",
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
        (["checks", "run", "--help"], ["--checks", "--check-id", "--phase"]),
        (
            ["checks", "catalog", "--help"],
            ["--manifest-path", "--format", "--output"],
        ),
        (
            ["fitness", "run", "--help"],
            ["--format", "--phase", "--check-id", "--dry-run"],
        ),
        (
            ["progress", "handoff-append", "--help"],
            ["--feature-id", "--attempt", "--timestamp"],
        ),
        (
            ["progress", "feature-prune", "--help"],
            ["--feature-id"],
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


def test_main_checks_run_command_uses_typer_handler(monkeypatch: Any) -> None:
    recorded: dict[str, object] = {}

    def _fake_cmd_checks_run(args: Any) -> int:
        recorded["project_root"] = args.project_root
        recorded["checks"] = args.checks
        recorded["check_id"] = args.check_id
        recorded["feature_path"] = args.feature_path
        recorded["phase"] = args.phase
        recorded["base"] = args.base
        recorded["head"] = args.head
        recorded["verbose_output"] = args.verbose_output
        return 0

    monkeypatch.setattr(cli_module, "cmd_checks_run", _fake_cmd_checks_run)

    with pytest.raises(SystemExit) as exc_info:
        cli_module.main(
            [
                "--project-root",
                "repo",
                "checks",
                "run",
                "--checks",
                "commands",
                "--check-id",
                "smoke",
                "--phase",
                "feature_done",
                "--base",
                "main",
                "--head",
                "HEAD",
                "--verbose-output",
            ]
        )

    assert exc_info.value.code == 0
    assert recorded == {
        "project_root": "repo",
        "checks": ["commands"],
        "check_id": "smoke",
        "feature_path": None,
        "phase": cli_module.HarnessCheckPhase.FEATURE_DONE,
        "base": "main",
        "head": "HEAD",
        "verbose_output": True,
    }


def test_main_fitness_run_command_uses_typer_handler(monkeypatch: Any) -> None:
    recorded: dict[str, object] = {}

    def _fake_cmd_fitness_run(args: Any) -> int:
        recorded["project_root"] = args.project_root
        recorded["output_format"] = args.output_format
        recorded["phase"] = args.phase
        recorded["check_id"] = args.check_id
        recorded["base"] = args.base
        recorded["head"] = args.head
        recorded["dry_run"] = args.dry_run
        return 0

    monkeypatch.setattr(cli_module, "cmd_fitness_run", _fake_cmd_fitness_run)

    with pytest.raises(SystemExit) as exc_info:
        cli_module.main(
            [
                "--project-root",
                "repo",
                "fitness",
                "run",
                "--format",
                "json",
                "--phase",
                "feature_done",
                "--check-id",
                "boundary",
                "--base",
                "main",
                "--head",
                "HEAD",
                "--dry-run",
            ]
        )

    assert exc_info.value.code == 0
    assert recorded == {
        "project_root": "repo",
        "output_format": "json",
        "phase": cli_module.HarnessCheckPhase.FEATURE_DONE,
        "check_id": "boundary",
        "base": "main",
        "head": "HEAD",
        "dry_run": True,
    }


def test_cmd_run_builds_looprun_context_for_loop_entrypoint(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    captured: dict[str, LoopRun] = {}

    def _fake_run_loop(loop_run: LoopRun) -> int:
        captured["loop_run"] = loop_run
        return 7

    monkeypatch.setattr(cli_module, "run_loop_controller", _fake_run_loop)

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


def test_progress_handoff_append_reads_json_stdin_and_appends_markdown(
    tmp_path: Path,
) -> None:
    payload = {
        "summary": "Iteration completed.",
        "completed_work": ["Implemented CLI append command"],
        "verification": ["uv run pytest -q tests/cli/test_cli.py -k progress"],
        "remaining_work": ["Add docs updates"],
    }

    runner = CliRunner(mix_stderr=False)
    result = runner.invoke(
        cli_module.build_typer_app(),
        [
            "--project-root",
            str(tmp_path),
            "progress",
            "handoff-append",
            "--feature-id",
            "FEAT-130",
            "--attempt",
            "6",
            "--timestamp",
            "2026-02-25T07:00:00Z",
        ],
        input=json.dumps(payload),
    )

    assert result.exit_code == 0
    assert "fallback=false" in result.stdout
    handoff_path = tmp_path / "progress" / "features" / "FEAT-130" / "handoff.md"
    assert handoff_path.exists()


def test_progress_handoff_append_uses_fallback_for_invalid_json(
    tmp_path: Path,
) -> None:
    runner = CliRunner(mix_stderr=False)
    result = runner.invoke(
        cli_module.build_typer_app(),
        [
            "--project-root",
            str(tmp_path),
            "progress",
            "handoff-append",
            "--feature-id",
            "FEAT-130",
            "--attempt",
            "6",
        ],
        input="{bad-json",
    )

    assert result.exit_code == 0
    assert "fallback=true" in result.stdout
    assert (tmp_path / "progress" / "features" / "FEAT-130" / "handoff.md").exists()


def test_progress_feature_prune_removes_feature_progress_directory(
    tmp_path: Path,
) -> None:
    feature_dir = tmp_path / "progress" / "features" / "FEAT-130"
    feature_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / "run.txt").write_text("log\n", encoding="utf-8")

    runner = CliRunner(mix_stderr=False)
    result = runner.invoke(
        cli_module.build_typer_app(),
        [
            "--project-root",
            str(tmp_path),
            "progress",
            "feature-prune",
            "--feature-id",
            "FEAT-130",
        ],
    )

    assert result.exit_code == 0
    assert "removed path=progress/features/FEAT-130" in result.stdout
    assert not feature_dir.exists()


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


def test_cmd_validate_delegates_to_run_checks(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: Any,
) -> None:
    recorded: dict[str, object] = {}

    def _fake_run_checks(
        project_root: str | Path,
        *,
        phase: str,
        checks: list[str] | None = None,
        schema_only: bool = False,
        **_: object,
    ) -> Any:
        recorded["project_root"] = str(project_root)
        recorded["phase"] = phase
        recorded["checks"] = checks
        recorded["schema_only"] = schema_only
        return SimpleNamespace(ok=True, output="")

    monkeypatch.setattr("engineeringagent.checks.run_checks", _fake_run_checks)

    code = cli_module.cmd_validate(
        SimpleNamespace(project_root=str(tmp_path), schema_only=True)
    )
    output = capsys.readouterr().out

    assert code == 0
    assert "spec validation: ok" in output
    assert recorded == {
        "project_root": str(tmp_path),
        "phase": "manual",
        "checks": ["validate"],
        "schema_only": True,
    }


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


def test_specs_allow_duplicate_done_base_ids_below_defaults_to_none(
    tmp_path: Path,
) -> None:
    assert resolve_allow_duplicate_done_base_ids_below(tmp_path) is None


def test_specs_allow_duplicate_done_base_ids_below_prefers_engineeringagent_toml(
    tmp_path: Path,
) -> None:
    (tmp_path / "engineeringagent.toml").write_text(
        "[specs]\nallow-duplicate-done-base-ids-below = 100\n",
        encoding="utf-8",
    )
    (tmp_path / "pyproject.toml").write_text(
        "[tool.engineeringagent.specs]\nallow-duplicate-done-base-ids-below = 200\n",
        encoding="utf-8",
    )

    assert resolve_allow_duplicate_done_base_ids_below(tmp_path) == 100


def test_specs_allow_duplicate_done_base_ids_below_reads_pyproject_tool_engineeringagent_specs(
    tmp_path: Path,
) -> None:
    (tmp_path / "pyproject.toml").write_text(
        "[tool.engineeringagent.specs]\nallow-duplicate-done-base-ids-below = 100\n",
        encoding="utf-8",
    )

    assert resolve_allow_duplicate_done_base_ids_below(tmp_path) == 100


def test_specs_allow_duplicate_done_base_ids_below_engineeringagent_missing_table_returns_none(
    tmp_path: Path,
) -> None:
    (tmp_path / "engineeringagent.toml").write_text(
        "docs-root = 'docs'\n",
        encoding="utf-8",
    )

    assert resolve_allow_duplicate_done_base_ids_below(tmp_path) is None


def test_specs_allow_duplicate_done_base_ids_below_engineeringagent_non_table_specs_returns_none(
    tmp_path: Path,
) -> None:
    (tmp_path / "engineeringagent.toml").write_text(
        "specs = 'not-a-table'\n",
        encoding="utf-8",
    )

    assert resolve_allow_duplicate_done_base_ids_below(tmp_path) is None


def test_specs_allow_duplicate_done_base_ids_below_pyproject_missing_sections_returns_none(
    tmp_path: Path,
) -> None:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("[build-system]\nrequires = []\n", encoding="utf-8")
    assert resolve_allow_duplicate_done_base_ids_below(tmp_path) is None

    pyproject.write_text("tool = 'not-a-table'\n", encoding="utf-8")
    assert resolve_allow_duplicate_done_base_ids_below(tmp_path) is None

    pyproject.write_text("[tool]\nengineeringagent = 'not-a-table'\n", encoding="utf-8")
    assert resolve_allow_duplicate_done_base_ids_below(tmp_path) is None

    pyproject.write_text("[tool.engineeringagent]\n", encoding="utf-8")
    assert resolve_allow_duplicate_done_base_ids_below(tmp_path) is None

    pyproject.write_text(
        "[tool.engineeringagent]\nspecs = 'not-a-table'\n",
        encoding="utf-8",
    )
    assert resolve_allow_duplicate_done_base_ids_below(tmp_path) is None


@pytest.mark.parametrize(
    "payload",
    [
        "[specs]\nallow-duplicate-done-base-ids-below = true\n",
        "[specs]\nallow-duplicate-done-base-ids-below = 1.0\n",
        "[specs]\nallow-duplicate-done-base-ids-below = '100'\n",
        "[specs]\nallow-duplicate-done-base-ids-below = -1\n",
    ],
)
def test_specs_allow_duplicate_done_base_ids_below_rejects_invalid_values(
    tmp_path: Path,
    payload: str,
) -> None:
    (tmp_path / "engineeringagent.toml").write_text(payload, encoding="utf-8")

    with pytest.raises(ValueError, match="allow-duplicate-done-base-ids-below"):
        resolve_allow_duplicate_done_base_ids_below(tmp_path)
