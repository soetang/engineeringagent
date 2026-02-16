from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
import typer

from engineeringagent import cli as cli_module
from engineeringagent.fitness import FitnessRunSummary
from engineeringagent.fitness.contracts import FitnessRuleResult


def test_path_resolution_helpers_cover_manifest_and_absolute_paths(
    tmp_path: Path,
) -> None:
    assert cli_module._resolve_manifest_path(None) is None
    assert cli_module._resolve_manifest_path("harness/rules.yaml") == Path(
        "harness/rules.yaml"
    )

    absolute = tmp_path / "fitness-rules.json"
    assert (
        cli_module._resolve_optional_path(path=str(absolute), project_root=tmp_path)
        == absolute
    )


def test_resolve_init_docs_dir_reports_invalid_inputs(tmp_path: Path) -> None:
    docs_dir, error = cli_module._resolve_init_docs_dir(
        project_root=tmp_path,
        docs_mode=None,
        scaffold_docs_dir="",
    )
    assert docs_dir is None
    assert error == "init input error: --scaffold-docs-dir cannot be empty"

    (tmp_path / "docs").mkdir()
    docs_dir, error = cli_module._resolve_init_docs_dir(
        project_root=tmp_path,
        docs_mode="separate",
        scaffold_docs_dir="docs",
    )
    assert docs_dir is None
    assert (
        error
        == "init input error: --scaffold-docs-dir must differ from docs when using --docs-mode separate"
    )

    docs_dir, error = cli_module._resolve_init_docs_dir(
        project_root=tmp_path,
        docs_mode="invalid",
        scaffold_docs_dir="docs.engineeringagent",
    )
    assert docs_dir is None
    assert (
        error
        == "init input error: docs mode must be 'reuse' or 'separate' when docs/ exists"
    )


def test_resolve_init_agents_mode_rejects_invalid_prompt_selection(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    (tmp_path / "AGENTS.md").write_text("# AGENTS\n", encoding="utf-8")
    monkeypatch.setattr("builtins.input", lambda _prompt: "invalid")

    mode, error = cli_module._resolve_init_agents_mode(tmp_path, None)

    assert mode is None
    assert (
        error
        == "init input error: AGENTS mode must be 'overwrite', 'preserve', or 'abort' when AGENTS.md exists"
    )


def test_write_init_docs_root_config_skips_existing_file_without_force(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "engineeringagent.toml"
    config_path.write_text('docs-root = "docs.already"\n', encoding="utf-8")

    created, skipped = cli_module._write_init_docs_root_config(
        tmp_path,
        "docs.engineeringagent",
        force=False,
    )

    assert (created, skipped) == (0, 1)


def test_fitness_text_output_paths_cover_list_and_run(
    tmp_path: Path,
    monkeypatch: Any,
    capsys: Any,
) -> None:
    definition = SimpleNamespace(
        metadata=SimpleNamespace(
            rule_id="custom.rule",
            name="Custom rule",
            summary="custom summary",
            scope="harness/fitness-functions",
            severity=SimpleNamespace(value="warning"),
            adapter=SimpleNamespace(value="command"),
            source=SimpleNamespace(value="custom"),
            side_effect_free=True,
            rationale="custom rationale",
            remediation="custom remediation",
        )
    )
    monkeypatch.setattr(
        cli_module,
        "build_rule_catalog",
        lambda *_args, **_kwargs: [definition],
    )

    list_code = cli_module.cmd_fitness_list(
        SimpleNamespace(
            project_root=str(tmp_path),
            manifest_path=None,
            format="text",
        )
    )
    list_output = capsys.readouterr().out
    assert list_code == 0
    assert "custom.rule [warning] (command/custom) - custom summary" in list_output

    empty_summary = FitnessRunSummary(results=())
    monkeypatch.setattr(
        cli_module, "run_rule_catalog", lambda *_args, **_kwargs: empty_summary
    )

    empty_code = cli_module.cmd_fitness_run(
        SimpleNamespace(
            project_root=str(tmp_path),
            manifest_path=None,
            jobs=1,
            format="text",
        )
    )
    empty_output = capsys.readouterr().out
    assert empty_code == 0
    assert "No active fitness rules found." in empty_output

    pass_result = FitnessRuleResult.model_validate(
        {
            "contract_version": "1.0",
            "rule_id": "custom.pass",
            "status": "pass",
            "severity": "warning",
            "summary": "all good",
            "violations": [],
        }
    )
    nonempty_summary = FitnessRunSummary(results=(pass_result,))
    monkeypatch.setattr(
        cli_module,
        "run_rule_catalog",
        lambda *_args, **_kwargs: nonempty_summary,
    )

    nonempty_code = cli_module.cmd_fitness_run(
        SimpleNamespace(
            project_root=str(tmp_path),
            manifest_path=None,
            jobs=1,
            format="text",
        )
    )
    nonempty_output = capsys.readouterr().out
    assert nonempty_code == 0
    assert "custom.pass: pass - all good" in nonempty_output


def test_fitness_catalog_prints_absolute_path_when_output_is_outside_project_root(
    tmp_path: Path,
    monkeypatch: Any,
    capsys: Any,
) -> None:
    monkeypatch.setattr(cli_module, "build_rule_catalog", lambda *_args, **_kwargs: [])
    outside_path = tmp_path.parent / "external-fitness-catalog.md"

    code = cli_module.cmd_fitness_catalog(
        SimpleNamespace(
            project_root=str(tmp_path),
            manifest_path=None,
            format="markdown",
            output=str(outside_path),
        )
    )
    output = capsys.readouterr().out

    assert code == 0
    assert f"fitness catalog written: {outside_path}" in output


def test_cmd_init_reports_docs_and_agents_input_errors(
    tmp_path: Path,
    monkeypatch: Any,
    capsys: Any,
) -> None:
    args = SimpleNamespace(
        project_root=str(tmp_path),
        force=False,
        scaffold_profile="core",
        docs_mode=None,
        scaffold_docs_dir="docs.engineeringagent",
        agents_mode=None,
    )

    monkeypatch.setattr(
        cli_module,
        "_resolve_init_docs_dir",
        lambda **_kwargs: (None, "docs mode error"),
    )
    docs_error_code = cli_module.cmd_init(args)
    docs_error_output = capsys.readouterr().out
    assert docs_error_code == 1
    assert "docs mode error" in docs_error_output

    monkeypatch.setattr(
        cli_module,
        "_resolve_init_docs_dir",
        lambda **_kwargs: ("docs", None),
    )
    monkeypatch.setattr(
        cli_module,
        "_resolve_init_agents_mode",
        lambda **_kwargs: (None, "agents mode error"),
    )
    agents_error_code = cli_module.cmd_init(args)
    agents_error_output = capsys.readouterr().out
    assert agents_error_code == 1
    assert "agents mode error" in agents_error_output


def test_cmd_init_preserve_mode_reports_skipped_merge_spec(
    tmp_path: Path,
    monkeypatch: Any,
    capsys: Any,
) -> None:
    (tmp_path / "AGENTS.md").write_text("# User agents\n", encoding="utf-8")
    (tmp_path / "AGENTS.user.md").write_text("# Existing backup\n", encoding="utf-8")
    merge_spec_path = (
        tmp_path
        / "docs"
        / "spec"
        / "features"
        / "FEAT-900-merge-preserved-agents-guidance.yaml"
    )
    merge_spec_path.parent.mkdir(parents=True, exist_ok=True)
    merge_spec_path.write_text("id: FEAT-900\n", encoding="utf-8")

    monkeypatch.setattr(cli_module, "apply_baseline_scaffold", lambda **_kwargs: (0, 0))
    monkeypatch.setattr(
        cli_module,
        "_write_init_docs_root_config",
        lambda *_args, **_kwargs: (0, 0),
    )

    code = cli_module.cmd_init(
        SimpleNamespace(
            project_root=str(tmp_path),
            force=False,
            scaffold_profile="core",
            docs_mode="reuse",
            scaffold_docs_dir="docs.engineeringagent",
            agents_mode="preserve",
        )
    )
    output = capsys.readouterr().out

    assert code == 0
    assert (
        "merge_spec_skipped=docs/spec/features/FEAT-900-merge-preserved-agents-guidance.yaml"
        in output
    )


def test_version_callback_exits_with_zero(
    monkeypatch: Any,
) -> None:
    monkeypatch.setattr(cli_module.importlib.metadata, "version", lambda _name: "1.2.3")
    with pytest.raises(typer.Exit) as exc_info:
        cli_module._version_callback(True)
    assert exc_info.value.exit_code == 0


def test_project_root_from_context_defaults_to_current_directory() -> None:
    class _FakeContext:
        def find_root(self) -> SimpleNamespace:
            return SimpleNamespace(obj=None)

    assert cli_module._project_root_from_typer_context(cast(Any, _FakeContext())) == "."


def test_cli_module_no_longer_exposes_argparse_bridge() -> None:
    assert not hasattr(cli_module, "CommandArgs")
    assert not hasattr(cli_module, "build_parser")
    assert not hasattr(cli_module, "_dispatch_typer_command_with_argparse")
    assert not hasattr(cli_module, "_run_legacy_cli_command")
